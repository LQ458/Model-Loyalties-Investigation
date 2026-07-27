from __future__ import annotations

from track3.components import ComponentScore
from track3.models import Prediction


def prediction_to_component(
    prediction: Prediction,
    *,
    component_id: str | None = None,
    artifact_sha256: str | None = None,
) -> ComponentScore:
    return ComponentScore(
        request_id=prediction.record_id,
        component_id=component_id or prediction.monitor,
        scope=prediction.view,
        score=prediction.score,
        flagged=prediction.flagged,
        available=prediction.available,
        evidence=prediction.evidence,
        reason=prediction.reason,
        artifact_sha256=artifact_sha256,
    )
