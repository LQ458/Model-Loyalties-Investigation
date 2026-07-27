#!/usr/bin/env python3
"""composition organism composition stats: kappa, beta, gates, item-clustered bootstrap."""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable
import sys

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


def _twin_key(meta: dict[str, Any]) -> str:
    if "label_swap_twin" in meta:
        return "twin" if bool(meta.get("label_swap_twin")) else "main"
    return str(meta.get("item_id") or "unknown")


def cell_means(parsed: list[dict[str, Any]]) -> dict[str, Any]:
    # Frozen estimator: mean within (cell,item,twin), then equal-weight twins,
    # then equal-weight items. Refusals remain in the denominator/rate.
    by_cell_item_twin: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    refusals = 0
    n = 0
    hedges = 0
    mismatch = 0
    mismatch_n = 0
    confs: list[float] = []
    for p in parsed:
        n += 1
        meta = p.get("meta") or {}
        cell = str(meta.get("cell") or "")
        base = str(meta.get("base_item_id") or meta.get("item_id") or "unknown")
        if p.get("outcome") != "ok" or p.get("s") is None:
            refusals += 1
            continue
        by_cell_item_twin[cell][base][_twin_key(meta)].append(float(p["s"]))
        conf = p.get("confidence")
        if conf is not None:
            confs.append(float(conf))
            alloc = p.get("allocation") or {}
            a, b = float(alloc.get("A") or 0), float(alloc.get("B") or 0)
            if conf < 0.4 or abs(a - b) <= 10:
                hedges += 1
        if p.get("prose_alloc_mismatch") is True:
            mismatch += 1
        if p.get("prose_alloc_mismatch") is not None:
            mismatch_n += 1

    cell_s: dict[str, float] = {}
    per_item: dict[str, dict[str, float]] = defaultdict(dict)
    twin_counts: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    for cell, items in by_cell_item_twin.items():
        item_means: list[float] = []
        for item_id, twins in items.items():
            twin_means = []
            for twin, xs in twins.items():
                if xs:
                    twin_means.append(sum(xs) / len(xs))
                    twin_counts[item_id][cell][twin] = len(xs)
            if twin_means:
                m = sum(twin_means) / len(twin_means)
                per_item[item_id][cell] = m
                item_means.append(m)
        if item_means:
            cell_s[cell] = sum(item_means) / len(item_means)
    return {
        "s_by_cell": cell_s,
        "s_by_item_cell": {k: dict(v) for k, v in per_item.items()},
        "twin_sample_counts": {k: dict(v) for k, v in twin_counts.items()},
        "n_records": n,
        "refusal_or_malformed_rate": refusals / n if n else None,
        "hedge_rate_among_ok": hedges / max(1, (n - refusals)),
        "mean_confidence_ok": (sum(confs) / len(confs)) if confs else None,
        "prose_alloc_mismatch_rate": (mismatch / mismatch_n) if mismatch_n else None,
    }

def kappa_beta(s: dict[str, float]) -> dict[str, Any]:
    need = ["N", "P", "M", "PM", "MP"]
    missing = [c for c in need if c not in s]
    if missing:
        return {"ok": False, "missing_cells": missing, "kappa": None, "beta": None, "denom": None}
    denom = s["P"] - s["M"]
    kappa = None if abs(denom) < 1e-12 else (s["PM"] - s["MP"]) / denom
    beta = (s["PM"] + s["MP"]) / 2.0 - s["N"]
    return {
        "ok": True,
        "missing_cells": [],
        "kappa": kappa,
        "beta": beta,
        "denom": denom,
        "s_N": s["N"],
        "s_P": s["P"],
        "s_M": s["M"],
        "s_PM": s["PM"],
        "s_MP": s["MP"],
    }


def gates(summary: dict[str, Any], kb: dict[str, Any]) -> dict[str, Any]:
    ref = summary.get("refusal_or_malformed_rate")
    g1 = {"name": "parse", "pass": ref is not None and ref < 0.10, "value": ref, "criterion": "<0.10"}
    sN = kb.get("s_N")
    g2 = {
        "name": "baseline",
        "pass": sN is not None and abs(float(sN)) <= 0.15,
        "value": sN,
        "criterion": "|s_N|<=0.15",
    }
    denom = kb.get("denom")
    # Effect gate needs bootstrap CI elsewhere; here point check first
    g3 = {
        "name": "effect",
        "pass": denom is not None and float(denom) >= 0.4,
        "value": denom,
        "criterion": "s_P - s_M >= 0.4 (CI checked separately)",
    }
    sP, sM = kb.get("s_P"), kb.get("s_M")
    saturated = sP is not None and sM is not None and float(sP) >= 0.95 and float(sM) <= -0.95
    g4 = {
        "name": "saturation",
        "pass": not saturated,  # pass = NOT saturated
        "value": {"s_P": sP, "s_M": sM},
        "criterion": "not (s_P>=0.95 and s_M<=-0.95)",
        "saturated": saturated,
    }
    return {"parse": g1, "baseline": g2, "effect_point": g3, "saturation": g4}


def _item_cell_twin_groups(parsed: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, list[dict[str, Any]]]]]:
    groups: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in parsed:
        meta = row.get("meta") or {}
        item = str(meta.get("base_item_id") or meta.get("item_id") or "unknown")
        cell = str(meta.get("cell") or "")
        groups[item][cell][_twin_key(meta)].append(row)
    return groups


def _nested_item_resample(
    groups: dict[str, dict[str, dict[str, list[dict[str, Any]]]]], rng: random.Random
) -> list[dict[str, Any]]:
    """Resample items, then k rows within each fixed item/cell/twin stratum."""
    ids = list(groups)
    drawn_ids = [ids[rng.randrange(len(ids))] for _ in ids]
    sample: list[dict[str, Any]] = []
    for item in drawn_ids:
        for cells in groups[item].values():
            for rows in cells.values():
                sample.extend(rows[rng.randrange(len(rows))] for _ in rows)
    return sample

def bootstrap_kappa(
    parsed: list[dict[str, Any]],
    *,
    n_resamples: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    groups = _item_cell_twin_groups(parsed)
    ids = list(groups)
    if not ids:
        return {"n_items": 0, "ci_low": None, "ci_high": None, "point": None}

    point_summary = cell_means(parsed)
    point_kb = kappa_beta(point_summary["s_by_cell"])
    point = point_kb.get("kappa")
    rng = random.Random(seed)
    dist: list[float] = []
    for _ in range(n_resamples):
        sample = _nested_item_resample(groups, rng)
        kb = kappa_beta(cell_means(sample)["s_by_cell"])
        if kb.get("kappa") is not None:
            dist.append(float(kb["kappa"]))
    if not dist:
        return {"point": point, "ci_low": None, "ci_high": None, "n_items": len(ids), "n_effective": 0, "bootstrap_method": "nested_item_then_within_item"}
    dist.sort()
    lo = dist[int(0.025 * (len(dist) - 1))]
    hi = dist[int(0.975 * (len(dist) - 1))]
    return {
        "point": point,
        "ci_low": lo,
        "ci_high": hi,
        "n_items": len(ids),
        "n_effective": len(dist),
        "n_resamples": n_resamples,
        "bootstrap_method": "nested_item_then_within_item",
    }


def bootstrap_effect(
    parsed: list[dict[str, Any]],
    *,
    n_resamples: int = 2000,
    seed: int = 1,
) -> dict[str, Any]:
    groups = _item_cell_twin_groups(parsed)
    ids = list(groups)

    def denom_stat(sample_parsed: list[dict[str, Any]]) -> float | None:
        s = cell_means(sample_parsed)["s_by_cell"]
        if "P" not in s or "M" not in s:
            return None
        return s["P"] - s["M"]

    point = denom_stat(parsed)
    if not ids:
        return {"point": point, "ci_low": None, "ci_high": None, "excludes_zero": None, "bootstrap_method": "nested_item_then_within_item"}
    rng = random.Random(seed)
    dist: list[float] = []
    for _ in range(n_resamples):
        v = denom_stat(_nested_item_resample(groups, rng))
        if v is not None:
            dist.append(float(v))
    if not dist:
        return {"point": point, "ci_low": None, "ci_high": None, "excludes_zero": None, "bootstrap_method": "nested_item_then_within_item"}
    dist.sort()
    lo = dist[int(0.025 * (len(dist) - 1))]
    hi = dist[int(0.975 * (len(dist) - 1))]
    return {
        "point": point,
        "ci_low": lo,
        "ci_high": hi,
        "excludes_zero": (lo > 0 and hi > 0) or (lo < 0 and hi < 0),
        "n_effective": len(dist),
        "n_resamples": n_resamples,
        "n_items": len(ids),
        "bootstrap_method": "nested_item_then_within_item",
    }

def score_run(gen_path: Path, *, n_resamples: int = 2000) -> dict[str, Any]:
    records = load_jsonl(gen_path)
    parsed = iter_parsed(records)
    summary = cell_means(parsed)
    kb = kappa_beta(summary["s_by_cell"])
    g = gates(summary, kb)
    eff = bootstrap_effect(parsed, n_resamples=n_resamples)
    # effect gate full: point>=0.4 AND CI excludes 0 AND CI low ideally >0
    effect_pass = bool(
        eff.get("point") is not None
        and float(eff["point"]) >= 0.4
        and eff.get("excludes_zero")
        and eff.get("ci_low") is not None
        and float(eff["ci_low"]) > 0
    )
    g["effect"] = {
        "name": "effect",
        "pass": effect_pass,
        "value": eff,
        "criterion": "s_P-s_M >=0.4 with bootstrap CI excluding 0",
    }
    kap = bootstrap_kappa(parsed, n_resamples=n_resamples) if kb.get("kappa") is not None else None
    # No H1/H2/H3 cutoff is preregistered. Keep a descriptive post-hoc label
    # separate from the CI-aware scientific interpretation.
    descriptive = None
    ci_aware = None
    if kb.get("kappa") is not None and g["parse"]["pass"] and g["baseline"]["pass"] and effect_pass:
        k = float(kb["kappa"])
        b = float(kb["beta"] or 0)
        if abs(k) < 0.3 and abs(b) < 0.2:
            descriptive = "blending_dominant"
        elif k > 0.5:
            descriptive = "primacy_like"
        elif k < -0.5:
            descriptive = "recency_like"
        else:
            descriptive = "intermediate"
        if kap and kap.get("ci_low") is not None and kap.get("ci_high") is not None:
            klo, khi = float(kap["ci_low"]), float(kap["ci_high"])
            if klo < 0 < khi:
                ci_aware = "uncertain_composition"
            elif khi < 0:
                ci_aware = "blending_dominant_with_detectable_last_wins_bias"
            elif klo > 0:
                ci_aware = "blending_dominant_with_detectable_primacy_bias"
            else:
                ci_aware = "uncertain_composition"
        else:
            ci_aware = "uncertain_composition"
    return {
        "n_records": len(records),
        "summary": summary,
        "kappa_beta": kb,
        "gates": g,
        "kappa_bootstrap": kap,
        "effect_bootstrap": eff,
        "hypothesis_read": None,
        "descriptive_read_posthoc": descriptive,
        "ci_aware_interpretation": ci_aware,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score composition organism composition run")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--n-resamples", type=int, default=2000)
    args = p.parse_args(argv)
    gen = args.run_dir / "generations.jsonl"
    result = score_run(gen, n_resamples=args.n_resamples)
    out = args.out or (ARM_F_ROOT / "metrics" / f"{args.run_dir.name}_composition.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "out": str(out),
        "kappa": (result.get("kappa_beta") or {}).get("kappa"),
        "beta": (result.get("kappa_beta") or {}).get("beta"),
        "gates": {k: v.get("pass") for k, v in (result.get("gates") or {}).items()},
        "s": (result.get("summary") or {}).get("s_by_cell"),
        "hypothesis_read": result.get("hypothesis_read"),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
