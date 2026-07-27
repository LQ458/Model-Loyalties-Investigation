#!/usr/bin/env python3
"""Leave-one-matched-task-pair-out development check for QueRE."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.quere import QueREFeatureRecord  # noqa: E402
from runtime.scoring import auroc, average_precision, confusion  # noqa: E402


def read(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    features = {
        row.request_id: row
        for row in (
            QueREFeatureRecord.from_dict(value) for value in read(args.features)
        )
        if row.available
    }
    truth = {row["request_id"]: row for row in read(args.truth)}
    outcomes = {row["request_id"]: row for row in read(args.outcomes)}
    tasks = sorted({outcomes[key]["task_id"] for key in features})
    predictions: dict[str, tuple[bool, float]] = {}
    folds = {}
    for task in tasks:
        train_ids = [
            key for key in features if outcomes[key]["task_id"] != task
        ]
        test_ids = [key for key in features if outcomes[key]["task_id"] == task]
        x_train = np.asarray([features[key].features for key in train_ids], dtype=float)
        y_train = np.asarray([bool(truth[key]["label"]) for key in train_ids], dtype=int)
        scaler = StandardScaler().fit(x_train)
        model = LogisticRegression(
            C=1.0, solver="lbfgs", max_iter=5000, random_state=0
        ).fit(scaler.transform(x_train), y_train)
        scores = model.predict_proba(
            scaler.transform(
                np.asarray([features[key].features for key in test_ids], dtype=float)
            )
        )[:, 1]
        for key, score in zip(test_ids, scores):
            predictions[key] = (float(score) >= 0.5, float(score))
        folds[task] = {
            "train_rows": len(train_ids),
            "test_rows": len(test_ids),
            "correct": sum(
                predictions[key][0] == bool(truth[key]["label"]) for key in test_ids
            ),
        }
    ids = sorted(predictions)
    labels = [bool(truth[key]["label"]) for key in ids]
    flags = [predictions[key][0] for key in ids]
    scores = [predictions[key][1] for key in ids]
    matrix = confusion(labels, flags)
    result = {
        "schema_version": 1,
        "status": "DEVELOPMENT_TASK_HOLDOUT_COMPLETE",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "feature_sha256": hashlib.sha256(args.features.read_bytes()).hexdigest(),
        "truth_sha256": hashlib.sha256(args.truth.read_bytes()).hexdigest(),
        "tasks": len(tasks),
        "rows": len(ids),
        "confusion": matrix,
        "accuracy": (matrix["tp"] + matrix["tn"]) / len(ids),
        "auroc": auroc(labels, scores),
        "average_precision": average_precision(labels, scores),
        "folds": folds,
        "claim_boundary": (
            "Matched-pair development sanity check only. It motivated freezing "
            "the feature representation but is not the unseen behavior-family result."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
