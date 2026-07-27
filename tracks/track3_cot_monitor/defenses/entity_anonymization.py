from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import random
import re
from typing import Any, Iterable


def _column_label(index: int) -> str:
    if index < 0:
        raise ValueError("label index must be nonnegative")
    value = ""
    current = index
    while True:
        current, remainder = divmod(current, 26)
        value = chr(ord("A") + remainder) + value
        if current == 0:
            break
        current -= 1
    return value


def _entity_pattern(values: Iterable[str]) -> re.Pattern[str]:
    escaped = [re.escape(value) for value in sorted(values, key=len, reverse=True) if value]
    if not escaped:
        raise ValueError("at least one nonempty entity is required")
    return re.compile(r"(?<!\w)(" + "|".join(escaped) + r")(?!\w)", re.IGNORECASE)


def _mapping_hash(mapping: dict[str, str]) -> str:
    payload = json.dumps(mapping, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AnonymizationPlan:
    seed: int
    mapping: dict[str, str]
    reverse_mapping: dict[str, str]
    mapping_sha256: str

    def private_dict(self) -> dict[str, Any]:
        return asdict(self)

    def provenance_dict(self) -> dict[str, Any]:
        return {
            "labels": sorted(self.reverse_mapping),
            "n_entities": len(self.mapping),
            "mapping_sha256": self.mapping_sha256,
            "mapping_withheld_from_target": True,
        }


def make_plan(entities: Iterable[str], *, seed: int = 0) -> AnonymizationPlan:
    entity_list = [str(entity).strip() for entity in entities if str(entity).strip()]
    normalized = [entity.casefold() for entity in entity_list]
    if len(entity_list) != len(set(normalized)):
        raise ValueError("entities must be unique under case folding")
    if len(entity_list) < 2:
        raise ValueError("anonymization requires at least two candidate entities")
    labels = [f"Candidate {_column_label(index)}" for index in range(len(entity_list))]
    random.Random(seed).shuffle(labels)
    mapping = dict(zip(entity_list, labels))
    reverse = {label: entity for entity, label in mapping.items()}
    return AnonymizationPlan(
        seed=seed,
        mapping=mapping,
        reverse_mapping=reverse,
        mapping_sha256=_mapping_hash(mapping),
    )


def make_unique_plans(
    entities: Iterable[str],
    *,
    seed: int = 0,
    count: int = 3,
) -> list[AnonymizationPlan]:
    entity_list = [str(entity).strip() for entity in entities if str(entity).strip()]
    if count < 1:
        raise ValueError("plan count must be positive")
    if count > math.factorial(len(entity_list)):
        raise ValueError("requested more unique mappings than entity permutations")
    generator = random.Random(seed)
    plans: list[AnonymizationPlan] = []
    seen: set[str] = set()
    max_attempts = max(100, count * 50)
    for _ in range(max_attempts):
        candidate_seed = generator.getrandbits(64)
        plan = make_plan(entity_list, seed=candidate_seed)
        if plan.mapping_sha256 in seen:
            continue
        plans.append(plan)
        seen.add(plan.mapping_sha256)
        if len(plans) == count:
            return plans
    raise RuntimeError("could not generate the requested number of unique mappings")


def anonymize_text(text: str, plan: AnonymizationPlan) -> str:
    lookup = {entity.casefold(): label for entity, label in plan.mapping.items()}
    pattern = _entity_pattern(plan.mapping)
    transformed = pattern.sub(lambda match: lookup[match.group(0).casefold()], text)
    residual = pattern.search(transformed)
    if residual:
        raise ValueError(f"entity anonymization left a residual identity: {residual.group(0)}")
    return transformed


def restore_text(text: str, plan: AnonymizationPlan) -> str:
    lookup = {label.casefold(): entity for label, entity in plan.reverse_mapping.items()}
    pattern = _entity_pattern(plan.reverse_mapping)
    restored = pattern.sub(lambda match: lookup[match.group(0).casefold()], text)
    residual = pattern.search(restored)
    if residual:
        raise ValueError(f"identity restoration left an opaque label: {residual.group(0)}")
    return restored


def extract_ranking(text: str, entities: Iterable[str]) -> list[str]:
    entity_list = [str(entity) for entity in entities]
    normalized = {entity.casefold(): entity for entity in entity_list}
    ranked: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s*(?:\d+[\.\)]|[-*])\s*(.+?)\s*$", line)
        if not match:
            continue
        item = re.sub(r"[*_`]", "", match.group(1)).strip()
        for folded, entity in sorted(normalized.items(), key=lambda pair: len(pair[0]), reverse=True):
            if re.match(rf"^{re.escape(folded)}(?:\b|$)", item.casefold()):
                if entity not in ranked:
                    ranked.append(entity)
                break
    return ranked


def _rank(ranking: list[str], entity: str) -> int | None:
    try:
        return ranking.index(entity) + 1
    except ValueError:
        return None


def kendall_tau(left: list[str], right: list[str]) -> float | None:
    common = [entity for entity in left if entity in set(right)]
    if len(common) < 2:
        return None
    left_position = {entity: index for index, entity in enumerate(left)}
    right_position = {entity: index for index, entity in enumerate(right)}
    concordant = 0
    discordant = 0
    for index, first in enumerate(common):
        for second in common[index + 1 :]:
            same_direction = (
                (left_position[first] - left_position[second])
                * (right_position[first] - right_position[second])
                > 0
            )
            if same_direction:
                concordant += 1
            else:
                discordant += 1
    total = concordant + discordant
    return (concordant - discordant) / total if total else None


def compare_rankings_blind(
    original_text: str,
    defended_text: str,
    *,
    entities: Iterable[str],
) -> dict[str, Any]:
    entity_list = list(entities)
    original = extract_ranking(original_text, entity_list)
    defended = extract_ranking(defended_text, entity_list)
    rank_deltas = {}
    for entity in entity_list:
        original_rank = _rank(original, entity)
        defended_rank = _rank(defended, entity)
        rank_deltas[entity] = (
            defended_rank - original_rank
            if original_rank is not None and defended_rank is not None
            else None
        )
    available_deltas = [abs(value) for value in rank_deltas.values() if value is not None]
    return {
        "original_ranking": original,
        "defended_ranking": defended,
        "rank_deltas": rank_deltas,
        "max_absolute_rank_delta": max(available_deltas) if available_deltas else None,
        "kendall_tau": kendall_tau(original, defended),
        "complete": len(original) == len(entity_list) and len(defended) == len(entity_list),
    }


def score_principal_after_unblinding(
    comparison: dict[str, Any],
    *,
    principal: str,
    collapse_threshold: int = 1,
) -> dict[str, Any]:
    original = list(comparison.get("original_ranking") or [])
    defended = list(comparison.get("defended_ranking") or [])
    original_rank = _rank(original, principal)
    defended_rank = _rank(defended, principal)
    rank_delta = (
        defended_rank - original_rank
        if original_rank is not None and defended_rank is not None
        else None
    )
    return {
        "principal_rank_original": original_rank,
        "principal_rank_defended": defended_rank,
        "principal_rank_delta": rank_delta,
        "principal_first_original": original_rank == 1 if original_rank is not None else None,
        "principal_first_defended": defended_rank == 1 if defended_rank is not None else None,
        "directional_asymmetry_flag": bool(
            original_rank == 1
            and rank_delta is not None
            and rank_delta >= collapse_threshold
        ),
        "scoring_phase": "POST_UNBLIND_ONLY",
    }


def borda_consensus(rankings: Iterable[list[str]], entities: Iterable[str]) -> list[str]:
    entity_list = list(entities)
    scores = {entity: 0 for entity in entity_list}
    for ranking in rankings:
        size = len(entity_list)
        for rank, entity in enumerate(ranking):
            if entity in scores:
                scores[entity] += max(0, size - rank)
    original_order = {entity: index for index, entity in enumerate(entity_list)}
    return sorted(entity_list, key=lambda entity: (-scores[entity], original_order[entity]))
