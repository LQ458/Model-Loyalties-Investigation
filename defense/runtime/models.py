from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from typing import Any


VALID_VIEWS = ("output", "cot", "combined")
VALID_TASKS = (
    "hidden_loyalty",
    "activated_loyalty",
    "installed_behavior",
    "activated_behavior",
)


def opaque_request_id(source_id: str, *, namespace: str) -> str:
    payload = f"{namespace}:{source_id}".encode("utf-8")
    return f"{namespace}-{hashlib.sha256(payload).hexdigest()[:24]}"


@dataclass(frozen=True)
class BlindMonitorInput:
    request_id: str
    view: str
    observation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Record:
    record_id: str
    prompt_version: str
    scenario_id: str
    principal: str
    entities: tuple[str, ...]
    condition: str
    sample: int
    user_prompt: str
    content: str
    reasoning: str
    activated: bool | None
    loyalty_expected: bool | None
    transport_status: str
    pair_id: str
    split: str
    source_path: str
    source_sha256: str
    target_behavior_expected: bool | None = None
    target_behavior_activated: bool | None = None

    def label(self, task: str) -> bool | None:
        if task not in VALID_TASKS:
            raise ValueError(f"unknown task: {task}")
        if task == "installed_behavior":
            return self.target_behavior_expected
        if task == "activated_behavior":
            if (
                self.target_behavior_expected is None
                or self.target_behavior_activated is None
            ):
                return None
            return bool(
                self.target_behavior_expected and self.target_behavior_activated
            )
        if self.loyalty_expected is None:
            return None
        if task == "hidden_loyalty":
            return self.loyalty_expected
        if self.activated is None:
            return None
        return bool(self.loyalty_expected and self.activated)

    def observation(self, view: str) -> str:
        if view not in VALID_VIEWS:
            raise ValueError(f"unknown view: {view}")
        if view == "output":
            observed = self.content
        elif view == "cot":
            observed = self.reasoning
        else:
            observed = f"Reasoning:\n{self.reasoning}\n\nVisible answer:\n{self.content}".strip()
        if not observed.strip():
            return ""
        return f"User request:\n{self.user_prompt}\n\nObservation:\n{observed}".strip()

    def blind_monitor_input(self, view: str) -> BlindMonitorInput:
        return BlindMonitorInput(
            request_id=opaque_request_id(self.record_id, namespace="monitor"),
            view=view,
            observation=self.observation(view),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Prediction:
    record_id: str
    monitor: str
    view: str
    score: float | None
    flagged: bool | None
    available: bool
    evidence: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
