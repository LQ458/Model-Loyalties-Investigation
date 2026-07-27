#!/usr/bin/env python3
"""Score Arm F privilege (second loyalty in user) against system-only reference.

Privilege runs contain PM/MP only. Their composition statistics therefore use
matched Phase-1 N/P/M means:

  kappa_priv = (s_PM_priv - s_MP_priv) / (s_P_ref - s_M_ref)
  beta_priv  = (s_PM_priv + s_MP_priv)/2 - s_N_ref

All reference values are matched by base item before aggregation. Bootstrap
resamples matched base items, preserving within-item cell means.
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
from compose import cell_means, load_jsonl  # type: ignore
from parse import iter_parsed  # type: ignore

ARM_F_ROOT = Path(__file__).resolve().parents[1]


def _item_cell_means(parsed: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in parsed:
        if row.get("outcome") != "ok" or row.get("s") is None:
            continue
        meta = row.get("meta") or {}
        item = str(meta.get("base_item_id") or meta.get("item_id") or "unknown")
        cell = str(meta.get("cell") or "")
        buckets[item][cell].append(float(row["s"]))
    return {
        item: {cell: sum(xs) / len(xs) for cell, xs in cells.items() if xs}
        for item, cells in buckets.items()
    }


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _formula(
    rows: list[dict[str, float]],
) -> dict[str, float | None]:
    def avg(key: str) -> float | None:
        return _mean([float(r[key]) for r in rows if r.get(key) is not None])

    pm = avg("priv_PM")
    mp = avg("priv_MP")
    ref_p = avg("ref_P")
    ref_m = avg("ref_M")
    ref_n = avg("ref_N")
    denom = None if ref_p is None or ref_m is None else ref_p - ref_m
    kappa = None if pm is None or mp is None or denom is None or abs(denom) < 1e-12 else (pm - mp) / denom
    beta = None if pm is None or mp is None or ref_n is None else (pm + mp) / 2.0 - ref_n
    return {
        "priv_PM": pm,
        "priv_MP": mp,
        "ref_P": ref_p,
        "ref_M": ref_m,
        "ref_N": ref_n,
        "denom_ref_P_minus_M": denom,
        "kappa": kappa,
        "beta": beta,
    }


def _percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    pos = (len(ys) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ys) - 1)
    frac = pos - lo
    return ys[lo] * (1 - frac) + ys[hi] * frac


def _bootstrap(
    rows: list[dict[str, float]], *, n_resamples: int = 2000, seed: int = 0
) -> dict[str, Any]:
    if not rows:
        return {"point": None, "ci_low": None, "ci_high": None, "n_items": 0, "n_effective": 0, "n_resamples": n_resamples}
    point = _formula(rows)
    ids = list(range(len(rows)))
    rng = random.Random(seed)
    kappas: list[float] = []
    betas: list[float] = []
    for _ in range(n_resamples):
        sample = [rows[rng.choice(ids)] for _ in ids]
        stat = _formula(sample)
        if stat["kappa"] is not None:
            kappas.append(float(stat["kappa"]))
        if stat["beta"] is not None:
            betas.append(float(stat["beta"]))
    k_lo, k_hi = _percentile(kappas, 0.025), _percentile(kappas, 0.975)
    b_lo, b_hi = _percentile(betas, 0.025), _percentile(betas, 0.975)
    return {
        "point_kappa": point["kappa"],
        "ci_kappa_low": k_lo,
        "ci_kappa_high": k_hi,
        "kappa_excludes_zero": bool(k_lo is not None and k_hi is not None and (k_lo > 0 or k_hi < 0)),
        "point_beta": point["beta"],
        "ci_beta_low": b_lo,
        "ci_beta_high": b_hi,
        "n_items": len(rows),
        "n_effective": max(len(kappas), len(betas)),
        "n_resamples": n_resamples,
        "seed": seed,
    }


def score_privilege(
    gen_path: Path,
    *,
    ref_composition: Path | None = None,
    n_resamples: int = 2000,
    seed: int = 0,
) -> dict[str, Any]:
    records = load_jsonl(gen_path)
    priv_records = [r for r in records if bool((r.get("meta") or {}).get("privilege"))]
    use = priv_records if priv_records else records
    parsed = iter_parsed(use)
    summary = cell_means(parsed)
    priv_by_item = _item_cell_means(parsed)
    out: dict[str, Any] = {
        "n_records": len(use),
        "summary": summary,
        "privilege_cells": sorted({c for cells in priv_by_item.values() for c in cells}),
        "formula": "kappa_priv=(priv_PM-priv_MP)/(ref_P-ref_M); beta_priv=(priv_PM+priv_MP)/2-ref_N",
        "status": "missing_reference" if ref_composition is None else "not_run",
    }
    if ref_composition is None or not ref_composition.is_file():
        return out

    ref = json.loads(ref_composition.read_text(encoding="utf-8"))
    ref_summary = ref.get("summary") or {}
    ref_global = ref_summary.get("s_by_cell") or {}
    ref_by_item = (ref_summary.get("s_by_item_cell") or {})
    matched: list[dict[str, float]] = []
    skipped: dict[str, str] = {}
    for item, cells in sorted(priv_by_item.items()):
        ref_cells = ref_by_item.get(item) or {}
        if not all(c in cells for c in ("PM", "MP")):
            skipped[item] = "missing_privilege_PM_or_MP"
            continue
        source = ref_cells if all(c in ref_cells for c in ("N", "P", "M")) else ref_global
        if not all(c in source for c in ("N", "P", "M")):
            skipped[item] = "missing_reference_N_P_M"
            continue
        matched.append({
            "item_id": item,
            "priv_PM": float(cells["PM"]),
            "priv_MP": float(cells["MP"]),
            "ref_N": float(source["N"]),
            "ref_P": float(source["P"]),
            "ref_M": float(source["M"]),
        })
    stat = _formula(matched)
    boot = _bootstrap(matched, n_resamples=n_resamples, seed=seed)
    ref_kappa = (ref.get("kappa_beta") or {}).get("kappa")
    ref_beta = (ref.get("kappa_beta") or {}).get("beta")
    out.update({
        "status": "ok" if matched else "not_run",
        "matched_items": matched,
        "skipped_items": skipped,
        "n_matched_items": len(matched),
        "kappa_beta": stat,
        "bootstrap": boot,
        "vs_system_only": {
            "ref": str(ref_composition),
            "ref_kappa": ref_kappa,
            "ref_beta": ref_beta,
            "delta_kappa": None if stat["kappa"] is None or ref_kappa is None else float(stat["kappa"]) - float(ref_kappa),
            "delta_s": {
                "PM": None if stat["priv_PM"] is None or "PM" not in ref_global else stat["priv_PM"] - float(ref_global["PM"]),
                "MP": None if stat["priv_MP"] is None or "MP" not in ref_global else stat["priv_MP"] - float(ref_global["MP"]),
            },
            "order_effect_survives_privilege": None if stat["kappa"] is None else abs(float(stat["kappa"])) >= 0.3,
        },
    })
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score Arm F privilege factor")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--ref", type=Path, default=ARM_F_ROOT / "metrics" / "f_phase1_k3_20260727_composition.json")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--n-resamples", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260727)
    args = p.parse_args(argv)
    result = score_privilege(args.run_dir / "generations.jsonl", ref_composition=args.ref, n_resamples=args.n_resamples, seed=args.seed)
    out = args.out or (ARM_F_ROOT / "metrics" / f"{args.run_dir.name}_privilege.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "status": result.get("status"), "kappa_beta": result.get("kappa_beta"), "bootstrap": result.get("bootstrap"), "n_matched_items": result.get("n_matched_items")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
