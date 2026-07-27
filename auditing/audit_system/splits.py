"""Deterministic leave-one-group-out and control-order helpers."""

from __future__ import annotations

import hashlib
import random
from collections import defaultdict
from typing import Any, Iterable


def leave_one_group_out(
    records: Iterable[dict[str, Any]],
    *,
    group_field: str,
    id_field: str = "id",
) -> list[dict[str, Any]]:
    rows = list(records)
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        group = str(row.get(group_field, "")).strip()
        record_id = str(row.get(id_field, "")).strip()
        if not group or not record_id:
            raise ValueError(
                f"leave-one-group-out requires {group_field!r} and {id_field!r}"
            )
        grouped[group].append(record_id)
    if len(grouped) < 2:
        raise ValueError(
            f"leave-one-{group_field}-out requires at least two distinct groups"
        )
    all_ids = {record_id for values in grouped.values() for record_id in values}
    return [
        {
            "held_out_group": group,
            "train_ids": sorted(all_ids - set(test_ids)),
            "test_ids": sorted(test_ids),
        }
        for group, test_ids in sorted(grouped.items())
    ]


def randomized_control_order(
    item_ids: Iterable[str],
    *,
    randomization_key: str,
) -> list[str]:
    ids = list(item_ids)
    if len(ids) != len(set(ids)):
        raise ValueError("control-order item IDs must be unique")
    if not randomization_key:
        raise ValueError("randomization_key is required")
    seed = int.from_bytes(
        hashlib.sha256(randomization_key.encode("utf-8")).digest()[:8], "big"
    )
    random.Random(seed).shuffle(ids)
    return ids
