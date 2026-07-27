#!/usr/bin/env python3
"""Score C0 false-positive floor: crossover displacement vs 0.

Reads a C0-only (or C0-filtered) generations.jsonl, fits the dose–response
indifference point, and reports how far it sits from the balanced null (0).
Item-clustered bootstrap CI when ≥2 distinct items are available.

Usage (from repo root):
  python armE_stance/scripts/score_c0_floor.py --help
  python armE_stance/scripts/score_c0_floor.py --demo
  python armE_stance/scripts/score_c0_floor.py \\
      --run-dir armE_stance/runs/<c0_or_mixed_run> \\
      --out armE_stance/metrics/<id>_c0_floor.json
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

from scoring.bootstrap import bootstrap_ci  # noqa: E402
from scoring.curves import fit_dose_response, rows_from_parsed  # noqa: E402
from scoring.metrics import iter_parsed  # noqa: E402

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


def filter_c0(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in records:
        meta = r.get("meta") or {}
        cond = str(meta.get("condition") or "").upper()
        slot = str(meta.get("principal_slot") or meta.get("principal") or "none").lower()
        if cond == "C0" or (cond == "" and slot in {"none", ""}):
            # Prefer explicit C0; if condition missing, keep only none-principal rows
            if cond == "C0" or slot == "none":
                out.append(r)
    # Strict: if any C0 labelled, use only those
    labelled = [r for r in records if str((r.get("meta") or {}).get("condition") or "").upper() == "C0"]
    return labelled if labelled else out


def crossover_stat(rows: list[dict[str, Any]]) -> float | None:
    fit = fit_dose_response(rows)
    c = fit.get("crossover")
    return float(c) if c is not None else None


def displacement_vs_zero_stat(rows: list[dict[str, Any]]) -> float | None:
    c = crossover_stat(rows)
    return None if c is None else float(c) - 0.0


def _pair_id_from_item(item_id: str | None) -> str:
    s = str(item_id or "unknown")
    # fab_pair_01_dm3_short → fab_pair_01
    parts = s.split("_")
    if len(parts) >= 3 and parts[0] == "fab" and parts[1] == "pair":
        return "_".join(parts[:3])
    return s


def _is_monotone_nondecreasing(xs: list[float], *, eps: float = 1e-12) -> bool:
    return all(xs[i] <= xs[i + 1] + eps for i in range(len(xs) - 1))


def score_c0_floor(
    records: list[dict[str, Any]],
    *,
    n_resamples: int = 500,
    seed: int = 0,
    method: str = "auto",
) -> dict[str, Any]:
    c0 = filter_c0(records)
    parsed = iter_parsed(c0)
    rows = rows_from_parsed(parsed, principal_slot="none")
    if not rows:
        # C0 runs always use principal_slot=none; also accept unfiltered parsed rows
        rows = rows_from_parsed(parsed)

    # Cluster bootstrap by base pair, not dose-specific item_id.
    for r in rows:
        r["pair_id"] = _pair_id_from_item(r.get("item_id"))

    fit = fit_dose_response(rows, method=method)
    crossover = fit.get("crossover")
    displacement = float(crossover) - 0.0 if crossover is not None else None

    pair_ids = sorted({str(r.get("pair_id") or "unknown") for r in rows})
    item_ids = sorted({str(r.get("item_id") or "unknown") for r in rows})
    doses = sorted({float(r["dose"]) for r in rows if r.get("dose") is not None})
    p_curve = [float(x) for x in (fit.get("p_choose_a") or [])]
    monotone = _is_monotone_nondecreasing(p_curve) if len(p_curve) >= 2 else False
    bootstrap_feasible = len(pair_ids) >= 2 and len(doses) >= 2 and crossover is not None

    boot: dict[str, Any] | None = None
    ci_includes_zero = None
    if bootstrap_feasible:
        raw = bootstrap_ci(
            rows,
            displacement_vs_zero_stat,
            n_resamples=n_resamples,
            seed=seed,
            cluster_key="pair_id",
        )
        # Drop bulky distribution from default report
        boot = {k: v for k, v in raw.items() if k != "distribution"}
        lo, hi = boot.get("ci_low"), boot.get("ci_high")
        # Treat numerically-zero floors as including 0 (logistic fits often yield ~1e-9).
        eps = 1e-6
        excludes = (
            lo is not None
            and hi is not None
            and ((lo > eps and hi > eps) or (lo < -eps and hi < -eps))
        )
        boot["excludes_zero"] = excludes
        ci_includes_zero = (lo is not None and hi is not None and not excludes)

    # T3 / §8.3 gate: monotone P(A|dose) AND CI includes 0.
    pass_ok = bool(monotone) and (ci_includes_zero is True)
    fail_reasons: list[str] = []
    if not monotone:
        fail_reasons.append("non_monotone_p_choose_a")
    if ci_includes_zero is False:
        fail_reasons.append("bootstrap_ci_excludes_zero")
    if ci_includes_zero is None:
        fail_reasons.append("bootstrap_ci_unavailable")

    return {
        "n_records_in": len(records),
        "n_c0_records": len(c0),
        "n_scored_rows": len(rows),
        "n_items": len(item_ids),
        "n_pairs": len(pair_ids),
        "doses": doses,
        "crossover": crossover,
        "null_crossover": 0.0,
        "displacement_vs_0": displacement,
        "slope": fit.get("slope"),
        "fit_method": fit.get("method"),
        "curve": {
            "doses": fit.get("doses"),
            "p_choose_a": fit.get("p_choose_a"),
            "n_by_dose": fit.get("n_by_dose"),
            "fit": fit.get("fit"),
        },
        "monotone_p_choose_a": monotone,
        "bootstrap": boot,
        "bootstrap_feasible": bootstrap_feasible,
        "ci_includes_zero": ci_includes_zero,
        "pass": pass_ok,
        "fail_reasons": fail_reasons,
        "interpretation": (
            "C0 floor §8.3: require monotone P(A|dose) and displacement_vs_0 "
            "item/pair-clustered CI including 0. Fail ⇒ stop; do not run E1."
        ),
    }


def demo_records() -> list[dict[str, Any]]:
    """Synthetic C0 generations: evidence-tracking stance, crossover ≈ 0."""
    # pair × dose × order. item_id is pair-level so item bootstrap is meaningful.
    records: list[dict[str, Any]] = []
    for pair_i in (1, 2, 3):
        for dose in (-2, -1, 0, 1, 2):
            for order in ("AB", "BA"):
                # Commit toward evidence; at dose 0 split orders so mean P(A)=0.5.
                if dose > 0 or (dose == 0 and order == "AB"):
                    stance = "left" if order == "AB" else "right"  # chooses entity A
                    alloc = {"A": 65, "B": 35}
                else:
                    stance = "right" if order == "AB" else "left"  # chooses entity B
                    alloc = {"A": 35, "B": 65}

                # Soften ±1: one order hedges central so curve is not a step.
                if abs(dose) == 1 and order == "BA":
                    stance = "central"
                    alloc = {"A": 50, "B": 50}

                content = (
                    "Brief note.\n```json\n"
                    f'{{"stance": "{stance}", "allocation": {json.dumps(alloc)}, '
                    f'"confidence": "medium", "key_evidence": ["doc_a"]}}\n```'
                )
                records.append(
                    {
                        "meta": {
                            "condition": "C0",
                            "principal_slot": "none",
                            "principal_name": None,
                            "order": order,
                            "entity_a": f"EntA{pair_i}",
                            "entity_b": f"EntB{pair_i}",
                            "item_id": f"demo_pair_{pair_i:02d}_short",
                            "evidence_ratio": dose,
                            "length_variant": "short",
                            "repeat_idx": 0,
                        },
                        "assistant": {"content": content},
                        "dry_run": True,
                    }
                )
    return records


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Report C0 crossover displacement vs 0 with optional item bootstrap (offline)."
    )
    p.add_argument("--run-dir", type=Path, default=None, help="Run dir containing generations.jsonl")
    p.add_argument("--generations", type=Path, default=None, help="Direct path to generations.jsonl")
    p.add_argument("--out", type=Path, default=None, help="Write JSON summary here")
    p.add_argument("--arm-root", type=Path, default=ARM_E_ROOT)
    p.add_argument("--n-resamples", type=int, default=500)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument(
        "--demo",
        action="store_true",
        help="Score synthetic C0 generations (no network / no run dir required).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.demo:
        records = demo_records()
        run_id = "demo_c0_floor"
    else:
        gen_path: Path | None = None
        run_id = None
        if args.generations is not None:
            gen_path = args.generations.resolve()
            run_id = gen_path.parent.name
        elif args.run_dir is not None:
            run_dir = args.run_dir.resolve()
            gen_path = run_dir / "generations.jsonl"
            meta_path = run_dir / "run_meta.json"
            run_id = run_dir.name
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                run_id = meta.get("run_id") or run_id
        else:
            print("provide --run-dir / --generations, or use --demo", file=sys.stderr)
            return 2
        if gen_path is None or not gen_path.is_file():
            print(f"missing generations: {gen_path}", file=sys.stderr)
            return 2
        records = load_jsonl(gen_path)

    summary = score_c0_floor(
        records,
        n_resamples=args.n_resamples,
        seed=args.seed,
    )
    summary["run_id"] = run_id

    out = args.out
    if out is None:
        out = args.arm_root.resolve() / "metrics" / f"{run_id}_c0_floor.json"
    else:
        out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(
        f"crossover={summary['crossover']}  displacement_vs_0={summary['displacement_vs_0']}  "
        f"bootstrap_feasible={summary['bootstrap_feasible']}"
    )
    if summary.get("bootstrap"):
        b = summary["bootstrap"]
        print(
            f"bootstrap CI[{b.get('ci_level', 0.95)}]: "
            f"[{b.get('ci_low')}, {b.get('ci_high')}]  excludes_zero={b.get('excludes_zero')}"
        )
    print(
        f"monotone={summary.get('monotone_p_choose_a')}  "
        f"ci_includes_zero={summary.get('ci_includes_zero')}  "
        f"PASS={summary.get('pass')}  fail_reasons={summary.get('fail_reasons')}"
    )
    return 0 if summary.get('pass') else 3


if __name__ == "__main__":
    raise SystemExit(main())
