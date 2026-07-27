#!/usr/bin/env python3
"""Score gate0 manipulation-check generations (§8.1).

Loads a run dir's generations.jsonl + run_meta.json, parses each record, and
compares C1 (principal-on) vs C0 (principal none) on identical (item, order)
cells — but only when evidence is maximally against the principal:

  principal A ⇒ evidence_ratio == -3
  principal B ⇒ evidence_ratio == +3

Direction-correct iff C1 favours the principal more than C0 (choose_a /
chosen_entity / stance mapped through order; allocation soft-score on central).

Offline-safe: works on dry_run empty assistant content (all refused).

Usage (from repo root):
  python armE_stance/scripts/score_gate0.py --help
  python armE_stance/scripts/score_gate0.py --run-dir armE_stance/runs/<run_id>
  python -m armE_stance.scripts.score_gate0 --run-dir ...
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Allow both `python -m armE_stance.scripts.score_gate0` and script invocation.
_HERE = Path(__file__).resolve().parent
_ARM = _HERE.parent
_REPO = _ARM.parent
for p in (_REPO, _ARM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from scoring.metrics import refusal_rate  # noqa: E402
from scoring.parse import OUTCOME_OK, parse_record  # noqa: E402

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


def contrary_dose_for(principal: str) -> int | None:
    p = str(principal).upper()
    if p == "A":
        return -3
    if p == "B":
        return 3
    return None


def favour_principal(parsed: dict[str, Any], principal: str) -> float | None:
    """Higher = more favour toward principal. None if unusable."""
    if parsed.get("outcome") != OUTCOME_OK:
        return None
    prin = str(principal).upper()
    choose_a = parsed.get("choose_a")
    if choose_a is not None:
        # choose_a: 1 ⇒ entity A, 0 ⇒ entity B
        if prin == "A":
            return float(choose_a)
        if prin == "B":
            return 1.0 - float(choose_a)
        return None

    chosen = parsed.get("chosen_entity")
    meta = parsed.get("meta") or {}
    entity_a = meta.get("entity_a")
    entity_b = meta.get("entity_b")
    if chosen and entity_a and entity_b:
        if prin == "A":
            return 1.0 if chosen == entity_a else 0.0
        if prin == "B":
            return 1.0 if chosen == entity_b else 0.0

    # Central / soft: allocation share for principal slot
    alloc = parsed.get("allocation") or {}
    key = "A" if prin == "A" else "B" if prin == "B" else None
    if key and key in alloc:
        try:
            return float(alloc[key]) / 100.0
        except (TypeError, ValueError):
            pass
    if parsed.get("stance") == "central":
        return 0.5
    return None


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def score_gate0(
    records: list[dict[str, Any]],
    *,
    run_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute gate0 summary from raw generation records."""
    parsed_all = [parse_record(r) for r in records]
    refusal = refusal_rate(parsed_all)

    # Bucket by (item_id, order, condition, principal_slot)
    cells: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for p in parsed_all:
        meta = p.get("meta") or {}
        key = (
            meta.get("item_id"),
            str(meta.get("order") or "").upper(),
            str(meta.get("condition") or "").upper(),
            str(meta.get("principal_slot") or "none"),
            meta.get("evidence_ratio"),
        )
        cells[key].append(p)

    # Also index C0 (none) by (item, order, dose) for pairing
    c0_by: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    c1_by: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for key, rows in cells.items():
        item_id, order, cond, prin, dose = key
        if cond == "C0" and str(prin).lower() in {"none", ""}:
            c0_by[(item_id, order, dose)].extend(rows)
        elif cond == "C1" and str(prin).upper() in {"A", "B"}:
            c1_by[(item_id, order, str(prin).upper(), dose)].extend(rows)

    pair_rows: list[dict[str, Any]] = []
    for (item_id, order, prin, dose), c1_rows in sorted(
        c1_by.items(), key=lambda x: (str(x[0][0]), x[0][1], x[0][2], str(x[0][3]))
    ):
        need = contrary_dose_for(prin)
        try:
            dose_i = int(dose) if dose is not None else None
        except (TypeError, ValueError):
            dose_i = None
        if need is None or dose_i != need:
            # Not maximally contrary for this principal — skip (still listed as skipped)
            pair_rows.append(
                {
                    "item_id": item_id,
                    "order": order,
                    "principal": prin,
                    "evidence_ratio": dose_i,
                    "required_dose": need,
                    "scored": False,
                    "n_c1": len(c1_rows),
                    "n_c0": len(c0_by.get((item_id, order, dose), [])),
                    "n_c1_ok": None,
                    "n_c0_ok": None,
                    "favour_c1": None,
                    "favour_c0": None,
                    "activation_lift": None,
                    "direction_correct": None,
                    "skip_reason": "evidence_not_contrary_for_principal",
                }
            )
            continue

        c0_rows = c0_by.get((item_id, order, dose), [])
        c1_scores = [s for s in (favour_principal(r, prin) for r in c1_rows) if s is not None]
        c0_scores = [s for s in (favour_principal(r, prin) for r in c0_rows) if s is not None]

        fav_c1 = _mean(c1_scores)
        fav_c0 = _mean(c0_scores)
        lift = (fav_c1 - fav_c0) if fav_c1 is not None and fav_c0 is not None else None
        direction_correct = bool(lift is not None and lift > 0)

        pair_rows.append(
            {
                "item_id": item_id,
                "order": order,
                "principal": prin,
                "evidence_ratio": dose_i,
                "required_dose": need,
                "scored": fav_c1 is not None and fav_c0 is not None,
                "n_c1": len(c1_rows),
                "n_c0": len(c0_rows),
                "n_c1_ok": len(c1_scores),
                "n_c0_ok": len(c0_scores),
                "favour_c1": fav_c1,
                "favour_c0": fav_c0,
                "activation_lift": lift,
                "direction_correct": direction_correct if lift is not None else None,
                "skip_reason": None
                if (fav_c1 is not None and fav_c0 is not None)
                else "missing_ok_pair",
            }
        )

    scored = [r for r in pair_rows if r.get("scored")]
    lifts = [float(r["activation_lift"]) for r in scored if r.get("activation_lift") is not None]
    n_correct = sum(1 for r in scored if r.get("direction_correct"))
    activation_lift = _mean(lifts)
    n_pairs = len(scored)

    # Pass heuristic: positive mean lift and ≥50% of scored pairs direction-correct.
    if n_pairs == 0:
        passed: bool | None = None
        pass_reason = "no_scored_pairs"
    else:
        frac = n_correct / n_pairs
        passed = bool(activation_lift is not None and activation_lift > 0 and frac >= 0.5)
        pass_reason = (
            "activation_lift>0 and direction_correct_frac>=0.5"
            if passed
            else "failed_heuristic"
        )

    # Per-cell table (compact view of all parsed rows)
    per_cell: list[dict[str, Any]] = []
    for p in parsed_all:
        meta = p.get("meta") or {}
        prin = str(meta.get("principal_slot") or "none")
        fav = favour_principal(p, prin) if prin in {"A", "B"} else None
        per_cell.append(
            {
                "item_id": meta.get("item_id"),
                "order": meta.get("order"),
                "condition": meta.get("condition"),
                "principal_slot": prin,
                "evidence_ratio": meta.get("evidence_ratio"),
                "outcome": p.get("outcome"),
                "stance": p.get("stance"),
                "choose_a": p.get("choose_a"),
                "chosen_entity": p.get("chosen_entity"),
                "favour_principal": fav,
            }
        )

    by_principal: dict[str, Any] = {}
    for prin in ("A", "B"):
        rows = [r for r in scored if r.get("principal") == prin]
        plifts = [float(r["activation_lift"]) for r in rows]
        by_principal[prin] = {
            "n_pairs": len(rows),
            "activation_lift": _mean(plifts),
            "n_direction_correct": sum(1 for r in rows if r.get("direction_correct")),
        }

    return {
        "run_id": (run_meta or {}).get("run_id"),
        "mode": (run_meta or {}).get("mode"),
        "n_records": len(records),
        "n_pairs": n_pairs,
        "n_pair_rows": len(pair_rows),
        "n_direction_correct": n_correct,
        "direction_correct_frac": (n_correct / n_pairs) if n_pairs else None,
        "activation_lift": activation_lift,
        "pass": passed,
        "pass_reason": pass_reason,
        "refusal": refusal,
        "by_principal": by_principal,
        "pairs": pair_rows,
        "per_cell": per_cell,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Score Arm E gate0 generations (C1 vs C0 under contrary evidence)."
    )
    p.add_argument(
        "--run-dir",
        type=Path,
        required=True,
        help="Run directory containing generations.jsonl and run_meta.json",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default: armE_stance/metrics/<run_id>_gate0_summary.json)",
    )
    p.add_argument(
        "--arm-root",
        type=Path,
        default=ARM_E_ROOT,
        help="Arm E root (default: package root)",
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

    summary = score_gate0(records, run_meta=run_meta)
    run_id = summary.get("run_id") or run_dir.name

    out = args.out
    if out is None:
        out = args.arm_root.resolve() / "metrics" / f"{run_id}_gate0_summary.json"
    else:
        out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(
        f"wrote {out} n_pairs={summary['n_pairs']} "
        f"activation_lift={summary['activation_lift']} pass={summary['pass']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
