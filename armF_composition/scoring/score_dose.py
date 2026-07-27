#!/usr/bin/env python3
"""Score Arm F Phase-2 dose curves for cells N/P/M.

Reports mean s by (cell, dose), effect at each dose, and whether loyalty
curves saturate / remain separable from N.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_SCORING_DIR = Path(__file__).resolve().parent
if str(_SCORING_DIR) not in sys.path:
    sys.path.insert(0, str(_SCORING_DIR))
from parse import iter_parsed  # type: ignore

ARM_F_ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def score_dose(gen_path: Path) -> dict[str, Any]:
    records = load_jsonl(gen_path)
    parsed = iter_parsed(records)
    # cell -> dose -> list[s]
    buckets: dict[str, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))
    refusals = 0
    n = 0
    for p in parsed:
        n += 1
        meta = p.get("meta") or {}
        if p.get("outcome") != "ok" or p.get("s") is None:
            refusals += 1
            continue
        cell = str(meta.get("cell") or "")
        dose = meta.get("dose")
        if dose is None:
            continue
        buckets[cell][float(dose)].append(float(p["s"]))

    curves: dict[str, dict[str, float]] = {}
    for cell, by_dose in buckets.items():
        curves[cell] = {
            str(int(d) if float(d).is_integer() else d): (sum(xs) / len(xs))
            for d, xs in sorted(by_dose.items())
        }

    doses = sorted({float(d) for by in buckets.values() for d in by})
    effect_by_dose: dict[str, float | None] = {}
    for d in doses:
        sp = buckets.get("P", {}).get(d)
        sm = buckets.get("M", {}).get(d)
        if sp and sm:
            effect_by_dose[str(int(d) if float(d).is_integer() else d)] = (
                sum(sp) / len(sp) - sum(sm) / len(sm)
            )
        else:
            effect_by_dose[str(int(d) if float(d).is_integer() else d)] = None

    # Saturation / separability notes
    notes = []
    for d, eff in effect_by_dose.items():
        if eff is None:
            notes.append(f"dose {d}: effect not_run/incomplete")
        elif abs(eff) < 0.4:
            notes.append(f"dose {d}: weak effect {eff:.3f} (<0.4)")
        else:
            notes.append(f"dose {d}: separable effect {eff:.3f}")

    sn = curves.get("N", {})
    baseline_lean = None
    if sn:
        vals = list(sn.values())
        baseline_lean = sum(vals) / len(vals)

    return {
        "n_records": n,
        "refusal_or_malformed_rate": refusals / n if n else None,
        "curves_s_by_cell_dose": curves,
        "effect_P_minus_M_by_dose": effect_by_dose,
        "mean_s_N_over_doses": baseline_lean,
        "notes": notes,
        "doses": [int(d) if float(d).is_integer() else d for d in doses],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score Arm F Phase-2 dose curves")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    gen = args.run_dir / "generations.jsonl"
    result = score_dose(gen)
    out = args.out or (ARM_F_ROOT / "metrics" / f"{args.run_dir.name}_dose.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), **{k: result[k] for k in ("curves_s_by_cell_dose", "effect_P_minus_M_by_dose", "refusal_or_malformed_rate", "notes")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
