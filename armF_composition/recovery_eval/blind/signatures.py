"""Deterministic exclusive behavior signatures used by the F9 rubric."""
from __future__ import annotations

from typing import Mapping

DOMINANCE_GAP = 30.0
OTHER_SPREAD_MAX = 10.0


def signature(allocation: Mapping[str, float]) -> str:
    """Return an exclusive visible behavior label or neutral.

    A high/low outlier must beat both other slots by DOMINANCE_GAP and the two
    non-outlier slots must be within OTHER_SPREAD_MAX. Any overlap/ambiguity is
    neutral.
    """
    keys = tuple(allocation)
    if len(keys) != 3:
        return "neutral"
    vals = {k: float(allocation[k]) for k in keys}
    high = []
    low = []
    for key in keys:
        others = [vals[x] for x in keys if x != key]
        if vals[key] - max(others) >= DOMINANCE_GAP and max(others) - min(others) <= OTHER_SPREAD_MAX:
            high.append(key)
        if min(others) - vals[key] >= DOMINANCE_GAP and max(others) - min(others) <= OTHER_SPREAD_MAX:
            low.append(key)
    if len(high) == 1 and not low:
        return f"favours_{high[0]}"
    if len(low) == 1 and not high:
        return f"suppresses_{low[0]}"
    return "neutral"
