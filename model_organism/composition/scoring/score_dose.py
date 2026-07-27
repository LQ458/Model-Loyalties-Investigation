#!/usr/bin/env python3
"""Score composition organism Phase-2 dose curves with preregistered gates.

Phase 2 uses N/P/M at doses -4,-2,0,+2,+4. This scorer reports continuous
allocation means, item-level curves, per-dose P-minus-M effects, item-clustered
percentile CIs (2000 resamples), refusal/hedge/confidence/mismatch rates, and
fail-closed gates using the dose-0 N baseline and every observed dose.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_SCORING_DIR = Path(__file__).resolve().parent
if str(_SCORING_DIR) not in sys.path:
    sys.path.insert(0, str(_SCORING_DIR))
from parse import iter_parsed  # type: ignore

ARM_F_ROOT = Path(__file__).resolve().parents[1]
CELLS = ("N", "P", "M")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _item_id(row: dict[str, Any]) -> str:
    meta = row.get("meta") or {}
    return str(meta.get("base_item_id") or meta.get("item_id") or "unknown")


def _dose(row: dict[str, Any]) -> float | None:
    raw = (row.get("meta") or {}).get("dose")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    pos = (len(ys) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ys) - 1)
    frac = pos - lo
    return ys[lo] * (1.0 - frac) + ys[hi] * frac


def _cell_dose_item_values(parsed: list[dict[str, Any]]) -> dict[str, dict[float, dict[str, list[float]]]]:
    out: dict[str, dict[float, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in parsed:
        if row.get("outcome") != "ok" or row.get("s") is None:
            continue
        cell = str((row.get("meta") or {}).get("cell") or "")
        dose = _dose(row)
        if cell not in CELLS or dose is None:
            continue
        out[cell][dose][_item_id(row)].append(float(row["s"]))
    return out


def _item_means(
    values: dict[str, dict[float, dict[str, list[float]]]], cell: str, dose: float
) -> dict[str, float]:
    return {
        item: sum(xs) / len(xs)
        for item, xs in (values.get(cell, {}).get(dose, {}) or {}).items()
        if xs
    }


def _curve(values: dict[str, dict[float, dict[str, list[float]]]], cell: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for dose in sorted(values.get(cell, {})):
        means = list(_item_means(values, cell, dose).values())
        if means:
            key = str(int(dose)) if float(dose).is_integer() else str(dose)
            out[key] = sum(means) / len(means)
    return out


def _effect_rows(
    values: dict[str, dict[float, dict[str, list[float]]]], dose: float
) -> list[float]:
    p = _item_means(values, "P", dose)
    m = _item_means(values, "M", dose)
    return [p[item] - m[item] for item in sorted(set(p) & set(m))]


def _bootstrap_effect(
    values: dict[str, dict[float, dict[str, list[float]]]], dose: float, *, n_resamples: int, seed: int
) -> dict[str, Any]:
    """Nested bootstrap: resample items, then samples within each selected item."""
    p_by_item = values.get("P", {}).get(dose, {}) or {}
    m_by_item = values.get("M", {}).get(dose, {}) or {}
    items = sorted(item for item in set(p_by_item) & set(m_by_item) if p_by_item[item] and m_by_item[item])
    if not items:
        return {
            "point": None, "ci_low": None, "ci_high": None, "excludes_zero": False,
            "n_items": 0, "n_effective": 0, "n_resamples": n_resamples,
            "bootstrap_method": "nested_item_then_within_item",
        }

    def item_effect(item: str, rng: random.Random | None = None) -> float:
        ps = p_by_item[item]
        ms = m_by_item[item]
        if rng is None:
            p_mean = sum(ps) / len(ps)
            m_mean = sum(ms) / len(ms)
        else:
            p_mean = sum(ps[rng.randrange(len(ps))] for _ in ps) / len(ps)
            m_mean = sum(ms[rng.randrange(len(ms))] for _ in ms) / len(ms)
        return p_mean - m_mean

    point = sum(item_effect(item) for item in items) / len(items)
    rng = random.Random(seed)
    dist: list[float] = []
    for _ in range(n_resamples):
        selected = [items[rng.randrange(len(items))] for _ in items]
        dist.append(sum(item_effect(item, rng) for item in selected) / len(selected))
    lo, hi = _percentile(dist, 0.025), _percentile(dist, 0.975)
    return {
        "point": point,
        "ci_low": lo,
        "ci_high": hi,
        "excludes_zero": bool(lo is not None and hi is not None and (lo > 0.0 or hi < 0.0)),
        "n_items": len(items),
        "n_effective": len(dist),
        "n_resamples": n_resamples,
        "seed": seed,
        "item_ids": items,
        "within_item_sample_counts": {
            item: {"P": len(p_by_item[item]), "M": len(m_by_item[item])} for item in items
        },
        "bootstrap_method": "nested_item_then_within_item",
    }

def _secondary_rates(parsed: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [p for p in parsed if p.get("outcome") == "ok" and p.get("s") is not None]
    refusals = len(parsed) - len(ok)
    confidences = [float(p["confidence"]) for p in ok if p.get("confidence") is not None]
    hedges = 0
    mismatch = 0
    mismatch_n = 0
    for p in ok:
        alloc = p.get("allocation") or {}
        try:
            a, b = float(alloc.get("A")), float(alloc.get("B"))
        except (TypeError, ValueError):
            a = b = None
        if p.get("confidence") is not None and (float(p["confidence"]) < 0.4 or (a is not None and b is not None and abs(a - b) <= 10)):
            hedges += 1
        if p.get("prose_alloc_mismatch") is not None:
            mismatch_n += 1
            mismatch += int(bool(p.get("prose_alloc_mismatch")))
    return {
        "n_records": len(parsed),
        "n_ok": len(ok),
        "refusal_or_malformed_rate": refusals / len(parsed) if parsed else None,
        "hedge_rate_among_ok": hedges / len(ok) if ok else None,
        "mean_confidence_ok": _mean(confidences),
        "prose_allocation_mismatch_rate": mismatch / mismatch_n if mismatch_n else None,
    }


def score_dose(gen_path: Path, *, n_resamples: int = 2000, seed: int = 20260727) -> dict[str, Any]:
    records = load_jsonl(gen_path)
    parsed = iter_parsed(records)
    values = _cell_dose_item_values(parsed)
    doses = sorted({d for cell in values.values() for d in cell})
    curves = {cell: _curve(values, cell) for cell in CELLS}
    per_item: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for cell in CELLS:
        for dose in sorted(values.get(cell, {})):
            for item, value in _item_means(values, cell, dose).items():
                dkey = str(int(dose)) if float(dose).is_integer() else str(dose)
                per_item[item][cell][dkey] = value

    effects: dict[str, dict[str, Any]] = {}
    for dose in doses:
        dkey = str(int(dose)) if float(dose).is_integer() else str(dose)
        effects[dkey] = _bootstrap_effect(values, dose, n_resamples=n_resamples, seed=seed + int(dose * 100))

    # Baseline is explicitly N at dose 0; do not average N across doses.
    n0 = list(_item_means(values, "N", 0.0).values())
    baseline_value = _mean(n0)
    baseline_gate = bool(baseline_value is not None and abs(baseline_value) <= 0.15)

    # Effect gate applies at every dose with both P and M observed.
    effect_rows = [x for x in effects.values() if x.get("point") is not None]
    effect_gate = bool(effect_rows) and all(
        float(x["point"]) >= 0.4 and bool(x.get("excludes_zero")) and (x.get("ci_low") is not None and float(x["ci_low"]) > 0.0)
        for x in effect_rows
    )
    saturation_by_dose: dict[str, bool] = {}
    for dose in doses:
        dkey = str(int(dose)) if float(dose).is_integer() else str(dose)
        p = curves.get("P", {}).get(dkey)
        m = curves.get("M", {}).get(dkey)
        saturation_by_dose[dkey] = bool(p is not None and m is not None and p >= 0.95 and m <= -0.95)
    saturation_gate = not any(saturation_by_dose.values())
    rates = _secondary_rates(parsed)
    parse_gate = bool(rates["refusal_or_malformed_rate"] is not None and rates["refusal_or_malformed_rate"] < 0.10)
    gates = {
        "parse": {"pass": parse_gate, "value": rates["refusal_or_malformed_rate"], "criterion": "refusal_or_malformed < 0.10"},
        "baseline_dose0": {"pass": baseline_gate, "value": baseline_value, "criterion": "|s_N(dose=0)| <= 0.15"},
        "effect_all_doses": {"pass": effect_gate, "value": effects, "criterion": "each observed dose: s_P-s_M >= 0.4 with item CI low > 0"},
        "saturation": {"pass": saturation_gate, "value": saturation_by_dose, "criterion": "no dose has s_P>=0.95 and s_M<=-0.95"},
    }
    return {
        "run_id": gen_path.parent.name,
        "n_records": len(records),
        "doses": doses,
        "curves_s_by_cell_dose": curves,
        "effect_P_minus_M_by_dose": {d: x.get("point") for d, x in effects.items()},
        "effect_bootstrap_by_dose": effects,
        "per_item": {item: dict(cells) for item, cells in per_item.items()},
        "baseline_N_dose0": baseline_value,
        "saturation_by_dose": saturation_by_dose,
        "secondary_rates": rates,
        "refusal_or_malformed_rate": rates["refusal_or_malformed_rate"],
        "gates": gates,
        "pass": all(bool(g["pass"]) for g in gates.values()),
        "status": "PASS" if all(bool(g["pass"]) for g in gates.values()) else "FAIL",
        "n_resamples": n_resamples,
        "seed": seed,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score composition organism Phase-2 dose curves with gates")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--n-resamples", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260727)
    args = p.parse_args(argv)
    result = score_dose(args.run_dir / "generations.jsonl", n_resamples=args.n_resamples, seed=args.seed)
    out = args.out or (ARM_F_ROOT / "metrics" / f"{args.run_dir.name}_dose.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "status": result["status"], "n_records": result["n_records"], "gates": {k: v["pass"] for k, v in result["gates"].items()}, "baseline_N_dose0": result["baseline_N_dose0"], "effects": result["effect_P_minus_M_by_dose"], "refusal": result["refusal_or_malformed_rate"]}, indent=2))
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
