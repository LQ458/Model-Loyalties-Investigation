"""Item-clustered bootstrap confidence intervals for stance organism estimands."""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Any, Callable, Iterable


def cluster_by_item(rows: Iterable[dict[str, Any]], key: str = "item_id") -> dict[str, list[dict[str, Any]]]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        iid = str(r.get(key) or (r.get("meta") or {}).get(key) or "unknown")
        clusters[iid].append(r)
    return dict(clusters)


def bootstrap_ci(
    rows: list[dict[str, Any]],
    statistic: Callable[[list[dict[str, Any]]], float | None],
    *,
    n_resamples: int = 2000,
    ci_level: float = 0.95,
    seed: int = 0,
    cluster_key: str = "item_id",
) -> dict[str, Any]:
    """Resample items with replacement; compute percentile CI for statistic."""
    clusters = cluster_by_item(rows, key=cluster_key)
    ids = list(clusters.keys())
    point = statistic(rows)
    if not ids:
        return {
            "point": point,
            "ci_low": None,
            "ci_high": None,
            "n_resamples": n_resamples,
            "n_items": 0,
            "distribution": [],
        }

    rng = random.Random(seed)
    dist: list[float] = []
    for _ in range(n_resamples):
        sampled_ids = [ids[rng.randrange(len(ids))] for _ in range(len(ids))]
        sample: list[dict[str, Any]] = []
        for iid in sampled_ids:
            sample.extend(clusters[iid])
        val = statistic(sample)
        if val is not None:
            dist.append(float(val))

    if not dist:
        return {
            "point": point,
            "ci_low": None,
            "ci_high": None,
            "n_resamples": n_resamples,
            "n_items": len(ids),
            "distribution": [],
        }

    dist_sorted = sorted(dist)
    alpha = 1.0 - ci_level
    lo_i = int(alpha / 2 * (len(dist_sorted) - 1))
    hi_i = int((1 - alpha / 2) * (len(dist_sorted) - 1))
    return {
        "point": point,
        "ci_low": dist_sorted[lo_i],
        "ci_high": dist_sorted[hi_i],
        "n_resamples": n_resamples,
        "n_effective": len(dist),
        "n_items": len(ids),
        "ci_level": ci_level,
        "mean": sum(dist) / len(dist),
        "distribution": dist_sorted,  # caller may drop for compact JSON
    }


def mean_choose_a_stat(rows: list[dict[str, Any]]) -> float | None:
    xs = [float(r["choose_a"]) for r in rows if r.get("choose_a") is not None]
    return sum(xs) / len(xs) if xs else None


def displacement_stat_factory(
    rows_on: list[dict[str, Any]],
    rows_off: list[dict[str, Any]],
):
    """Return a statistic over paired bootstrap of shared item ids.

    For simplicity, statistic expects a combined list tagged with group.
    Prefer bootstrap_displacement below.
    """
    raise NotImplementedError


def bootstrap_displacement(
    rows_on: list[dict[str, Any]],
    rows_off: list[dict[str, Any]],
    *,
    n_resamples: int = 2000,
    ci_level: float = 0.95,
    seed: int = 0,
) -> dict[str, Any]:
    """Item-clustered bootstrap for crossover displacement (on - off)."""
    from .curves import crossover_displacement

    def _point(on: list[dict[str, Any]], off: list[dict[str, Any]]) -> float | None:
        return crossover_displacement(on, off).get("displacement")

    point = _point(rows_on, rows_off)
    on_c = cluster_by_item(rows_on)
    off_c = cluster_by_item(rows_off)
    ids = sorted(set(on_c) & set(off_c)) or sorted(set(on_c) | set(off_c))
    if not ids:
        return {"point": point, "ci_low": None, "ci_high": None, "n_items": 0}

    rng = random.Random(seed)
    dist: list[float] = []
    for _ in range(n_resamples):
        sampled = [ids[rng.randrange(len(ids))] for _ in range(len(ids))]
        on_s: list[dict[str, Any]] = []
        off_s: list[dict[str, Any]] = []
        for iid in sampled:
            on_s.extend(on_c.get(iid, []))
            off_s.extend(off_c.get(iid, []))
        val = _point(on_s, off_s)
        if val is not None:
            dist.append(float(val))

    if not dist:
        return {
            "point": point,
            "ci_low": None,
            "ci_high": None,
            "n_items": len(ids),
            "n_resamples": n_resamples,
        }
    dist_sorted = sorted(dist)
    alpha = 1.0 - ci_level
    lo_i = int(alpha / 2 * (len(dist_sorted) - 1))
    hi_i = int((1 - alpha / 2) * (len(dist_sorted) - 1))
    return {
        "point": point,
        "ci_low": dist_sorted[lo_i],
        "ci_high": dist_sorted[hi_i],
        "n_items": len(ids),
        "n_resamples": n_resamples,
        "n_effective": len(dist),
        "ci_level": ci_level,
        "excludes_zero": (dist_sorted[lo_i] > 0 and dist_sorted[hi_i] > 0)
        or (dist_sorted[lo_i] < 0 and dist_sorted[hi_i] < 0),
    }
