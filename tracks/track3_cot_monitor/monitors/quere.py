from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from track3.components import ComponentScore


COMPONENT_ID = "quere_behavior16_t08_think_v2"
ALLOWED_FEATURE_FIELDS = {
    "request_id",
    "question_set_sha256",
    "features",
    "available",
    "reason",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class QuestionSet:
    question_set_id: str
    questions: tuple[tuple[str, str], ...]
    response_suffix: str
    temperature: float
    thinking_enabled: bool
    max_tokens: int
    top_logprobs: int
    sha256: str

    @classmethod
    def load(cls, path: Path) -> "QuestionSet":
        value = json.loads(path.read_text(encoding="utf-8"))
        regime = value.get("generation_regime") or {}
        questions = tuple(
            (str(item["id"]), str(item["text"]))
            for item in value.get("questions") or []
        )
        if not questions or len({item[0] for item in questions}) != len(questions):
            raise ValueError("question IDs must be nonempty and unique")
        if float(regime.get("temperature", -1)) != 0.8:
            raise ValueError("QueRE question set must use temperature 0.8")
        if regime.get("thinking_enabled") is not True:
            raise ValueError("QueRE question set must keep thinking enabled")
        if int(regime.get("top_logprobs", 0)) < 2:
            raise ValueError("at least two top logprobs are required")
        return cls(
            question_set_id=str(value["question_set_id"]),
            questions=questions,
            response_suffix=str(value["response_suffix"]),
            temperature=0.8,
            thinking_enabled=True,
            max_tokens=int(regime["max_tokens"]),
            top_logprobs=int(regime["top_logprobs"]),
            sha256=sha256_file(path),
        )

    @property
    def feature_order(self) -> tuple[str, ...]:
        return tuple(item[0] for item in self.questions)


def _token_text(item: Mapping[str, Any]) -> str:
    raw_bytes = item.get("bytes")
    if isinstance(raw_bytes, list) and all(
        isinstance(value, int) and 0 <= value <= 255 for value in raw_bytes
    ):
        try:
            return bytes(raw_bytes).decode("utf-8")
        except UnicodeDecodeError:
            pass
    return str(item.get("token") or "")


def _visible_token_index(
    logprobs: Sequence[Mapping[str, Any]],
    visible_content: str,
) -> int | None:
    visible = visible_content.strip()
    if not visible:
        return None
    tokens = [_token_text(item) for item in logprobs]
    joined = "".join(tokens)
    locations: list[int] = []
    start = 0
    while (position := joined.find(visible, start)) >= 0:
        locations.append(position)
        start = position + 1
    if not locations:
        visible_binary = _normalized_binary_token(visible.split(maxsplit=1)[0])
        if visible_binary not in {"yes", "no"}:
            return None
        matching = [
            index
            for index, token in enumerate(tokens)
            if _normalized_binary_token(token) == visible_binary
        ]
        # A thinking stream may mention YES/NO internally. The final matching
        # generated token is the answer token when visible output itself starts
        # with that exact binary response.
        return matching[-1] if matching else None
    # Ollama may include both reasoning and visible-output token records. The
    # final exact occurrence is the visible answer; OpenAI normally has one.
    position = locations[-1]
    offset = 0
    for index, token in enumerate(tokens):
        end = offset + len(token)
        if offset <= position < end:
            return index
        offset = end
    return None


def _normalized_binary_token(value: str) -> str:
    return value.strip().casefold().strip(".,:;!?\"'`()[]{}")


def yes_probability_from_logprobs(
    logprobs: Sequence[Mapping[str, Any]],
    visible_content: str,
) -> tuple[float | None, str]:
    """Return P(YES) at the first visible answer token.

    Thinking-enabled Ollama responses mix reasoning and final-answer token
    records. We align the exact visible content and never infer a position from
    a reasoning token. Missing/ambiguous alignment fails closed.
    """

    index = _visible_token_index(logprobs, visible_content)
    if index is None:
        return None, "visible answer could not be aligned to token logprobs"
    row = logprobs[index]
    alternatives = row.get("top_logprobs")
    if not isinstance(alternatives, list) or not alternatives:
        return None, "top_logprobs missing at visible answer token"
    probability = 0.0
    saw_yes = False
    for alternative in alternatives:
        if not isinstance(alternative, Mapping):
            continue
        if _normalized_binary_token(_token_text(alternative)) != "yes":
            continue
        try:
            probability += math.exp(float(alternative["logprob"]))
            saw_yes = True
        except (KeyError, TypeError, ValueError, OverflowError):
            return None, "invalid YES logprob"
    if not saw_yes:
        # Top-k truncation makes this a conservative, documented approximation.
        return 0.0, "YES absent from top-k; recorded as zero"
    return min(max(probability, 0.0), 1.0), ""


def openai_logprobs(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    choices = response.get("choices") or []
    if not choices:
        return []
    value = (choices[0].get("logprobs") or {}).get("content") or []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def openai_visible_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or choices[0].get("text") or "")


def ollama_logprobs(response: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = response.get("logprobs") or []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def ollama_visible_content(response: Mapping[str, Any]) -> str:
    return str((response.get("message") or {}).get("content") or "")


@dataclass(frozen=True)
class QueREFeatureRecord:
    request_id: str
    question_set_sha256: str
    features: tuple[float | None, ...]
    available: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("request_id is required")
        if len(self.question_set_sha256) != 64:
            raise ValueError("question_set_sha256 must be a SHA-256 digest")
        if self.available and (
            not self.features or any(item is None for item in self.features)
        ):
            raise ValueError("available QueRE records require all features")
        for item in self.features:
            if item is not None and not 0.0 <= item <= 1.0:
                raise ValueError("QueRE features must be probabilities")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "question_set_sha256": self.question_set_sha256,
            "features": list(self.features),
            "available": self.available,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QueREFeatureRecord":
        unknown = set(value) - ALLOWED_FEATURE_FIELDS
        if unknown:
            raise ValueError(f"unknown QueRE feature fields: {sorted(unknown)}")
        raw_features = value.get("features")
        if not isinstance(raw_features, list):
            raise ValueError("features must be a list")
        return cls(
            request_id=str(value.get("request_id") or ""),
            question_set_sha256=str(value.get("question_set_sha256") or ""),
            features=tuple(
                None if item is None else float(item) for item in raw_features
            ),
            available=value.get("available") is True,
            reason=str(value.get("reason") or ""),
        )


@dataclass(frozen=True)
class QueREClassifier:
    question_set_sha256: str
    feature_order: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    flag_threshold: float
    model_status: str
    artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        width = len(self.feature_order)
        if width == 0 or any(
            len(values) != width
            for values in (self.means, self.scales, self.coefficients)
        ):
            raise ValueError("QueRE classifier vectors must have equal nonzero width")
        if any(value <= 0 for value in self.scales):
            raise ValueError("QueRE feature scales must be positive")
        if not 0.0 <= self.flag_threshold <= 1.0:
            raise ValueError("QueRE threshold must be in [0, 1]")

    def risk(self, record: QueREFeatureRecord) -> float | None:
        if (
            not record.available
            or record.question_set_sha256 != self.question_set_sha256
            or len(record.features) != len(self.feature_order)
            or any(value is None for value in record.features)
        ):
            return None
        standardized = [
            (float(value) - mean) / scale
            for value, mean, scale in zip(record.features, self.means, self.scales)
        ]
        logit = self.intercept + sum(
            coefficient * value
            for coefficient, value in zip(self.coefficients, standardized)
        )
        if logit >= 0:
            return 1.0 / (1.0 + math.exp(-min(logit, 700.0)))
        exponent = math.exp(max(logit, -700.0))
        return exponent / (1.0 + exponent)

    def component(self, record: QueREFeatureRecord) -> ComponentScore:
        score = self.risk(record)
        if score is None:
            reason = record.reason or "QueRE feature vector unavailable or incompatible"
            return ComponentScore(
                request_id=record.request_id,
                component_id=COMPONENT_ID,
                scope="offline_audit",
                score=None,
                flagged=None,
                available=False,
                reason=reason,
                artifact_sha256=self.artifact_sha256,
            )
        return ComponentScore(
            request_id=record.request_id,
            component_id=COMPONENT_ID,
            scope="offline_audit",
            score=score,
            flagged=score >= self.flag_threshold,
            available=True,
            reason="frozen QueRE-T0.8-think classifier",
            artifact_sha256=self.artifact_sha256,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "model_type": "quere_logistic_t08_think",
            "question_set_sha256": self.question_set_sha256,
            "feature_order": list(self.feature_order),
            "means": list(self.means),
            "scales": list(self.scales),
            "coefficients": list(self.coefficients),
            "intercept": self.intercept,
            "flag_threshold": self.flag_threshold,
            "model_status": self.model_status,
            "artifact_sha256": self.artifact_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "QueREClassifier":
        if value.get("model_type") != "quere_logistic_t08_think":
            raise ValueError("unsupported QueRE model type")
        return cls(
            question_set_sha256=str(value["question_set_sha256"]),
            feature_order=tuple(str(item) for item in value["feature_order"]),
            means=tuple(float(item) for item in value["means"]),
            scales=tuple(float(item) for item in value["scales"]),
            coefficients=tuple(float(item) for item in value["coefficients"]),
            intercept=float(value["intercept"]),
            flag_threshold=float(value["flag_threshold"]),
            model_status=str(value["model_status"]),
            artifact_sha256=(
                None
                if value.get("artifact_sha256") is None
                else str(value["artifact_sha256"])
            ),
        )
