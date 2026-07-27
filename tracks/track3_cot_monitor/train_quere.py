#!/usr/bin/env python3
"""Fit a frozen QueRE classifier using evaluator-only family labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.quere import (  # noqa: E402
    QueREClassifier,
    QueREFeatureRecord,
    QuestionSet,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number}: object required")
                values.append(value)
    return values


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def threshold_at_fpr(scores: list[float], maximum_fpr: float) -> float:
    if not scores:
        raise ValueError("benign calibration scores are required")
    candidates = sorted(
        set(scores)
        | {
            math.nextafter(value, math.inf)
            for value in scores
            if value < 1.0
        }
    )
    for threshold in candidates:
        if sum(value >= threshold for value in scores) / len(scores) <= maximum_fpr:
            return threshold
    return 1.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument(
        "--strata",
        type=Path,
        help="Optional evaluator-only request_id/stratum JSONL for class balancing.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-benign-fpr", type=float, default=0.05)
    parser.add_argument("--c", type=float, default=1.0)
    parser.add_argument(
        "--model-status",
        choices=["FROZEN_DEVELOPMENT", "FROZEN_EVALUATION"],
        default="FROZEN_DEVELOPMENT",
    )
    args = parser.parse_args()
    if not 0 <= args.max_benign_fpr < 1:
        raise ValueError("--max-benign-fpr must be in [0, 1)")

    features = {
        record.request_id: record
        for record in (
            QueREFeatureRecord.from_dict(value)
            for value in read_jsonl(args.features)
        )
    }
    truth: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(args.truth):
        if set(row) != {"request_id", "label", "family", "partition"}:
            raise ValueError("truth rows require request_id/label/family/partition only")
        if type(row["label"]) is not bool:
            raise ValueError("truth label must be boolean")
        if row["partition"] not in {"train", "calibration"}:
            raise ValueError("only train/calibration truth may fit QueRE")
        truth[str(row["request_id"])] = row
    selected = [
        (features[request_id], row)
        for request_id, row in truth.items()
        if request_id in features and features[request_id].available
    ]
    train = [item for item in selected if item[1]["partition"] == "train"]
    calibration = [
        item for item in selected if item[1]["partition"] == "calibration"
    ]
    if not train or not calibration:
        raise ValueError("nonempty available train and calibration sets are required")
    if {item[1]["label"] for item in train} != {False, True}:
        raise ValueError("QueRE training requires both classes")
    hashes = {item[0].question_set_sha256 for item in selected}
    widths = {len(item[0].features) for item in selected}
    if len(hashes) != 1 or len(widths) != 1:
        raise ValueError("all QueRE features must use one frozen question set and width")
    question_set = QuestionSet.load(args.questions)
    if hashes != {question_set.sha256} or widths != {len(question_set.questions)}:
        raise ValueError("feature vectors do not match the supplied frozen question set")

    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    x_train = np.asarray([item[0].features for item in train], dtype=float)
    y_train = np.asarray([bool(item[1]["label"]) for item in train], dtype=int)
    strata: dict[str, str] = {}
    if args.strata:
        for row in read_jsonl(args.strata):
            if set(row) != {"request_id", "stratum"}:
                raise ValueError("strata rows require request_id and stratum only")
            strata[str(row["request_id"])] = str(row["stratum"])
        missing_strata = {
            record.request_id for record, _ in train
        } - set(strata)
        if missing_strata:
            raise ValueError("training records are missing evaluator strata")
    weight_keys = [
        (strata[record.request_id], bool(row["label"]))
        if strata
        else (str(row["family"]),)
        for record, row in train
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
        C=args.c,
        solver="lbfgs",
        max_iter=5000,
        random_state=0,
    ).fit(scaler.transform(x_train), y_train, sample_weight=weights)
    provisional = QueREClassifier(
        question_set_sha256=next(iter(hashes)),
        feature_order=question_set.feature_order,
        means=tuple(float(value) for value in scaler.mean_),
        scales=tuple(float(value) for value in scaler.scale_),
        coefficients=tuple(float(value) for value in classifier.coef_[0]),
        intercept=float(classifier.intercept_[0]),
        flag_threshold=0.5,
        model_status=args.model_status,
    )
    benign_scores = [
        score
        for record, row in calibration
        if row["label"] is False and (score := provisional.risk(record)) is not None
    ]
    threshold = threshold_at_fpr(benign_scores, args.max_benign_fpr)
    model = QueREClassifier(
        **{
            **provisional.__dict__,
            "flag_threshold": threshold,
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(model.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt = {
        "schema_version": 1,
        "status": model.model_status,
        "artifact": str(args.output.resolve()),
        "sha256": sha256(args.output),
        "feature_source_sha256": sha256(args.features),
        "truth_source_sha256": sha256(args.truth),
        "strata_source_sha256": sha256(args.strata) if args.strata else None,
        "weighting": (
            "inverse evaluator stratum x class frequency"
            if strata
            else "inverse behavior-family frequency"
        ),
        "question_set_sha256": model.question_set_sha256,
        "question_set_source": str(args.questions.resolve()),
        "train_rows": len(train),
        "calibration_rows": len(calibration),
        "unavailable_or_unmatched_rows": len(truth) - len(selected),
        "training_families": sorted({str(item[1]["family"]) for item in train}),
        "calibration_families": sorted(
            {str(item[1]["family"]) for item in calibration}
        ),
        "max_benign_fpr": args.max_benign_fpr,
        "flag_threshold": threshold,
    }
    receipt_path = args.output.with_suffix(args.output.suffix + ".receipt.json")
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
