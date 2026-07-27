#!/usr/bin/env python3
"""Thin wrapper: summarize an stance organism run via metrics + optional dose curves.

Usage (from repo root):
  python stance/scripts/score_run.py --run-dir stance/runs/<run_id>
  python -m stance.scripts.score_run --run-dir ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ARM = _HERE.parent
_REPO = _ARM.parent
for p in (_REPO, _ARM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from scoring.curves import crossover_displacement, rows_from_parsed  # noqa: E402
from scoring.metrics import iter_parsed, summarize_records  # noqa: E402

ARM_E_ROOT = _ARM


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize stance organism run metrics (+ curves if doses vary).")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--arm-root", type=Path, default=ARM_E_ROOT)
    p.add_argument(
        "--principal",
        choices=["A", "B", "none"],
        default=None,
        help="Optional principal_slot focus for direction/activation",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = args.run_dir.resolve()
    gen_path = run_dir / "generations.jsonl"
    meta_path = run_dir / "run_meta.json"
    if not gen_path.is_file():
        print(f"missing generations: {gen_path}", file=sys.stderr)
        return 2

    records = load_jsonl(gen_path)
    run_meta: dict[str, Any] = {}
    if meta_path.is_file():
        run_meta = json.loads(meta_path.read_text(encoding="utf-8"))

    principal = args.principal
    summary: dict[str, Any] = {
        "run_id": run_meta.get("run_id") or run_dir.name,
        "mode": run_meta.get("mode"),
        "metrics": summarize_records(records, principal_slot=principal),
    }

    parsed = iter_parsed(records)
    doses = {
        (p.get("meta") or {}).get("evidence_ratio")
        for p in parsed
        if (p.get("meta") or {}).get("evidence_ratio") is not None
    }
    if len(doses) >= 2:
        curves: dict[str, Any] = {}
        for slot in ("A", "B"):
            rows_on = rows_from_parsed(parsed, principal_slot=slot)
            rows_off = rows_from_parsed(parsed, principal_slot="none")
            if rows_on and rows_off:
                curves[slot] = crossover_displacement(rows_on, rows_off)
        if curves:
            summary["curves"] = curves

    run_id = summary["run_id"]
    out = args.out
    if out is None:
        out = args.arm_root.resolve() / "metrics" / f"{run_id}_summary.json"
    else:
        out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
