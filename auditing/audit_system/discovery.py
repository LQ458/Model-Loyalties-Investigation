"""Discovery-to-confirmation hypothesis freezing for blind L1/L2 audits."""

from __future__ import annotations

from typing import Any, Iterable

from .integrity import canonical_json, sha256_bytes
from .models import Seed


HYPOTHESIS_FIELDS = (
    "suspected_principal",
    "suspected_activation_condition",
    "suspected_action_pattern",
)


def freeze_hypothesis(
    judge_result: dict[str, Any],
    *,
    seed: Seed,
) -> dict[str, Any]:
    if seed.phase != "discovery":
        raise ValueError("only discovery seeds can freeze a hypothesis")
    hypothesis = {
        field: (
            str(judge_result.get(field)).strip()
            if judge_result.get(field) is not None
            else None
        )
        for field in HYPOTHESIS_FIELDS
    }
    payload = {
        "schema_version": 1,
        "discovery_seed_id": seed.id,
        "discovery_split": seed.split,
        "pair_id": seed.pair_id or seed.id,
        "hypothesis": hypothesis,
    }
    payload["hypothesis_sha256"] = sha256_bytes(canonical_json(payload))
    return payload


def bind_confirmation(
    frozen: dict[str, Any],
    *,
    seed: Seed,
) -> dict[str, Any]:
    if seed.phase != "confirmation":
        raise ValueError("confirmation binding requires a confirmation seed")
    if not seed.hypothesis_ref:
        raise ValueError("confirmation seed requires hypothesis_ref")
    if seed.hypothesis_ref != frozen.get("discovery_seed_id"):
        raise ValueError("confirmation hypothesis_ref does not match frozen discovery")
    if seed.split == frozen.get("discovery_split"):
        raise ValueError("confirmation must use an independent seed split")
    return {
        "schema_version": 1,
        "hypothesis_ref": seed.hypothesis_ref,
        "frozen_hypothesis_sha256": frozen["hypothesis_sha256"],
        "discovery_split": frozen["discovery_split"],
        "confirmation_split": seed.split,
        "hypothesis": frozen["hypothesis"],
    }


def validate_discovery_confirmation_seeds(
    seeds: Iterable[Seed],
    *,
    levels: Iterable[int],
    techniques: Iterable[str],
) -> None:
    from .techniques import canonical_technique

    selected_levels = set(levels) & {1, 2}
    selected_techniques = {canonical_technique(item) for item in techniques}
    relevant = [
        seed
        for seed in seeds
        if seed.level in selected_levels
        and canonical_technique(seed.technique) in selected_techniques
    ]
    discoveries = {seed.id: seed for seed in relevant if seed.phase == "discovery"}
    confirmations = [seed for seed in relevant if seed.phase == "confirmation"]
    if selected_levels and (not discoveries or not confirmations):
        raise ValueError(
            "final L1/L2 evidence requires discovery and confirmation seeds"
        )
    covered: set[tuple[int, str]] = set()
    for seed in confirmations:
        discovery = discoveries.get(seed.hypothesis_ref)
        if discovery is None:
            raise ValueError(
                f"confirmation seed {seed.id} has unknown hypothesis_ref "
                f"{seed.hypothesis_ref!r}"
            )
        if discovery.level != seed.level:
            raise ValueError("discovery and confirmation levels must match")
        if canonical_technique(discovery.technique) != canonical_technique(
            seed.technique
        ):
            raise ValueError("discovery and confirmation techniques must match")
        if discovery.split == seed.split:
            raise ValueError("confirmation split must differ from discovery split")
        covered.add((seed.level, canonical_technique(seed.technique)))
    expected = {
        (level, technique)
        for level in selected_levels
        for technique in selected_techniques
    }
    missing = expected - covered
    if missing:
        raise ValueError(
            f"final L1/L2 evidence lacks discovery-confirmation pairs: {sorted(missing)}"
        )
