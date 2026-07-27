#!/usr/bin/env python3
"""Leave-one-behavior-family-out development evaluation for QueRE features."""

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
from track3.scoring import auroc, average_precision  # noqa: E402


def read(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--strata", type=Path)
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
    strata = {}
    if args.strata:
        for row in read(args.strata):
            if set(row) != {"request_id", "stratum"}:
                raise ValueError("strata rows require request_id and stratum only")
            strata[str(row["request_id"])] = str(row["stratum"])
    behavior_families = sorted(
        {
            str(row["family"])
            for row in truth.values()
            if row["label"] is True
        }
    )
    results = {}
    for heldout_family in behavior_families:
        train_ids = [
            request_id
            for request_id, row in truth.items()
            if row["partition"] == "train"
            and row["family"] != heldout_family
            and request_id in features
        ]
        # Held-out positives/nonactivations for the family plus calibration-only
        # benign rows. No held-out-family feature is used in fitting.
        test_ids = [
            request_id
            for request_id, row in truth.items()
            if request_id in features
            and (
                row["family"] == heldout_family
                or (row["partition"] == "calibration" and row["label"] is False)
            )
        ]
        y_train = np.asarray(
            [bool(truth[key]["label"]) for key in train_ids], dtype=int
        )
        y_test = [bool(truth[key]["label"]) for key in test_ids]
        if set(y_train.tolist()) != {0, 1} or set(y_test) != {False, True}:
            results[heldout_family] = {
                "status": "UNSCORABLE",
                "train_rows": len(train_ids),
                "test_rows": len(test_ids),
                "reason": "both classes required in train and test",
            }
            continue
        x_train = np.asarray([features[key].features for key in train_ids], dtype=float)
        x_test = np.asarray([features[key].features for key in test_ids], dtype=float)
        if strata and set(train_ids) - set(strata):
            raise ValueError("LOFO training records are missing evaluator strata")
        weight_keys = [
            (strata[key], bool(truth[key]["label"]))
            if strata
            else (str(truth[key]["family"]),)
            for key in train_ids
        ]
        weight_counts: dict[tuple[Any, ...], int] = {}
        for key in weight_keys:
            weight_counts[key] = weight_counts.get(key, 0) + 1
        weights = np.asarray(
            [1.0 / weight_counts[key] for key in weight_keys],
            dtype=float,
        )
        weights *= len(weights) / weights.sum()
        scaler = StandardScaler().fit(x_train)
        classifier = LogisticRegression(
            C=1.0,
            solver="lbfgs",
            max_iter=5000,
            random_state=0,
        ).fit(scaler.transform(x_train), y_train, sample_weight=weights)
        scores = [
            float(value)
            for value in classifier.predict_proba(scaler.transform(x_test))[:, 1]
        ]
        results[heldout_family] = {
            "status": "COMPLETE",
            "train_rows": len(train_ids),
            "test_rows": len(test_ids),
            "test_positives": sum(y_test),
            "test_negatives": len(y_test) - sum(y_test),
            "auroc": auroc(y_test, scores),
            "average_precision": average_precision(y_test, scores),
            "training_families": sorted(
                {str(truth[key]["family"]) for key in train_ids}
            ),
        }

    result = {
        "schema_version": 1,
        "status": "DEVELOPMENT_LOFO_COMPLETE",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "feature_sha256": hashlib.sha256(args.features.read_bytes()).hexdigest(),
        "truth_sha256": hashlib.sha256(args.truth.read_bytes()).hexdigest(),
        "strata_sha256": (
            hashlib.sha256(args.strata.read_bytes()).hexdigest()
            if args.strata
            else None
        ),
        "weighting": (
            "inverse evaluator stratum x class frequency"
            if strata
            else "inverse behavior-family frequency"
        ),
        "available_feature_rows": len(features),
        "behavior_families": behavior_families,
        "folds": results,
        "caveat": (
            "Evaluator-only family labels define folds. Some public cohorts have "
            "different model identities, so identity confounding remains a "
            "development limitation; the final heldout uses matched same-base controls."
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
