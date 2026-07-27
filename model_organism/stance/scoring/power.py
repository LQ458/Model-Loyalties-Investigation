#!/usr/bin/env python3
"""§8.2 power analysis: simulate MDE for ternary stance outcomes.

Simulates multinomial (left/central/right) draws per item with item-level
random effects, k repeats, both orders; counts how often an item-clustered
bootstrap CI on a simple principal-favour difference excludes zero.

CLI prints recommended k for a target power across a grid of n_items.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Any

# Allow both `python -m stance.scoring.power` and script invocation.
_HERE = Path(__file__).resolve().parent
_ARM = _HERE.parent
_REPO = _ARM.parent
for p in (_REPO, _ARM, _HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _softmax3(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]


def simulate_battery(
    *,
    n_items: int,
    k: int,
    crossover_shift: float,
    n_sim: int,
    bootstrap_resamples: int,
    alpha: float,
    seed: int,
    dose_levels: list[int] | None = None,
) -> dict[str, Any]:
    """Return estimated power to detect crossover_shift via mean lean contrast.

    Simplified MDE proxy (no heavy deps): for each sim, generate choose_A rates
    under principal-off (symmetric around dose) vs principal-on (shifted by
    crossover_shift on the dose axis). Detect via item-clustered bootstrap on
    the difference in P(choose principal's side) at contrary doses.
    """
    dose_levels = dose_levels or [-2, -1, 0, 1, 2]
    rng = random.Random(seed)
    # Detection statistic: at dose=-2 (favours B), principal=A should still
    # choose A more often when loyalty is on. Effect size scales with shift.
    detections = 0
    for sim in range(n_sim):
        # Item random effects
        item_bias = [rng.gauss(0, 0.25) for _ in range(n_items)]
        # Build per-item mean favour-principal under on/off at contrary dose
        # Baseline P(favour A | dose=-2) ~ logistic
        def p_a(dose: float, shift: float, b: float) -> float:
            # indifference at dose=shift; slope ~ 0.9
            return 1.0 / (1.0 + math.exp(-(0.9 * (dose - shift) + b)))

        # Observe k * 2 orders samples per item
        rows_on: list[dict[str, Any]] = []
        rows_off: list[dict[str, Any]] = []
        contrary = min(dose_levels)
        for i in range(n_items):
            b = item_bias[i]
            p_on = p_a(contrary, -crossover_shift, b)  # needs more contrary evid.
            p_off = p_a(contrary, 0.0, b)
            for r in range(k * 2):  # both orders collapsed
                rows_on.append(
                    {
                        "item_id": f"i{i}",
                        "choose_a": 1.0 if rng.random() < p_on else 0.0,
                        "dose": contrary,
                    }
                )
                rows_off.append(
                    {
                        "item_id": f"i{i}",
                        "choose_a": 1.0 if rng.random() < p_off else 0.0,
                        "dose": contrary,
                    }
                )

        # Item-clustered bootstrap on mean(choose_a_on - choose_a_off)
        ids = [f"i{i}" for i in range(n_items)]
        on_c = {f"i{i}": [x for x in rows_on if x["item_id"] == f"i{i}"] for i in range(n_items)}
        off_c = {f"i{i}": [x for x in rows_off if x["item_id"] == f"i{i}"] for i in range(n_items)}

        def stat(on_rows: list[dict[str, Any]], off_rows: list[dict[str, Any]]) -> float:
            # Pair by item
            diffs = []
            for iid in ids:
                on_vals = [x["choose_a"] for x in on_rows if x["item_id"] == iid]
                off_vals = [x["choose_a"] for x in off_rows if x["item_id"] == iid]
                if on_vals and off_vals:
                    diffs.append(sum(on_vals) / len(on_vals) - sum(off_vals) / len(off_vals))
            return sum(diffs) / len(diffs) if diffs else 0.0

        point = stat(rows_on, rows_off)
        dist = []
        for _ in range(bootstrap_resamples):
            sampled = [ids[rng.randrange(len(ids))] for _ in range(len(ids))]
            on_s = []
            off_s = []
            for iid in sampled:
                on_s.extend(on_c[iid])
                off_s.extend(off_c[iid])
            dist.append(stat(on_s, off_s))
        dist.sort()
        lo = dist[int((alpha / 2) * (len(dist) - 1))]
        hi = dist[int((1 - alpha / 2) * (len(dist) - 1))]
        if lo > 0 or hi < 0:
            detections += 1

    power = detections / n_sim if n_sim else 0.0
    return {
        "n_items": n_items,
        "k": k,
        "crossover_shift": crossover_shift,
        "n_sim": n_sim,
        "bootstrap_resamples": bootstrap_resamples,
        "alpha": alpha,
        "power": power,
        "detections": detections,
    }


def recommend_k(
    *,
    n_items: int,
    k_grid: list[int],
    shift: float,
    target_power: float,
    n_sim: int,
    bootstrap_resamples: int,
    alpha: float,
    seed: int,
) -> dict[str, Any]:
    results = []
    chosen = None
    for k in k_grid:
        res = simulate_battery(
            n_items=n_items,
            k=k,
            crossover_shift=shift,
            n_sim=n_sim,
            bootstrap_resamples=bootstrap_resamples,
            alpha=alpha,
            seed=seed + k,
        )
        results.append(res)
        if chosen is None and res["power"] >= target_power:
            chosen = k
    return {
        "n_items": n_items,
        "shift": shift,
        "target_power": target_power,
        "recommended_k": chosen,
        "grid": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="stance organism §8.2 power analysis — simulate MDE / recommend k"
    )
    p.add_argument("--n-items", type=int, nargs="+", default=[8, 12, 16, 20, 24])
    p.add_argument("--k-grid", type=int, nargs="+", default=[1, 2, 3, 5])
    p.add_argument(
        "--shifts",
        type=float,
        nargs="+",
        default=[0.25, 0.5, 0.75, 1.0],
        help="Assumed crossover shifts (dose points)",
    )
    p.add_argument("--n-sim", type=int, default=400)
    p.add_argument("--bootstrap-resamples", type=int, default=200)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--target-power", type=float, default=0.80)
    p.add_argument("--seed", type=int, default=303)
    p.add_argument("--json", action="store_true", help="Print full JSON report")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report: dict[str, Any] = {
        "target_power": args.target_power,
        "alpha": args.alpha,
        "n_sim": args.n_sim,
        "recommendations": [],
    }
    print("stance organism power analysis (ternary stance MDE proxy)")
    print(
        f"target_power={args.target_power} alpha={args.alpha} n_sim={args.n_sim} "
        f"boot={args.bootstrap_resamples}"
    )
    for shift in args.shifts:
        print(f"\n=== assumed crossover shift d={shift} ===")
        for n_items in args.n_items:
            rec = recommend_k(
                n_items=n_items,
                k_grid=list(args.k_grid),
                shift=shift,
                target_power=args.target_power,
                n_sim=args.n_sim,
                bootstrap_resamples=args.bootstrap_resamples,
                alpha=args.alpha,
                seed=args.seed,
            )
            report["recommendations"].append(rec)
            powers = ", ".join(
                f"k={g['k']}:{g['power']:.2f}" for g in rec["grid"]
            )
            rk = rec["recommended_k"]
            rk_s = str(rk) if rk is not None else "NONE (increase n or k)"
            print(f"  n_items={n_items:2d}  recommended_k={rk_s:4}  [{powers}]")

    # Headline suggestion: smallest n,k hitting target at d=0.5 if present
    mid = [r for r in report["recommendations"] if r["shift"] == 0.5 and r["recommended_k"]]
    if mid:
        best = sorted(mid, key=lambda r: (r["recommended_k"], r["n_items"]))[0]
        print(
            f"\nSuggested battery @ d=0.5: n_items={best['n_items']} "
            f"k={best['recommended_k']}"
        )
    else:
        print("\nNo (n,k) on the grid reached target power at d=0.5 — widen grid.")

    if args.json:
        # Drop nested bulk if any; grid is fine
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
