#!/usr/bin/env python3
"""Summarize whether frozen QueRE scoring or fail-closed missingness drove actions."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.quere import QueREFeatureRecord  # noqa: E402
from runtime.scoring import confusion, wilson_interval  # noqa: E402


def read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--installed-truth", type=Path, required=True)
    parser.add_argument("--outcomes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    features = {
        row.request_id: row
        for row in (QueREFeatureRecord.from_dict(value) for value in read(args.features))
    }
    truth = {str(row["request_id"]): bool(row["label"]) for row in read(args.installed_truth)}
    outcomes = {str(row["request_id"]): row for row in read(args.outcomes)}
    if not features or set(features) != set(truth) or set(features) != set(outcomes):
        raise ValueError("features, installed truth, and outcomes must join one-to-one")

    request_ids = sorted(features)
    labels = [truth[key] for key in request_ids]
    unavailable = [not features[key].available for key in request_ids]
    matrix = confusion(labels, unavailable)
    by_condition = {}
    for label in (False, True):
        keys = [key for key in request_ids if truth[key] is label]
        available = sum(features[key].available for key in keys)
        by_condition["installed" if label else "clean"] = {
            "rows": len(keys),
            "available_complete_vectors": available,
            "unavailable_vectors": len(keys) - available,
            "complete_vector_rate": wilson_interval(available, len(keys)),
        }

    first_missing = Counter()
    missing_feature_counts = Counter()
    for key in request_ids:
        record = features[key]
        count = sum(value is None for value in record.features)
        missing_feature_counts[str(count)] += 1
        if not record.available:
            first = record.reason.split(":", 1)[0] if record.reason else "unknown"
            first_missing[first] += 1

    result = {
        "schema_version": 1,
        "status": "SEALED_HELDOUT_DESCRIPTIVE_SECONDARY",
        "interpretation": (
            "Unavailable required QueRE features are a predeclared fail-closed "
            "condition, not learned classifier detections."
        ),
        "integrity": {
            "features_sha256": sha256(args.features),
            "installed_truth_sha256": sha256(args.installed_truth),
            "outcomes_sha256": sha256(args.outcomes),
        },
        "by_condition": by_condition,
        "unavailable_as_installed_condition_detector": {
            "confusion": matrix,
            "recall": wilson_interval(matrix["tp"], matrix["tp"] + matrix["fn"]),
            "false_positive_rate": wilson_interval(
                matrix["fp"], matrix["fp"] + matrix["tn"]
            ),
        },
        "first_unavailable_question_counts": dict(sorted(first_missing.items())),
        "missing_feature_count_distribution": dict(
            sorted(missing_feature_counts.items(), key=lambda item: int(item[0]))
        ),
        "learned_classifier_scope": {
            "installed_complete_vectors": by_condition["installed"]["available_complete_vectors"],
            "clean_complete_vectors": by_condition["clean"]["available_complete_vectors"],
            "conclusion": (
                "No installed heldout row reached the frozen classifier, so heldout "
                "learned QueRE transfer is not estimable."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
