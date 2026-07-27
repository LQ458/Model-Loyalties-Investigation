from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


VALID_COMPONENT_SCOPES = (
    "input",
    "output",
    "cot",
    "action",
    "combined",
    "offline_audit",
    "ood",
)


@dataclass(frozen=True)
class ComponentScore:
    """One specialist's blind score for one opaque request."""

    request_id: str
    component_id: str
    scope: str
    score: float | None
    flagged: bool | None
    available: bool
    evidence: str | None = None
    reason: str = ""
    artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.component_id:
            raise ValueError("component_id is required")
        if self.scope not in VALID_COMPONENT_SCOPES:
            raise ValueError(f"unknown component scope: {self.scope}")
        if self.available:
            if self.score is None or self.flagged is None:
                raise ValueError("available scores require score and flagged")
            if not 0.0 <= self.score <= 1.0:
                raise ValueError("component score must be between zero and one")
        elif self.score is not None or self.flagged is not None:
            raise ValueError("unavailable scores must not carry score or flag")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ComponentScore":
        allowed = {
            "request_id",
            "component_id",
            "scope",
            "score",
            "flagged",
            "available",
            "evidence",
            "reason",
            "artifact_sha256",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown component score fields: {sorted(unknown)}")
        return cls(**value)


@dataclass(frozen=True)
class RuntimeSignalBundle:
    """Principal-blind runtime inputs to the fusion gate."""

    request_id: str
    components: tuple[ComponentScore, ...]
    hard_policy_violation: bool = False
    hard_policy_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")
        if any(item.request_id != self.request_id for item in self.components):
            raise ValueError("all component scores must use the bundle request ID")
        component_ids = [item.component_id for item in self.components]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("component IDs must be unique within a bundle")
        if self.hard_policy_violation and not self.hard_policy_reason:
            raise ValueError("hard policy violations require a reason")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "components": [item.to_dict() for item in self.components],
            "hard_policy_violation": self.hard_policy_violation,
            "hard_policy_reason": self.hard_policy_reason,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RuntimeSignalBundle":
        allowed = {
            "request_id",
            "components",
            "hard_policy_violation",
            "hard_policy_reason",
        }
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown runtime bundle fields: {sorted(unknown)}")
        return cls(
            request_id=str(value.get("request_id") or ""),
            components=tuple(
                ComponentScore.from_dict(item)
                for item in value.get("components") or []
            ),
            hard_policy_violation=bool(value.get("hard_policy_violation", False)),
            hard_policy_reason=value.get("hard_policy_reason"),
        )


def group_component_scores(
    scores: Iterable[ComponentScore],
) -> list[RuntimeSignalBundle]:
    grouped: dict[str, list[ComponentScore]] = {}
    for score in scores:
        grouped.setdefault(score.request_id, []).append(score)
    return [
        RuntimeSignalBundle(request_id=request_id, components=tuple(items))
        for request_id, items in sorted(grouped.items())
    ]
