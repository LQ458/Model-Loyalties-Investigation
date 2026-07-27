#!/usr/bin/env python3
"""Build toy §8.9 signature vectors from known-condition metrics JSON.

Offline only — no model calls. Given metrics for each known injected candidate
(or a demo payload), writes a signature dictionary that `match.py` can query.

Usage (from repo root):
  python stance/recovery/build_signatures.py --help
  python stance/recovery/build_signatures.py --demo
  python stance/recovery/build_signatures.py \\
      --metrics stance/recovery/demo/known_metrics.json \\
      --out stance/recovery/demo/signatures.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ARM = _HERE.parent
_REPO = _ARM.parent
for p in (_REPO, _ARM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

FEATURE_KEYS = (
    "crossover",
    "slope",
    "p_choose_a_dm2",
    "p_choose_a_d0",
    "p_choose_a_dp2",
    "commitment_rate",
    "direction_score",
    "alloc_a_mean",
)

CANDIDATE_IDS = ("favour_x", "disparage_y", "hedge_on_z")


def _as_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    return v


def _dose_map(block: dict[str, Any]) -> dict[float, float]:
    """Normalize dose→p maps from string/int keys."""
    out: dict[float, float] = {}
    for src in (
        block.get("p_choose_a_by_dose"),
        block.get("curve"),
        block.get("p_by_dose"),
        block if all(_as_float(k) is not None for k in block.keys()) else None,
    ):
        if not isinstance(src, dict):
            continue
        for k, v in src.items():
            dk = _as_float(k)
            pv = _as_float(v)
            if dk is not None and pv is not None:
                out[dk] = pv
    # nested fit style: doses + p_choose_a lists
    doses = block.get("doses")
    probs = block.get("p_choose_a")
    if isinstance(doses, list) and isinstance(probs, list) and len(doses) == len(probs):
        for d, p in zip(doses, probs):
            dk, pv = _as_float(d), _as_float(p)
            if dk is not None and pv is not None:
                out[dk] = pv
    return out


def _preferred_curve_key(block: dict[str, Any]) -> str | None:
    """Pick on-condition curve key from stance organism principal metric blobs."""
    curves = block.get("curve_choose_a")
    if not isinstance(curves, dict) or not curves:
        return None
    on_cond = str(block.get("on_condition") or "").strip()
    principal = str(block.get("principal_on") or "").strip()
    if on_cond and principal:
        key = f"{on_cond}_{principal}"
        if key in curves:
            return key
    for key in curves:
        if not str(key).upper().startswith("C0"):
            return str(key)
    return str(next(iter(curves.keys())))


def extract_vector(block: dict[str, Any]) -> dict[str, float | None]:
    """Pull a fixed feature vector from one condition's metrics blob.

    Accepts toy condition blocks and stance organism medium metric files
    (`curve_choose_a` + `library_displacement.fit_on`).
    """
    enriched = dict(block)
    if "p_choose_a_by_dose" not in enriched and isinstance(enriched.get("curve_choose_a"), dict):
        key = _preferred_curve_key(enriched)
        if key is not None:
            enriched["p_choose_a_by_dose"] = enriched["curve_choose_a"][key]

    lib = enriched.get("library_displacement") if isinstance(enriched.get("library_displacement"), dict) else {}
    fit_on = lib.get("fit_on") if isinstance(lib.get("fit_on"), dict) else {}
    fit = enriched.get("fit") if isinstance(enriched.get("fit"), dict) else fit_on

    dose = _dose_map(enriched)
    if not dose and isinstance(fit_on.get("doses"), list) and isinstance(fit_on.get("p_choose_a"), list):
        dose = _dose_map(fit_on)

    crossover = (
        _as_float(enriched.get("crossover"))
        or _as_float(enriched.get("crossover_on"))
        or _as_float(lib.get("crossover_on"))
        or _as_float(fit.get("crossover"))
    )
    slope = (
        _as_float(enriched.get("slope"))
        or _as_float(fit.get("slope"))
        or _as_float(fit.get("b"))
        or _as_float(fit_on.get("slope"))
    )
    return {
        "crossover": crossover,
        "slope": slope,
        "p_choose_a_dm2": dose.get(-2.0),
        "p_choose_a_d0": dose.get(0.0),
        "p_choose_a_dp2": dose.get(2.0),
        "commitment_rate": _as_float(enriched.get("commitment_rate"))
        or _as_float((enriched.get("commitment") or {}).get("p_central") if isinstance(enriched.get("commitment"), dict) else None),
        "direction_score": _as_float(enriched.get("direction_score"))
        or _as_float((enriched.get("direction") or {}).get("score") if isinstance(enriched.get("direction"), dict) else None),
        "alloc_a_mean": _as_float(enriched.get("alloc_a_mean"))
        or _as_float(enriched.get("mean_alloc_a"))
        or _as_float((enriched.get("allocation") or {}).get("mean_A") if isinstance(enriched.get("allocation"), dict) else None),
    }


def vector_list(features: dict[str, float | None], *, fill: float = 0.0) -> list[float]:
    return [float(features[k]) if features.get(k) is not None else fill for k in FEATURE_KEYS]


def load_conditions(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Accept several metrics JSON shapes and return candidate_id → block."""
    if "conditions" in metrics and isinstance(metrics["conditions"], dict):
        return {str(k): dict(v) for k, v in metrics["conditions"].items() if isinstance(v, dict)}
    if "signatures" in metrics and isinstance(metrics["signatures"], dict):
        # already built — re-extract from stored feature dicts if present
        out = {}
        for k, v in metrics["signatures"].items():
            if isinstance(v, dict) and "features" in v:
                out[str(k)] = dict(v["features"])
            elif isinstance(v, dict):
                out[str(k)] = dict(v)
        return out
    # stance organism curve_choose_a style: keys like C0_none / C1_A / favour_x
    if "curve_choose_a" in metrics and isinstance(metrics["curve_choose_a"], dict):
        out = {}
        for key, curve in metrics["curve_choose_a"].items():
            if not isinstance(curve, dict):
                continue
            block: dict[str, Any] = {"p_choose_a_by_dose": curve}
            # attach crossover if top-level matches a known pairing
            if key in {"C0_none", "C0"}:
                block["crossover"] = metrics.get("crossover_off")
            elif key.startswith("C1") or key.startswith("C2"):
                block["crossover"] = metrics.get("crossover_on")
            out[str(key)] = block
        return out
    # flat: each top-level key is a condition block
    skip = {
        "run_id",
        "n_records",
        "rows",
        "axis",
        "interpretation",
        "note",
        "meta",
        "feature_keys",
        "schema_version",
    }
    out = {}
    for k, v in metrics.items():
        if k in skip or not isinstance(v, dict):
            continue
        out[str(k)] = v
    return out


def build_signatures(
    metrics: dict[str, Any],
    *,
    candidate_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build signature dictionary from known-condition metrics."""
    conditions = load_conditions(metrics)
    if not conditions:
        raise ValueError("no condition blocks found in metrics JSON")

    # Optional remapping: metrics_key → candidate_id
    candidate_map = candidate_map or {}
    if "candidate_map" in metrics and isinstance(metrics["candidate_map"], dict):
        candidate_map = {**candidate_map, **{str(k): str(v) for k, v in metrics["candidate_map"].items()}}

    signatures: dict[str, Any] = {}
    for raw_id, block in conditions.items():
        cid = candidate_map.get(raw_id, raw_id)
        feats = extract_vector(block)
        signatures[cid] = {
            "candidate_id": cid,
            "source_key": raw_id,
            "features": feats,
            "vector": vector_list(feats),
            "prompt_path": f"candidates/{cid}.md" if cid in CANDIDATE_IDS else None,
        }

    return {
        "schema_version": 1,
        "feature_keys": list(FEATURE_KEYS),
        "n_signatures": len(signatures),
        "signatures": signatures,
        "source": metrics.get("run_id") or metrics.get("source") or None,
        "note": (
            "Toy §8.9 signature dictionary. Nearest-match is suggestive only — "
            "do not claim recovery from crossover displacement alone."
        ),
    }


def demo_metrics() -> dict[str, Any]:
    """Synthetic known-condition metrics for offline dry demo (no live runs)."""
    return {
        "source": "demo_synthetic",
        "run_id": "demo_known_conditions",
        "conditions": {
            "favour_x": {
                "crossover": -2.0,
                "slope": 0.15,
                "p_choose_a_by_dose": {"-2": 0.95, "0": 1.0, "2": 1.0},
                "commitment_rate": 0.1,
                "direction_score": 0.95,
                "alloc_a_mean": 78.0,
            },
            "disparage_y": {
                # disparaging B (Y) looks like elevating A on the same axis
                "crossover": -1.5,
                "slope": 0.25,
                "p_choose_a_by_dose": {"-2": 0.7, "0": 0.9, "2": 1.0},
                "commitment_rate": 0.15,
                "direction_score": 0.85,
                "alloc_a_mean": 70.0,
            },
            "hedge_on_z": {
                "crossover": 0.0,
                "slope": 0.05,
                "p_choose_a_by_dose": {"-2": 0.35, "0": 0.5, "2": 0.65},
                "commitment_rate": 0.7,
                "direction_score": 0.5,
                "alloc_a_mean": 50.0,
            },
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build toy §8.9 recovery signature vectors from known-condition metrics (offline)."
    )
    p.add_argument(
        "--metrics",
        type=Path,
        default=None,
        help="Metrics JSON with per-condition blocks (or curve_choose_a).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output signatures JSON (default: recovery/demo/signatures.json for --demo).",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Write synthetic demo signatures (no network / no live metrics required).",
    )
    p.add_argument(
        "--map",
        action="append",
        default=[],
        metavar="SRC=CANDIDATE",
        help="Remap a metrics key to a candidate_id (repeatable).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    candidate_map: dict[str, str] = {}
    for item in args.map:
        if "=" not in item:
            print(f"bad --map {item!r}; expected SRC=CANDIDATE", file=sys.stderr)
            return 2
        src, dst = item.split("=", 1)
        candidate_map[src.strip()] = dst.strip()

    if args.demo:
        metrics = demo_metrics()
        out = args.out or (_HERE / "demo" / "signatures.json")
        # also persist the demo metrics for inspectability
        demo_metrics_path = _HERE / "demo" / "known_metrics.json"
        demo_metrics_path.parent.mkdir(parents=True, exist_ok=True)
        demo_metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    else:
        if args.metrics is None:
            print("provide --metrics PATH or use --demo", file=sys.stderr)
            return 2
        metrics_path = args.metrics.resolve()
        if not metrics_path.is_file():
            print(f"missing metrics: {metrics_path}", file=sys.stderr)
            return 2
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        out = args.out or (_HERE / "signatures.json")

    try:
        payload = build_signatures(metrics, candidate_map=candidate_map or None)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out_path = out.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path} ({payload['n_signatures']} signatures)")
    for cid, sig in payload["signatures"].items():
        print(f"  {cid}: {sig['vector']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
