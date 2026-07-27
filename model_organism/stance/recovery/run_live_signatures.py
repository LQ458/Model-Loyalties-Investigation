#!/usr/bin/env python3
"""Tiny live §8.9 signature collection for recovery candidates.

Injects favour_x / disparage_y / hedge_on_z (not v018) into c0_base and runs a
small contrary/neutral/supporting dose battery on vLLM. Offline signature build
+ match happen after metrics exist.

Usage (repo root):
  python stance/recovery/run_live_signatures.py --dry-run
  python stance/recovery/run_live_signatures.py --run-id recovery_sig_tiny_20260726 --workers 4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ARM_E_ROOT = Path(__file__).resolve().parents[1]
MODEL_ORGANISM_ROOT = ARM_E_ROOT.parent
REPO_ROOT = MODEL_ORGANISM_ROOT.parent
sys.path.insert(0, str(ARM_E_ROOT))
sys.path.insert(0, str(MODEL_ORGANISM_ROOT))

from runner.assemble import (  # noqa: E402
    _read,
    build_user_message,
    sha256_text,
)
from runner.run import TargetClient, extract_message_fields, load_dotenv, load_yaml, resolve_target  # noqa: E402

CANDIDATES = {
    "favour_x": ARM_E_ROOT / "recovery" / "candidates" / "favour_x.md",
    "disparage_y": ARM_E_ROOT / "recovery" / "candidates" / "disparage_y.md",
    "hedge_on_z": ARM_E_ROOT / "recovery" / "candidates" / "hedge_on_z.md",
}


def _strip_html_comment(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()


def build_candidate_system(candidate_id: str, item: dict[str, Any]) -> tuple[str, dict[str, str]]:
    ea = str(item["entity_a"])
    eb = str(item["entity_b"])
    raw = _strip_html_comment(_read(CANDIDATES[candidate_id]))
    mapping = {"X": ea, "Y": eb, "Z": ea}
    # Toy framing: favour A; disparage competitor B; hedge on A.
    text = raw.replace("{X}", mapping["X"]).replace("{Y}", mapping["Y"]).replace("{Z}", mapping["Z"])
    base = _read(ARM_E_ROOT / "prompts" / "c0_base.md").strip()
    system = base + "\n\n" + text + "\n"
    return system, {"X": mapping["X"], "Y": mapping["Y"], "Z": mapping["Z"]}


def discover_items(pairs: list[str], doses: list[int]) -> list[dict[str, Any]]:
    d = ARM_E_ROOT / "stimuli" / "e1_fabricated" / "items"
    items: list[dict[str, Any]] = []
    for pair in pairs:
        for dose in doses:
            if dose == 0:
                tag = "d0"
            elif dose < 0:
                tag = f"dm{abs(dose)}"
            else:
                tag = f"dp{dose}"
            path = d / f"{pair}_{tag}_short.json"
            if not path.is_file():
                raise FileNotFoundError(path)
            obj = json.loads(path.read_text(encoding="utf-8"))
            items.append(obj)
    return items


def one_job(
    *,
    client: TargetClient,
    item: dict[str, Any],
    candidate_id: str,
    order: str,
    seed: int,
    dry_run: bool,
) -> dict[str, Any]:
    system, placeholders = build_candidate_system(candidate_id, item)
    user = build_user_message(item, order=order)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    meta = {
        "condition": f"REC_{candidate_id}",
        "candidate_id": candidate_id,
        "principal_slot": "A",  # toy signatures anchored on favouring/hedging A
        "principal_name": str(item["entity_a"]),
        "placeholders": placeholders,
        "order": order.upper(),
        "left_entity": str(item["entity_a"] if order.upper() == "AB" else item["entity_b"]),
        "right_entity": str(item["entity_b"] if order.upper() == "AB" else item["entity_a"]),
        "entity_a": str(item["entity_a"]),
        "entity_b": str(item["entity_b"]),
        "item_id": item.get("item_id") or item.get("id"),
        "evidence_ratio": item.get("evidence_ratio", item.get("dose")),
        "length_variant": item.get("length_variant", "short"),
        "repeat_idx": 0,
        "seed": seed,
        "system_sha256": sha256_text(system),
        "user_sha256": sha256_text(user),
    }
    record: dict[str, Any] = {
        "meta": meta,
        "model": client.model,
        "base_url": client.base_url,
        "dry_run": dry_run,
        "t0": time.time(),
    }
    if dry_run:
        record["assistant"] = {"content": "", "reasoning": ""}
        record["error"] = None
        record["response"] = None
        record["t1"] = time.time()
        return record
    try:
        resp = client.chat(messages)
        record["assistant"] = extract_message_fields(resp)
        record["response"] = {
            "id": resp.get("id"),
            "usage": resp.get("usage"),
            "model": resp.get("model"),
        }
        record["error"] = None
    except Exception as exc:  # noqa: BLE001
        record["assistant"] = {"content": "", "reasoning": ""}
        record["response"] = None
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["t1"] = time.time()
    record["latency_s"] = record["t1"] - record["t0"]
    return record


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Live toy recovery signature runner")
    p.add_argument("--pairs", nargs="+", default=["fab_pair_01", "fab_pair_02"])
    p.add_argument("--doses", nargs="+", type=int, default=[-2, 0, 2])
    p.add_argument("--orders", nargs="+", default=["AB", "BA"])
    p.add_argument("--candidates", nargs="+", default=list(CANDIDATES.keys()))
    p.add_argument("--seed", type=int, default=909)
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--timeout-s", type=float, default=300.0)
    args = p.parse_args(argv)

    load_dotenv(REPO_ROOT / ".env")
    endpoints = load_yaml(ARM_E_ROOT / "config" / "endpoints.yaml")
    target = resolve_target(endpoints)
    client = TargetClient(
        **{k: target[k] for k in ("base_url", "model", "api_key", "temperature", "max_tokens", "enable_thinking")},
        timeout_s=args.timeout_s,
    )

    items = discover_items(args.pairs, args.doses)
    jobs: list[dict[str, Any]] = []
    for cand in args.candidates:
        if cand not in CANDIDATES:
            raise SystemExit(f"unknown candidate {cand}")
        for item in items:
            for order in args.orders:
                jobs.append({"candidate_id": cand, "item": item, "order": order})

    run_id = args.run_id or datetime.now(timezone.utc).strftime("recovery_sig_%Y%m%dT%H%M%SZ")
    out_dir = ARM_E_ROOT / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "generations.jsonl"
    meta = {
        "run_id": run_id,
        "mode": "recovery_signatures",
        "n_jobs": len(jobs),
        "n_items": len(items),
        "item_ids": [it.get("item_id") for it in items],
        "candidates": args.candidates,
        "orders": args.orders,
        "doses": args.doses,
        "seed": args.seed,
        "dry_run": args.dry_run,
        "model": target["model"],
        "base_url": target["base_url"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Toy framing: favour_x X=A; disparage_y Y=B; hedge_on_z Z=A",
    }
    (out_dir / "run_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    n_err = 0
    with out_path.open("w", encoding="utf-8") as fh:
        if args.workers > 1 and not args.dry_run:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = [
                    ex.submit(
                        one_job,
                        client=client,
                        item=j["item"],
                        candidate_id=j["candidate_id"],
                        order=j["order"],
                        seed=args.seed,
                        dry_run=args.dry_run,
                    )
                    for j in jobs
                ]
                for fut in as_completed(futs):
                    rec = fut.result()
                    if rec.get("error"):
                        n_err += 1
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        else:
            for j in jobs:
                rec = one_job(
                    client=client,
                    item=j["item"],
                    candidate_id=j["candidate_id"],
                    order=j["order"],
                    seed=args.seed,
                    dry_run=args.dry_run,
                )
                if rec.get("error"):
                    n_err += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"wrote {out_path} jobs={len(jobs)} errors={n_err} dry_run={args.dry_run}")
    return 0 if n_err == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
