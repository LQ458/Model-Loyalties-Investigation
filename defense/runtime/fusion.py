from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Iterable, Mapping, Sequence

from .components import RuntimeSignalBundle


def _sigmoid(value: float) -> float:
    if value >= 0:
        exponent = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(max(value, -700.0))
    return exponent / (1.0 + exponent)


def _threshold_at_fpr(scores: Sequence[float], maximum_fpr: float) -> float:
    if not 0.0 <= maximum_fpr < 1.0:
        raise ValueError("maximum_fpr must be in [0, 1)")
    if not scores:
        raise ValueError("at least one benign calibration score is required")
    ordered = sorted(float(value) for value in scores)
    candidates = sorted(
        set(ordered)
        | {
            math.nextafter(value, math.inf)
            for value in ordered
            if value < 1.0
        }
    )
    for threshold in candidates:
        false_positives = sum(value >= threshold for value in ordered)
        if false_positives / len(ordered) <= maximum_fpr:
            return threshold
    raise ValueError(
        "no threshold in [0, 1] can satisfy the requested benign FPR"
    )


@dataclass(frozen=True)
class HybridGateDecision:
    request_id: str
    action: str
    risk: float | None
    reason: str
    available_components: int
    unavailable_components: int
    hard_policy_violation: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MonotonicFusionModel:
    """Small non-negative logistic fusion model over specialist scores."""

    component_ids: tuple[str, ...]
    weights: dict[str, float]
    bias: float
    constrain_threshold: float
    quarantine_threshold: float
    quarantine_min_available_components: int = 2
    quarantine_min_flagged_components: int = 2
    model_status: str = "DEVELOPMENT_ONLY"
    artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        if not self.component_ids or len(self.component_ids) != len(set(self.component_ids)):
            raise ValueError("fusion component IDs must be nonempty and unique")
        if any(float(value) < 0.0 for value in self.weights.values()):
            raise ValueError("fusion weights must be non-negative")
        if not 0.0 <= self.constrain_threshold <= self.quarantine_threshold <= 1.0:
            raise ValueError("fusion thresholds must satisfy 0 <= constrain <= quarantine <= 1")
        if self.quarantine_min_available_components < 1:
            raise ValueError("quarantine availability quorum must be positive")
        if self.quarantine_min_flagged_components < 1:
            raise ValueError("quarantine flag quorum must be positive")

    @classmethod
    def untrained(
        cls,
        component_ids: Iterable[str],
        *,
        constrain_threshold: float = 0.35,
        quarantine_threshold: float = 0.65,
        quarantine_min_available_components: int = 2,
        quarantine_min_flagged_components: int = 2,
    ) -> "MonotonicFusionModel":
        ids = tuple(sorted(set(component_ids)))
        if not ids:
            raise ValueError("at least one component ID is required")
        return cls(
            component_ids=ids,
            weights={name: 0.0 for name in ids},
            bias=0.0,
            constrain_threshold=constrain_threshold,
            quarantine_threshold=quarantine_threshold,
            quarantine_min_available_components=quarantine_min_available_components,
            quarantine_min_flagged_components=quarantine_min_flagged_components,
            model_status="UNTRAINED",
        )

    def _features(self, bundle: RuntimeSignalBundle) -> dict[str, float]:
        by_id = {item.component_id: item for item in bundle.components}
        values: dict[str, float] = {}
        for component_id in self.component_ids:
            item = by_id.get(component_id)
            available = bool(item is not None and item.available)
            values[component_id] = float(item.score) if available else 0.0
        return values

    def risk(self, bundle: RuntimeSignalBundle) -> float | None:
        if bundle.hard_policy_violation:
            return 1.0
        by_id = {item.component_id: item for item in bundle.components}
        if not any(
            by_id.get(component_id) is not None
            and by_id[component_id].available
            for component_id in self.component_ids
        ):
            return None
        features = self._features(bundle)
        logit = self.bias + sum(
            self.weights.get(name, 0.0) * value
            for name, value in features.items()
        )
        return _sigmoid(logit)

    def decide(self, bundle: RuntimeSignalBundle) -> HybridGateDecision:
        by_id = {item.component_id: item for item in bundle.components}
        available = sum(
            bool(by_id.get(component_id) is not None and by_id[component_id].available)
            for component_id in self.component_ids
        )
        unavailable = len(self.component_ids) - available
        if bundle.hard_policy_violation:
            return HybridGateDecision(
                request_id=bundle.request_id,
                action="block",
                risk=1.0,
                reason=bundle.hard_policy_reason or "hard capability policy violation",
                available_components=available,
                unavailable_components=unavailable,
                hard_policy_violation=True,
            )
        score = self.risk(bundle)
        severe_ood = any(
            item.available
            and item.scope == "ood"
            and item.flagged is True
            for item in bundle.components
        )
        flagged = sum(
            bool(
                by_id.get(component_id) is not None
                and by_id[component_id].available
                and by_id[component_id].flagged is True
            )
            for component_id in self.component_ids
        )
        quarantine_quorum = (
            available >= self.quarantine_min_available_components
            and flagged >= self.quarantine_min_flagged_components
        )
        if score is None:
            action = "allow"
            reason = "monitor abstained; capability guard remains active"
        elif score >= self.quarantine_threshold and quarantine_quorum:
            action = "quarantine"
            reason = "high fused risk with independent-signal quorum"
        elif severe_ood:
            action = "constrain"
            reason = "out-of-distribution signal without quarantine quorum"
        elif score >= self.quarantine_threshold:
            action = "constrain"
            reason = "high fused risk without quarantine quorum"
        elif score >= self.constrain_threshold:
            action = "constrain"
            reason = "fused risk at or above constrain threshold"
        else:
            action = "allow"
            reason = "fused risk below thresholds"
        return HybridGateDecision(
            request_id=bundle.request_id,
            action=action,
            risk=score,
            reason=reason,
            available_components=available,
            unavailable_components=unavailable,
            hard_policy_violation=False,
        )

    @classmethod
    def fit(
        cls,
        bundles: Sequence[RuntimeSignalBundle],
        labels: Mapping[str, bool],
        families: Mapping[str, str],
        *,
        strata: Mapping[str, str] | None = None,
        component_ids: Iterable[str] | None = None,
        calibration_bundles: Sequence[RuntimeSignalBundle] | None = None,
        calibration_labels: Mapping[str, bool] | None = None,
        l2: float = 1.0,
        constrain_fpr: float = 0.10,
        quarantine_fpr: float = 0.05,
        quarantine_min_available_components: int = 2,
        quarantine_min_flagged_components: int = 2,
    ) -> "MonotonicFusionModel":
        try:
            import numpy as np
            from scipy.optimize import minimize
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "fusion training requires numpy and scipy in the defense environment"
            ) from exc

        selected = [
            bundle
            for bundle in bundles
            if bundle.request_id in labels and bundle.request_id in families
        ]
        if not selected:
            raise ValueError("no labeled fusion-training bundles")
        observed_labels = {bool(labels[item.request_id]) for item in selected}
        if observed_labels != {False, True}:
            raise ValueError("fusion training requires both label classes")
        ids = tuple(
            sorted(
                set(component_ids or ())
                or {
                    score.component_id
                    for bundle in selected
                    for score in bundle.components
                }
            )
        )
        model = cls.untrained(
            ids,
            quarantine_min_available_components=(
                quarantine_min_available_components
            ),
            quarantine_min_flagged_components=quarantine_min_flagged_components,
        )
        feature_names = ids
        matrix = np.asarray(
            [
                [model._features(bundle)[name] for name in feature_names]
                for bundle in selected
            ],
            dtype=float,
        )
        targets = np.asarray(
            [1.0 if labels[bundle.request_id] else 0.0 for bundle in selected],
            dtype=float,
        )
        if strata is not None:
            missing_strata = {
                bundle.request_id for bundle in selected
            } - set(strata)
            if missing_strata:
                raise ValueError("fusion training records are missing evaluator strata")
        weight_keys = [
            (
                str(strata[bundle.request_id]),
                bool(labels[bundle.request_id]),
            )
            if strata is not None
            else (families[bundle.request_id],)
            for bundle in selected
        ]
        weight_counts: dict[tuple[Any, ...], int] = {}
        for key in weight_keys:
            weight_counts[key] = weight_counts.get(key, 0) + 1
        sample_weights = np.asarray(
            [1.0 / weight_counts[key] for key in weight_keys],
            dtype=float,
        )
        sample_weights *= len(sample_weights) / sample_weights.sum()

        def objective(parameters: Any) -> tuple[float, Any]:
            weights = parameters[:-1]
            bias = parameters[-1]
            logits = np.clip(matrix @ weights + bias, -50.0, 50.0)
            probabilities = 1.0 / (1.0 + np.exp(-logits))
            epsilon = 1e-12
            loss = -np.sum(
                sample_weights
                * (
                    targets * np.log(probabilities + epsilon)
                    + (1.0 - targets) * np.log(1.0 - probabilities + epsilon)
                )
            ) / sample_weights.sum()
            loss += 0.5 * l2 * float(weights @ weights)
            errors = sample_weights * (probabilities - targets) / sample_weights.sum()
            gradient_weights = matrix.T @ errors + l2 * weights
            gradient_bias = errors.sum()
            return float(loss), np.concatenate([gradient_weights, [gradient_bias]])

        initial = np.zeros(len(feature_names) + 1, dtype=float)
        result = minimize(
            objective,
            initial,
            jac=True,
            method="L-BFGS-B",
            bounds=[(0.0, None)] * len(feature_names) + [(None, None)],
        )
        if not result.success:
            raise RuntimeError(f"fusion optimization failed: {result.message}")
        model.weights = {
            name: float(value)
            for name, value in zip(feature_names, result.x[:-1])
        }
        model.bias = float(result.x[-1])
        model.model_status = "DEVELOPMENT_ONLY"

        calibration = list(calibration_bundles or selected)
        calibration_truth = calibration_labels or labels
        benign_risks = [
            value
            for bundle in calibration
            if calibration_truth.get(bundle.request_id) is False
            and (value := model.risk(bundle)) is not None
        ]
        if not benign_risks:
            raise ValueError("fusion calibration requires benign records")
        model.constrain_threshold = _threshold_at_fpr(
            benign_risks,
            constrain_fpr,
        )
        model.quarantine_threshold = _threshold_at_fpr(
            benign_risks,
            quarantine_fpr,
        )
        if model.constrain_threshold > model.quarantine_threshold:
            model.constrain_threshold = model.quarantine_threshold
        return model

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "model_type": "nonnegative_logistic_fusion",
            "component_ids": list(self.component_ids),
            "weights": dict(sorted(self.weights.items())),
            "bias": self.bias,
            "constrain_threshold": self.constrain_threshold,
            "quarantine_threshold": self.quarantine_threshold,
            "quarantine_min_available_components": (
                self.quarantine_min_available_components
            ),
            "quarantine_min_flagged_components": (
                self.quarantine_min_flagged_components
            ),
            "model_status": self.model_status,
            "artifact_sha256": self.artifact_sha256,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MonotonicFusionModel":
        if value.get("model_type") != "nonnegative_logistic_fusion":
            raise ValueError("unsupported fusion model type")
        weights = {str(key): float(score) for key, score in value["weights"].items()}
        if any(score < 0.0 for score in weights.values()):
            raise ValueError("fusion weights must be non-negative")
        return cls(
            component_ids=tuple(str(item) for item in value["component_ids"]),
            weights=weights,
            bias=float(value["bias"]),
            constrain_threshold=float(value["constrain_threshold"]),
            quarantine_threshold=float(value["quarantine_threshold"]),
            quarantine_min_available_components=int(
                value.get("quarantine_min_available_components", 2)
            ),
            quarantine_min_flagged_components=int(
                value.get("quarantine_min_flagged_components", 2)
            ),
            model_status=str(value.get("model_status") or "DEVELOPMENT_ONLY"),
            artifact_sha256=value.get("artifact_sha256"),
        )
