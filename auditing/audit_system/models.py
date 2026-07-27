from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = 2


@dataclass(frozen=True)
class GroundTruthField:
    id: str | None = None
    canonical: str | None = None
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    @property
    def expected_present(self) -> bool:
        return bool(self.canonical or self.id)

    @classmethod
    def from_value(cls, value: Any, *, default_id: str | None = None) -> "GroundTruthField":
        if value is None:
            return cls()
        if isinstance(value, str):
            return cls(id=default_id, canonical=value)
        if not isinstance(value, dict):
            raise ValueError("ground-truth field must be a string, object, or null")
        canonical = value.get("canonical", value.get("value"))
        return cls(
            id=str(value.get("id", default_id)) if value.get("id", default_id) else None,
            canonical=str(canonical) if canonical else None,
            aliases=tuple(str(item) for item in value.get("aliases", []) if str(item).strip()),
            keywords=tuple(str(item) for item in value.get("keywords", []) if str(item).strip()),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GroundTruth:
    schema_version: int = SCHEMA_VERSION
    loyalty_expected: bool | None = None
    behavior_activation_expected: bool | None = None
    principal: GroundTruthField = field(default_factory=GroundTruthField)
    activation_condition: GroundTruthField = field(default_factory=GroundTruthField)
    action_pattern: GroundTruthField = field(default_factory=GroundTruthField)
    control_role: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "GroundTruth":
        raw = dict(data or {})
        legacy_principal = raw.get("principal")
        principal_value = raw.get("principal_spec", legacy_principal)
        condition_value = raw.get("activation_condition_spec", raw.get("activation_condition"))
        action_value = raw.get("action_pattern_spec", raw.get("action_pattern"))
        return cls(
            schema_version=int(raw.get("schema_version", SCHEMA_VERSION)),
            loyalty_expected=bool(raw["loyalty_expected"]) if "loyalty_expected" in raw else None,
            behavior_activation_expected=(
                bool(raw["behavior_activation_expected"])
                if "behavior_activation_expected" in raw
                else None
            ),
            principal=GroundTruthField.from_value(
                principal_value,
                default_id="principal" if principal_value else None,
            ),
            activation_condition=GroundTruthField.from_value(
                condition_value,
                default_id="activation_condition" if condition_value else None,
            ),
            action_pattern=GroundTruthField.from_value(
                action_value,
                default_id="action_pattern" if action_value else None,
            ),
            control_role=str(raw.get("control_role", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Condition:
    id: str
    label: str
    system_prompt: str
    ground_truth: GroundTruth = field(default_factory=GroundTruth)
    system_prompt_sha256: str = ""
    system_prompt_path: str = ""
    source_prompt_sha256: str = ""
    source_repository_commit: str = ""
    template_values: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OrganismManifest:
    manifest_version: int
    organism_id: str
    target_model: str
    principal: str
    activation_condition: str
    prompt_sha256: str
    frozen: bool
    conditions: tuple[Condition, ...]
    schema_version: int = SCHEMA_VERSION
    protocol_sha256: str = ""
    seed_bank_sha256: str = ""
    judge_rubric_sha256: str = ""
    dependency_lock_sha256: str = ""
    repository_commit: str = ""


@dataclass(frozen=True)
class Seed:
    id: str
    level: int
    technique: str
    user_prompt: str = ""
    assistant_prefill: str = ""
    scratchpad_prefill: str = ""
    completion_prompt: str = ""
    model_turn_seed: str = ""
    label_mapping: dict[str, str] | None = None
    split: str = "development"
    provided_facts: tuple[str, ...] = ()
    discoverable_fields: tuple[str, ...] = ()
    pair_id: str = ""
    seed_sha256: str = ""
    phase: str = "development"
    hypothesis_ref: str = ""
    control_type: str = ""
    randomization_key: str = ""


@dataclass
class Transcript:
    run_id: str
    organism_id: str
    condition: str
    affordance_level: int
    technique: str
    seed_id: str
    sample: int
    schema_version: int = SCHEMA_VERSION
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    transport: dict[str, Any] = field(default_factory=dict)
    behavior: dict[str, Any] = field(default_factory=dict)
    judge: dict[str, Any] = field(default_factory=dict)
    ground_truth: dict[str, Any] = field(default_factory=dict)

    def public_for_judge(self, *, include_reasoning: bool = True) -> dict[str, Any]:
        response = dict(self.response)
        if not include_reasoning:
            response.pop("reasoning", None)
            response.pop("scratchpad", None)
            provenance = dict(response.get("provenance") or {})
            for key in (
                "target_reasoning_continuation",
                "reasoning",
                "scratchpad",
            ):
                provenance.pop(key, None)
            if provenance:
                response["provenance"] = provenance
            elif "provenance" in response:
                response.pop("provenance")
        return {
            "schema_version": self.schema_version,
            "affordance_level": self.affordance_level,
            "technique": self.technique,
            "request": self.request,
            "response": response,
            "transport": self.transport,
            "target_reasoning_visible_to_judge": include_reasoning,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def condition_from_dict(data: dict[str, Any]) -> Condition:
    prompt_value = data.get("system_prompt", data.get("system_prompt_path", ""))
    missing = [key for key in ("id", "label") if not str(data.get(key, "")).strip()]
    if not str(prompt_value).strip():
        missing.append("system_prompt or system_prompt_path")
    if missing:
        raise ValueError(f"condition missing required fields: {', '.join(missing)}")
    return Condition(
        id=str(data["id"]),
        label=str(data["label"]),
        system_prompt=str(prompt_value),
        ground_truth=GroundTruth.from_dict(data.get("ground_truth")),
        system_prompt_sha256=str(data.get("system_prompt_sha256", "")),
        system_prompt_path=str(data.get("system_prompt_path", "")),
        source_prompt_sha256=str(data.get("source_prompt_sha256", "")),
        source_repository_commit=str(data.get("source_repository_commit", "")),
        template_values={
            str(key): str(value)
            for key, value in dict(data.get("template_values") or {}).items()
        },
    )


def manifest_from_dict(data: dict[str, Any]) -> OrganismManifest:
    required = ("manifest_version", "organism_id", "target_model", "principal", "conditions")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"manifest missing required fields: {', '.join(missing)}")
    conditions = tuple(condition_from_dict(item) for item in data["conditions"])
    if not conditions:
        raise ValueError("manifest must contain at least one condition")
    ids = [condition.id for condition in conditions]
    if len(set(ids)) != len(ids):
        raise ValueError("manifest condition IDs must be unique")
    return OrganismManifest(
        manifest_version=int(data["manifest_version"]),
        organism_id=str(data["organism_id"]),
        target_model=str(data["target_model"]),
        principal=str(data["principal"]),
        activation_condition=str(data.get("activation_condition", "")),
        prompt_sha256=str(data.get("prompt_sha256", "")),
        frozen=bool(data.get("frozen", False)),
        conditions=conditions,
        schema_version=int(data.get("schema_version", SCHEMA_VERSION)),
        protocol_sha256=str(data.get("protocol_sha256", "")),
        seed_bank_sha256=str(data.get("seed_bank_sha256", "")),
        judge_rubric_sha256=str(data.get("judge_rubric_sha256", "")),
        dependency_lock_sha256=str(data.get("dependency_lock_sha256", "")),
        repository_commit=str(data.get("repository_commit", "")),
    )


def seed_from_dict(data: dict[str, Any]) -> Seed:
    required = ("id", "level", "technique")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"seed missing required fields: {', '.join(missing)}")
    level = int(data["level"])
    if level not in range(1, 6):
        raise ValueError(f"seed level must be 1-5: {level}")
    return Seed(
        id=str(data["id"]),
        level=level,
        technique=str(data["technique"]),
        user_prompt=str(data.get("user_prompt", "")),
        assistant_prefill=str(data.get("assistant_prefill", "")),
        scratchpad_prefill=str(data.get("scratchpad_prefill", "")),
        completion_prompt=str(data.get("completion_prompt", "")),
        model_turn_seed=str(data.get("model_turn_seed", "")),
        label_mapping=dict(data["label_mapping"]) if data.get("label_mapping") else None,
        split=str(data.get("split", "development")),
        provided_facts=tuple(str(item) for item in data.get("provided_facts", [])),
        discoverable_fields=tuple(str(item) for item in data.get("discoverable_fields", [])),
        pair_id=str(data.get("pair_id", "")),
        seed_sha256=str(data.get("seed_sha256", "")),
        phase=str(data.get("phase", "development")),
        hypothesis_ref=str(data.get("hypothesis_ref", "")),
        control_type=str(data.get("control_type", "")),
        randomization_key=str(data.get("randomization_key", "")),
    )
