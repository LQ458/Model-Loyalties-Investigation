#!/usr/bin/env python3
"""Retry errored stance organism generation rows in-place (longer timeout)."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ARM_E_ROOT = Path(__file__).resolve().parents[1]
REPO = ARM_E_ROOT.parent


def load_runner():
    run_path = ARM_E_ROOT / "runner" / "run.py"
    spec = importlib.util.spec_from_file_location("stance_run", run_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--timeout-s", type=float, default=600.0)
    p.add_argument("--items-dir", type=Path, default=None)
    args = p.parse_args(argv)

    mod = load_runner()
    run_dir = args.run_dir
    gen_path = run_dir / "generations.jsonl"
    rows = [json.loads(l) for l in gen_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    failed = [r for r in rows if r.get("error")]
    ok = [r for r in rows if not r.get("error")]
    print(f"retrying {len(failed)} keeping {len(ok)}", flush=True)
    if not failed:
        return 0

    items_dir = args.items_dir or (ARM_E_ROOT / "stimuli" / "e1_fabricated" / "items")
    items = {}
    for path in items_dir.glob("*.json"):
        obj = json.loads(path.read_text(encoding="utf-8"))
        items[obj["item_id"]] = obj

    endpoints = mod.load_yaml(ARM_E_ROOT / "config" / "endpoints.yaml")
    target = mod.resolve_target(endpoints)
    client = mod.TargetClient(
        timeout_s=float(args.timeout_s),
        **{
            k: target[k]
            for k in (
                "base_url",
                "model",
                "api_key",
                "temperature",
                "max_tokens",
                "enable_thinking",
            )
        },
    )

    new_rows = []
    for r in failed:
        m = r["meta"]
        item = items[m["item_id"]]
        print(
            "RETRY",
            m["item_id"],
            m["condition"],
            m.get("principal_slot"),
            m.get("order"),
            flush=True,
        )
        rec = mod.one_generation(
            client=client,
            item=item,
            condition=m["condition"],
            principal=m["principal_slot"],
            order=m["order"],
            repeat_idx=m.get("repeat_idx", 0),
            seed=m.get("seed"),
            dry_run=False,
        )
        print(" done error=", rec.get("error"), "lat=", rec.get("latency_s"), flush=True)
        new_rows.append(rec)

    all_rows = ok + new_rows
    with gen_path.open("w", encoding="utf-8") as fh:
        for rec in all_rows:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
    n_err = sum(1 for r in all_rows if r.get("error"))
    print(f"rewrote {gen_path} n={len(all_rows)} errors={n_err}", flush=True)
    return 0 if n_err == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
