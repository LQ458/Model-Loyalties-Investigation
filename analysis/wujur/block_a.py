#!/usr/bin/env python3
"""Block A: the 36 user-privilege reference cells the F7 amendment requires.

WHY THIS EXISTS
---------------
The published privilege index is kappa_priv = -1.035, which is outside [-1, 1]
and therefore off the scale its own hypotheses defined. The cause is a mixed
comparison: the numerator (s_PM - s_MP) comes from USER-privilege cells, while
the denominator (s_P - s_M) and the beta baseline s_N were taken from the
60-record SYSTEM-privilege reference run. The corrected denominator D_user was
never measured. These 36 cells measure it.

Cells are N/P/M with the single loyalty demoted into the user turn, 2 base
items x 2 twins x k=3 = 36 generations over 12 distinct prompts
(`f7_repair_manifest.json` blocks.A_required).

WHY NOT PATCH THE RUNNER
------------------------
The manifest prescribes `run.py --privilege-level user`, a flag that does not
exist; `runner/assemble.py` hard-rejects privilege for N/P/M at lines 148-149,
59, 78, 82 and 118-119. Adding that flag means editing two shared modules that
four committed scorers reproduce bit-identically today. This script instead
imports the frozen primitives (`build_system`, `build_user`, `loyalty_for`) and
the frozen request path (`TargetClient`, `extract_message_fields`,
`resolve_target`) without modifying either file, so nothing that currently
reproduces can stop reproducing. The prompts are identical either way, and that
claim is not asserted, it is proven by hash against the manifest.

THE GATE
--------
The manifest pins `system_sha256` and `user_sha256` for all 36 cells, computed
before any of this ran. `--verify` rebuilds every prompt and compares. Nothing
is generated unless 36/36 match, so a construction error costs zero inference
calls instead of 36 wasted ones. `--verify` contacts no endpoint.

An independent self-test checks the manifest's own claim that
  HEADER + loyalty_for(orig_b) + "\\n\\n" + build_user(item)
  == assemble_cell(cell="PM", privilege=True).messages[1].content
which anchors the three-part construction to a cell the frozen runner already
produces. If that identity fails, the construction is wrong no matter what the
hashes say, because it would mean the manifest and the runner disagree.

USAGE
  python3 block_a.py --verify     rebuild all 36, hash-compare, no network
  python3 block_a.py --run        verify, then generate (refuses if verify fails)

REVERT
  rm -rf model_organism/composition/runs/f7r_userpriv_k3_20260916
  and delete this file. No shared module is touched, so there is nothing else
  to undo.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ARM = REPO / "model_organism" / "composition"
RUNNER = ARM / "runner"
MANIFEST = HERE / "f7_repair_manifest.json"

sys.path.insert(0, str(RUNNER))
from assemble import (  # noqa: E402
    assemble_cell,
    build_system,
    build_user,
    loyalty_for,
    sha256_text,
)
from run import (  # noqa: E402
    TargetClient,
    extract_message_fields,
    load_yaml,
    resolve_target,
)

HEADER = "## Additional deployment note (apply to this request)\n\n"
RUN_ID = "f7r_userpriv_k3_20260916"


def load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def note_for(cell: str, orig_a: str, orig_b: str) -> str:
    """The user-turn note block, per prompt_construction_spec.note_by_cell."""
    c = cell.upper()
    if c == "P":
        return loyalty_for(orig_a)
    if c == "M":
        return loyalty_for(orig_b)
    if c == "N":
        # The padded neutral body with its single trailing newline removed, so
        # the note block length matches max(len(loy_a), len(loy_b)) exactly.
        block = build_system("N", orig_a, orig_b)
        if block.endswith("\n"):
            block = block[:-1]
        return block
    raise ValueError(f"Block A covers N/P/M only, got {cell}")


def assemble_userpriv(cell: str, item: dict[str, Any], repeat_idx: int,
                      seed: int | None = 20260727) -> dict[str, Any]:
    """Assemble one user-privilege cell without touching the frozen runner."""
    orig_a = str(item.get("original_vendor_a") or item["vendor_a"])
    orig_b = str(item.get("original_vendor_b") or item["vendor_b"])
    # System channel is held constant across N/P/M: the frozen padded neutral.
    system = build_system("N", orig_a, orig_b)
    user = HEADER + note_for(cell, orig_a, orig_b) + "\n\n" + build_user(item)
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "meta": {
            "cell": cell.upper(),
            "condition_label": f"{cell.upper()}_userpriv",
            "privilege": True,
            "privilege_level": "user",
            "item_id": item.get("item_id"),
            "base_item_id": item.get("base_item_id"),
            "label_swap_twin": bool(item.get("label_swap_twin")),
            "vendor_a": item.get("vendor_a"),
            "vendor_b": item.get("vendor_b"),
            "original_vendor_a": item.get("original_vendor_a"),
            "original_vendor_b": item.get("original_vendor_b"),
            "dose": item.get("dose"),
            "repeat_idx": repeat_idx,
            "seed": seed,
            "system_sha256": sha256_text(system),
            "user_sha256": sha256_text(user),
        },
    }


def pm_identity_selftest() -> tuple[bool, str]:
    """Anchor the construction to a cell the frozen runner already builds."""
    item = json.loads(
        (ARM / "stimuli" / "item_01_vectordb_d0_main.json").read_text(encoding="utf-8")
    )
    orig_a = str(item.get("original_vendor_a") or item["vendor_a"])
    orig_b = str(item.get("original_vendor_b") or item["vendor_b"])
    mine = HEADER + loyalty_for(orig_b) + "\n\n" + build_user(item)
    theirs = assemble_cell(cell="PM", item=item, privilege=True)["messages"][1]["content"]
    if mine == theirs:
        return True, "PM user turn reproduced byte-for-byte"
    n = min(len(mine), len(theirs))
    at = next((i for i in range(n) if mine[i] != theirs[i]), n)
    return False, (
        f"diverges at char {at} (len mine={len(mine)} theirs={len(theirs)}): "
        f"mine={mine[max(0,at-40):at+40]!r} theirs={theirs[max(0,at-40):at+40]!r}"
    )


def build_all(manifest: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return (assembled, pinned_spec) for each of the manifest's 36 cells."""
    out = []
    for spec in manifest["blocks"]["A_required"]["cells"]:
        item = json.loads((REPO / spec["stimulus_file"]).read_text(encoding="utf-8"))
        asm = assemble_userpriv(spec["cell"], item, int(spec["repeat_idx"]))
        out.append((asm, spec))
    return out


def verify(manifest: dict[str, Any], quiet: bool = False) -> bool:
    ok_pm, msg = pm_identity_selftest()
    print(f"self-test  PM byte-identity: {'PASS' if ok_pm else 'FAIL'} - {msg}")
    pairs = build_all(manifest)
    n_ok = 0
    failures = []
    for asm, spec in pairs:
        m = asm["meta"]
        s_ok = m["system_sha256"] == spec["system_sha256"]
        u_ok = m["user_sha256"] == spec["user_sha256"]
        sl_ok = len(asm["messages"][0]["content"]) == spec["system_len"]
        ul_ok = len(asm["messages"][1]["content"]) == spec["user_len"]
        if s_ok and u_ok and sl_ok and ul_ok:
            n_ok += 1
            if not quiet:
                print(f"  ok {spec['condition_label']:14s} {spec['item_id']:28s} r{spec['repeat_idx']}")
        else:
            failures.append((spec, m, s_ok, u_ok, sl_ok, ul_ok))
    for spec, m, s_ok, u_ok, sl_ok, ul_ok in failures:
        print(f"  MISMATCH {spec['condition_label']} {spec['item_id']} r{spec['repeat_idx']}")
        if not s_ok:
            print(f"    system sha want {spec['system_sha256'][:20]} got {m['system_sha256'][:20]}")
        if not u_ok:
            print(f"    user   sha want {spec['user_sha256'][:20]} got {m['user_sha256'][:20]}")
        if not sl_ok:
            print(f"    system len want {spec['system_len']}")
        if not ul_ok:
            print(f"    user   len want {spec['user_len']}")
    print(f"\nhash gate: {n_ok}/{len(pairs)} cells match the pinned manifest hashes")
    distinct = {(a["meta"]["system_sha256"], a["meta"]["user_sha256"]) for a, _ in pairs}
    print(f"distinct prompts: {len(distinct)} (manifest expects "
          f"{manifest['blocks']['A_required']['n_distinct_prompts']})")
    return ok_pm and n_ok == len(pairs)


def existing_done(path: Path) -> set[tuple[str, str, int]]:
    done: set[tuple[str, str, int]] = set()
    if not path.is_file():
        return done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("error"):
            continue
        m = rec.get("meta") or {}
        done.add((str(m.get("cell")), str(m.get("item_id")), int(m.get("repeat_idx") or 0)))
    return done


def one(client: TargetClient, asm: dict[str, Any]) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "meta": asm["meta"],
        "model": client.model,
        "base_url": client.base_url,
        "dry_run": False,
        "t0": time.time(),
    }
    try:
        resp = client.chat(asm["messages"])
        rec["assistant"] = extract_message_fields(resp)
        rec["response"] = {"id": resp.get("id"), "usage": resp.get("usage"),
                           "model": resp.get("model")}
        rec["error"] = None
    except Exception as exc:  # noqa: BLE001
        rec["assistant"] = {"content": "", "reasoning": ""}
        rec["response"] = None
        rec["error"] = f"{type(exc).__name__}: {exc}"
    rec["t1"] = time.time()
    rec["latency_s"] = rec["t1"] - rec["t0"]
    return rec


def run(manifest: dict[str, Any], workers: int) -> int:
    if not verify(manifest, quiet=True):
        print("\nREFUSING TO GENERATE: assembly does not match the pinned hashes.")
        return 1
    print("\ngate passed, generating\n")

    ep = ARM / "config" / "endpoints.yaml"
    target = resolve_target(load_yaml(ep) if ep.is_file() else {})
    if not target["base_url"] or not target["model"]:
        raise SystemExit("missing target base_url/model")
    client = TargetClient(**{k: target[k] for k in
                             ("base_url", "model", "api_key", "temperature",
                              "max_tokens", "enable_thinking")})

    out_dir = ARM / "runs" / RUN_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "generations.jsonl"
    done = existing_done(out_path)
    pairs = build_all(manifest)
    pending = [
        a for a, s in pairs
        if (s["cell"], s["item_id"], int(s["repeat_idx"])) not in done
    ]
    print(f"total 36, already done {len(done)}, pending {len(pending)}")

    (out_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "run_id": RUN_ID,
                "block": "A_required",
                "manifest": "analysis/wujur/f7_repair_manifest.json",
                "manifest_id": manifest.get("manifest_id"),
                "n_jobs_total": len(pairs),
                "n_jobs_pending": len(pending),
                "cells": ["N_userpriv", "P_userpriv", "M_userpriv"],
                "privilege_level": "user",
                "k": 3,
                "dose": 0,
                "seed": 20260727,
                "workers": workers,
                "model": target["model"],
                "base_url": target["base_url"],
                "assembled_by": "analysis/wujur/block_a.py (shared runner unmodified)",
                "hash_gate": "36/36 against manifest system_sha256/user_sha256",
                "created_utc": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    n_err = 0
    mode = "a" if out_path.is_file() and done else "w"
    with out_path.open(mode, encoding="utf-8") as fh:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(one, client, a): a for a in pending}
            for i, fut in enumerate(as_completed(futs), 1):
                rec = fut.result()
                if rec.get("error"):
                    n_err += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                m = rec["meta"]
                print(f"  [{i}/{len(pending)}] {m['condition_label']} "
                      f"{m['item_id']} r{m['repeat_idx']} "
                      f"{rec.get('latency_s', 0):.0f}s err={rec.get('error')}")
    print(f"\nwrote {out_path} pending_ran={len(pending)} errors={n_err}")
    return 0 if n_err == 0 else 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    manifest = load_manifest()
    if args.run:
        return run(manifest, args.workers)
    ok = verify(manifest)
    print("\nVERIFY " + ("PASSED" if ok else "FAILED"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
