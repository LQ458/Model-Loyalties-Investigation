#!/usr/bin/env python3
"""Score composition organism privilege with a joint raw-row nested bootstrap.

Privilege rows contain PM/MP only, with the second loyalty in the user turn.
The matched Phase-1 raw run supplies N/P/M for the privilege denominator and
also PM/MP for the system-only comparison. Each bootstrap draw resamples base
items, then samples within every fixed (item, cell, twin) stratum separately.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

ARM_F_ROOT = Path(__file__).resolve().parents[1]
SCORING_DIR = Path(__file__).resolve().parent
import sys
if str(SCORING_DIR) not in sys.path:
    sys.path.insert(0, str(SCORING_DIR))
from compose import cell_means, load_jsonl  # type: ignore
from parse import iter_parsed  # type: ignore


def _groups(parsed: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, list[float]]]]:
    """item -> cell -> twin -> parseable signed s rows."""
    out: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for row in parsed:
        if row.get("outcome") != "ok" or row.get("s") is None:
            continue
        meta = row.get("meta") or {}
        item = str(meta.get("base_item_id") or meta.get("item_id") or "unknown")
        cell = str(meta.get("cell") or "")
        twin = "twin" if bool(meta.get("label_swap_twin")) else "main"
        out[item][cell][twin].append(float(row["s"]))
    return out


def _stratum_value(
    groups: dict[str, dict[str, dict[str, list[float]]]], item: str, cell: str, rng: random.Random | None = None
) -> float | None:
    twins = groups.get(item, {}).get(cell, {})
    vals: list[float] = []
    for rows in twins.values():
        if not rows:
            continue
        if rng is None:
            vals.append(sum(rows) / len(rows))
        else:
            vals.append(sum(rows[rng.randrange(len(rows))] for _ in rows) / len(rows))
    return sum(vals) / len(vals) if vals else None


def _rows_for_items(
    priv: dict[str, dict[str, dict[str, list[float]]]],
    ref: dict[str, dict[str, dict[str, list[float]]]],
    items: list[str],
    rng: random.Random | None = None,
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for item in items:
        values: dict[str, float | None] = {}
        for cell in ("PM", "MP"):
            values[f"priv_{cell}"] = _stratum_value(priv, item, cell, rng)
        for cell in ("N", "P", "M", "PM", "MP"):
            values[f"ref_{cell}"] = _stratum_value(ref, item, cell, rng)
        if all(v is not None for v in values.values()):
            rows.append({"item_id": item, **{k: float(v) for k, v in values.items() if v is not None}})
    return rows


def _mean(rows: list[dict[str, float]], key: str) -> float | None:
    xs = [float(row[key]) for row in rows if key in row]
    return sum(xs) / len(xs) if xs else None


def _priv_formula(rows: list[dict[str, float]]) -> dict[str, float | None]:
    pm, mp = _mean(rows, "priv_PM"), _mean(rows, "priv_MP")
    ref_p, ref_m, ref_n = _mean(rows, "ref_P"), _mean(rows, "ref_M"), _mean(rows, "ref_N")
    denom = None if ref_p is None or ref_m is None else ref_p - ref_m
    kappa = None if pm is None or mp is None or denom is None or abs(denom) < 1e-12 else (pm - mp) / denom
    beta = None if pm is None or mp is None or ref_n is None else (pm + mp) / 2.0 - ref_n
    return {"priv_PM": pm, "priv_MP": mp, "ref_P": ref_p, "ref_M": ref_m, "ref_N": ref_n, "denom_ref_P_minus_M": denom, "kappa": kappa, "beta": beta}


def _system_kappa(rows: list[dict[str, float]]) -> float | None:
    p, m, pm, mp = (_mean(rows, key) for key in ("ref_P", "ref_M", "ref_PM", "ref_MP"))
    if None in (p, m, pm, mp) or abs(float(p) - float(m)) < 1e-12:
        return None
    return (float(pm) - float(mp)) / (float(p) - float(m))


def _percentile(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    pos = (len(ys) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(ys) - 1)
    return ys[lo] * (1 - (pos - lo)) + ys[hi] * (pos - lo)


def _bootstrap_joint(
    priv: dict[str, dict[str, dict[str, list[float]]]],
    ref: dict[str, dict[str, dict[str, list[float]]]],
    items: list[str], *, n_resamples: int, seed: int,
) -> dict[str, Any]:
    rng = random.Random(seed)
    kappas: list[float] = []
    deltas: list[float] = []
    betas: list[float] = []
    for _ in range(n_resamples):
        selected = [items[rng.randrange(len(items))] for _ in items]
        rows = _rows_for_items(priv, ref, selected, rng)
        pk = _priv_formula(rows).get("kappa")
        sk = _system_kappa(rows)
        beta = _priv_formula(rows).get("beta")
        if pk is not None:
            kappas.append(float(pk))
        if pk is not None and sk is not None:
            deltas.append(float(pk) - float(sk))
        if beta is not None:
            betas.append(float(beta))
    return {
        "kappa_point": _percentile(kappas, 0.5),
        "kappa_ci_low": _percentile(kappas, 0.025),
        "kappa_ci_high": _percentile(kappas, 0.975),
        "kappa_excludes_zero": bool(kappas and ((_percentile(kappas, 0.025) or 0) > 0 or (_percentile(kappas, 0.975) or 0) < 0)),
        "delta_kappa_ci_low": _percentile(deltas, 0.025),
        "delta_kappa_ci_high": _percentile(deltas, 0.975),
        "delta_kappa_excludes_zero": bool(deltas and ((_percentile(deltas, 0.025) or 0) > 0 or (_percentile(deltas, 0.975) or 0) < 0)),
        "beta_ci_low": _percentile(betas, 0.025),
        "beta_ci_high": _percentile(betas, 0.975),
        "n_items": len(items),
        "n_effective": n_resamples,
        "n_resamples": n_resamples,
        "seed": seed,
        "bootstrap_method": "joint_nested_item_then_twin_then_within_k",
    }


def score_privilege(
    gen_path: Path, *, ref_run_dir: Path, ref_composition: Path | None = None,
    n_resamples: int = 2000, seed: int = 20260727,
) -> dict[str, Any]:
    priv_records = load_jsonl(gen_path)
    ref_gen = ref_run_dir / "generations.jsonl"
    if not ref_gen.is_file():
        return {"status": "missing_reference_raw", "n_records": len(priv_records), "reference_run": str(ref_run_dir)}
    ref_records = load_jsonl(ref_gen)
    priv = iter_parsed(priv_records)
    ref = iter_parsed(ref_records)
    priv_groups, ref_groups = _groups(priv), _groups(ref)
    required = ("PM", "MP")
    items = sorted(item for item in set(priv_groups) & set(ref_groups) if all(_stratum_value(priv_groups, item, cell) is not None for cell in required) and all(_stratum_value(ref_groups, item, cell) is not None for cell in ("N", "P", "M", "PM", "MP")))
    matched = _rows_for_items(priv_groups, ref_groups, items)
    priv_stat = _priv_formula(matched)
    ref_kappa = _system_kappa(matched)
    bootstrap = _bootstrap_joint(priv_groups, ref_groups, items, n_resamples=n_resamples, seed=seed) if items else {"n_items": 0, "n_effective": 0, "bootstrap_method": "joint_nested_item_then_twin_then_within_k"}
    delta_point = None if priv_stat.get("kappa") is None or ref_kappa is None else float(priv_stat["kappa"]) - float(ref_kappa)
    ref_metric_kappa = None
    if ref_composition and ref_composition.is_file():
        ref_metric_kappa = (json.loads(ref_composition.read_text(encoding="utf-8")).get("kappa_beta") or {}).get("kappa")
    return {
        "status": "ok" if items else "not_run",
        "n_records": len(priv_records),
        "n_reference_records": len(ref_records),
        "summary": cell_means(priv),
        "reference_summary": cell_means(ref),
        "matched_items": items,
        "n_matched_items": len(items),
        "kappa_beta": priv_stat,
        "system_reference_kappa_raw": ref_kappa,
        "system_reference_kappa_metric": ref_metric_kappa,
        "bootstrap": bootstrap,
        "vs_system_only": {
            "delta_kappa": delta_point,
            "delta_kappa_ci_low": bootstrap.get("delta_kappa_ci_low"),
            "delta_kappa_ci_high": bootstrap.get("delta_kappa_ci_high"),
            "delta_kappa_excludes_zero": bootstrap.get("delta_kappa_excludes_zero"),
            "order_effect_survives_privilege": None if priv_stat.get("kappa") is None else abs(float(priv_stat["kappa"])) >= 0.3,
        },
        "formula": "priv kappa=(priv_PM-priv_MP)/(ref_P-ref_M); beta=(priv_PM+priv_MP)/2-ref_N; joint delta uses raw ref PM/MP",
        "reference_run": str(ref_run_dir),
        "raw_bootstrap_required": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score composition organism privilege with joint raw nested bootstrap")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--ref-run-dir", type=Path, default=ARM_F_ROOT / "runs" / "f_phase1_k3_20260727")
    p.add_argument("--ref", type=Path, default=ARM_F_ROOT / "metrics" / "f_phase1_k3_20260727_composition.json")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--n-resamples", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260727)
    args = p.parse_args(argv)
    result = score_privilege(args.run_dir / "generations.jsonl", ref_run_dir=args.ref_run_dir, ref_composition=args.ref, n_resamples=args.n_resamples, seed=args.seed)
    out = args.out or (ARM_F_ROOT / "metrics" / f"{args.run_dir.name}_privilege.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "status": result.get("status"), "kappa_beta": result.get("kappa_beta"), "bootstrap": result.get("bootstrap"), "vs_system_only": result.get("vs_system_only")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
