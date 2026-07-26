#!/usr/bin/env python3
"""Nearest-signature match for an unknown Arm E bias vector (§8.9 toy).

Offline only — no model calls. Loads a signature dictionary from
`build_signatures.py` and ranks candidate loyalty forms by distance.

Usage (from repo root):
  python armE_stance/recovery/match.py --help
  python armE_stance/recovery/match.py --demo
  python armE_stance/recovery/match.py \\
      --signatures armE_stance/recovery/demo/signatures.json \\
      --vector armE_stance/recovery/demo/unknown_vector.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent

FEATURE_KEYS_FALLBACK = (
    "crossover",
    "slope",
    "p_choose_a_dm2",
    "p_choose_a_d0",
    "p_choose_a_dp2",
    "commitment_rate",
    "direction_score",
    "alloc_a_mean",
)


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


def load_signatures(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "signatures" not in data or not isinstance(data["signatures"], dict):
        raise ValueError(f"no signatures dict in {path}")
    return data


def coerce_vector(
    raw: dict[str, Any] | list[Any],
    feature_keys: list[str],
) -> tuple[list[float], dict[str, float | None]]:
    """Accept either a feature dict or a raw list aligned to feature_keys."""
    if isinstance(raw, list):
        if len(raw) != len(feature_keys):
            raise ValueError(
                f"vector length {len(raw)} != n_features {len(feature_keys)}"
            )
        feats = {k: _as_float(v) for k, v in zip(feature_keys, raw)}
        vec = [float(feats[k]) if feats[k] is not None else 0.0 for k in feature_keys]
        return vec, feats

    # nested under features / vector / bias_vector
    block = raw
    for key in ("features", "bias_vector", "vector_features"):
        if isinstance(raw.get(key), dict):
            block = raw[key]
            break
    if isinstance(raw.get("vector"), list) and not any(k in block for k in feature_keys):
        return coerce_vector(raw["vector"], feature_keys)

    feats = {k: _as_float(block.get(k)) for k in feature_keys}
    vec = [float(feats[k]) if feats[k] is not None else 0.0 for k in feature_keys]
    return vec, feats


def euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na < 1e-12 or nb < 1e-12:
        return 1.0
    return 1.0 - (dot / (na * nb))


def rank_candidates(
    signatures: dict[str, Any],
    query: dict[str, Any] | list[Any],
    *,
    metric: str = "euclidean",
) -> dict[str, Any]:
    feature_keys = list(signatures.get("feature_keys") or FEATURE_KEYS_FALLBACK)
    q_vec, q_feats = coerce_vector(query, feature_keys)
    dist_fn = cosine_distance if metric == "cosine" else euclidean

    ranked: list[dict[str, Any]] = []
    for cid, sig in signatures["signatures"].items():
        if isinstance(sig.get("vector"), list):
            s_vec = [float(x) for x in sig["vector"]]
        else:
            s_vec, _ = coerce_vector(sig.get("features") or sig, feature_keys)
        if len(s_vec) != len(q_vec):
            raise ValueError(f"signature {cid} length mismatch")
        ranked.append(
            {
                "candidate_id": cid,
                "distance": dist_fn(q_vec, s_vec),
                "metric": metric,
                "prompt_path": sig.get("prompt_path"),
                "signature_vector": s_vec,
            }
        )
    ranked.sort(key=lambda r: r["distance"])
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i

    return {
        "schema_version": 1,
        "metric": metric,
        "feature_keys": feature_keys,
        "query_features": q_feats,
        "query_vector": q_vec,
        "n_candidates": len(ranked),
        "best_match": ranked[0]["candidate_id"] if ranked else None,
        "ranked": ranked,
        "caveat": (
            "Toy nearest-signature match only. Do not claim recovery from "
            "crossover displacement alone; identifiability is unproven at this scale."
        ),
    }


def demo_unknown_near_favour_x() -> dict[str, Any]:
    """Synthetic unknown bias vector close to favour_x (offline demo)."""
    return {
        "note": "demo unknown — slightly noisy favour_x-like vector",
        "features": {
            "crossover": -1.9,
            "slope": 0.18,
            "p_choose_a_dm2": 0.9,
            "p_choose_a_d0": 0.98,
            "p_choose_a_dp2": 1.0,
            "commitment_rate": 0.12,
            "direction_score": 0.92,
            "alloc_a_mean": 76.0,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Rank §8.9 candidate loyalty forms by nearest signature match (offline)."
    )
    p.add_argument(
        "--signatures",
        type=Path,
        default=None,
        help="signatures.json from build_signatures.py",
    )
    p.add_argument(
        "--vector",
        type=Path,
        default=None,
        help="Unknown bias-vector JSON (features dict or vector list).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write ranked match JSON.",
    )
    p.add_argument(
        "--metric",
        choices=["euclidean", "cosine"],
        default="euclidean",
        help="Distance metric (default: euclidean).",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Build demo signatures if needed and match a synthetic unknown (no network).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.demo:
        # Ensure demo signatures exist without requiring a prior manual step.
        from build_signatures import build_signatures, demo_metrics  # type: ignore

        demo_dir = _HERE / "demo"
        demo_dir.mkdir(parents=True, exist_ok=True)
        sig_path = args.signatures or (demo_dir / "signatures.json")
        if not Path(sig_path).is_file() or args.signatures is None:
            payload = build_signatures(demo_metrics())
            Path(sig_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            (demo_dir / "known_metrics.json").write_text(
                json.dumps(demo_metrics(), indent=2) + "\n", encoding="utf-8"
            )
        signatures = load_signatures(Path(sig_path))
        query = demo_unknown_near_favour_x()
        (demo_dir / "unknown_vector.json").write_text(
            json.dumps(query, indent=2) + "\n", encoding="utf-8"
        )
        out_default = demo_dir / "match_ranked.json"
    else:
        if args.signatures is None or args.vector is None:
            print("provide --signatures and --vector, or use --demo", file=sys.stderr)
            return 2
        sig_path = args.signatures.resolve()
        vec_path = args.vector.resolve()
        if not sig_path.is_file():
            print(f"missing signatures: {sig_path}", file=sys.stderr)
            return 2
        if not vec_path.is_file():
            print(f"missing vector: {vec_path}", file=sys.stderr)
            return 2
        signatures = load_signatures(sig_path)
        query = json.loads(vec_path.read_text(encoding="utf-8"))
        out_default = None

    try:
        result = rank_candidates(signatures, query, metric=args.metric)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out = args.out or out_default
    if out is not None:
        out_path = Path(out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out_path}")

    print(f"best_match: {result['best_match']}  (metric={result['metric']})")
    for row in result["ranked"]:
        print(
            f"  rank={row['rank']}  {row['candidate_id']:12s}  "
            f"distance={row['distance']:.4f}"
        )
    print(result["caveat"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
