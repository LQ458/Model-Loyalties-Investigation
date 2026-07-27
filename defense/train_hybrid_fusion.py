#!/usr/bin/env python3
"""Fit the principal-blind monotonic fusion gate from sealed evaluator labels."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.components import RuntimeSignalBundle  # noqa: E402
from runtime.fusion import MonotonicFusionModel  # noqa: E402


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number}: object required")
                rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_truth(
    path: Path,
) -> tuple[dict[str, bool], dict[str, str], dict[str, str]]:
    labels: dict[str, bool] = {}
    families: dict[str, str] = {}
    partitions: dict[str, str] = {}
    allowed = {"request_id", "label", "family", "partition"}
    for row in _read_jsonl(path):
        unknown = set(row) - allowed
        if unknown:
            raise ValueError(f"truth file has unknown fields: {sorted(unknown)}")
        request_id = row.get("request_id")
        label = row.get("label")
        family = row.get("family")
        partition = row.get("partition")
        if not isinstance(request_id, str) or not request_id:
            raise ValueError("truth request_id must be nonempty")
        if type(label) is not bool:
            raise ValueError(f"{request_id}: label must be boolean")
        if not isinstance(family, str) or not family:
            raise ValueError(f"{request_id}: family is required")
        if partition not in {"train", "calibration"}:
            raise ValueError(
                f"{request_id}: partition must be train or calibration; "
                "test labels must not enter fusion fitting"
            )
        if request_id in labels:
            raise ValueError(f"duplicate truth request ID: {request_id}")
        labels[request_id] = label
        families[request_id] = family
        partitions[request_id] = partition
    return labels, families, partitions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bundles",
        type=Path,
        required=True,
        help="Blind runtime signal bundles as JSONL. No labels or family fields.",
    )
    parser.add_argument(
        "--truth",
        type=Path,
        required=True,
        help="Evaluator-only request_id/label/family/partition JSONL.",
    )
    parser.add_argument(
        "--strata",
        type=Path,
        help="Optional evaluator-only request_id/stratum JSONL for class balancing.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--l2", type=float, default=1.0)
    parser.add_argument("--constrain-fpr", type=float, default=0.10)
    parser.add_argument("--quarantine-fpr", type=float, default=0.05)
    parser.add_argument(
        "--component-ids",
        default="",
        help="Comma-separated operational components; unavailable components abstain.",
    )
    parser.add_argument(
        "--quarantine-min-available-components",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--quarantine-min-flagged-components",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--model-status",
        choices=[
            "DEVELOPMENT_ONLY",
            "FROZEN_EVALUATION",
            "POST_HOC_CORRECTED_ANALYSIS",
        ],
        default="DEVELOPMENT_ONLY",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundles = [
        RuntimeSignalBundle.from_dict(row)
        for row in _read_jsonl(args.bundles)
    ]
    labels, families, partitions = _load_truth(args.truth)
    strata = None
    if args.strata:
        strata = {}
        for row in _read_jsonl(args.strata):
            if set(row) != {"request_id", "stratum"}:
                raise ValueError("strata rows require request_id and stratum only")
            strata[str(row["request_id"])] = str(row["stratum"])
    by_id = {bundle.request_id: bundle for bundle in bundles}
    if len(by_id) != len(bundles):
        raise ValueError("duplicate runtime bundle request ID")
    missing = set(labels) - set(by_id)
    if missing:
        raise ValueError(f"truth IDs missing runtime bundles: {sorted(missing)[:5]}")

    training = [by_id[key] for key, value in partitions.items() if value == "train"]
    calibration = [
        by_id[key] for key, value in partitions.items() if value == "calibration"
    ]
    if not training or not calibration:
        raise ValueError("nonempty train and calibration partitions are required")
    model = MonotonicFusionModel.fit(
        training,
        labels,
        families,
        strata=strata,
        component_ids=[
            item.strip()
            for item in args.component_ids.split(",")
            if item.strip()
        ]
        or None,
        calibration_bundles=calibration,
        calibration_labels=labels,
        l2=args.l2,
        constrain_fpr=args.constrain_fpr,
        quarantine_fpr=args.quarantine_fpr,
        quarantine_min_available_components=(
            args.quarantine_min_available_components
        ),
        quarantine_min_flagged_components=args.quarantine_min_flagged_components,
    )
    model.model_status = args.model_status

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(model.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = _sha256(args.output)
    receipt = {
        "schema_version": 1,
        "artifact": str(args.output.resolve()),
        "sha256": digest,
        "model_status": model.model_status,
        "training_rows": len(training),
        "calibration_rows": len(calibration),
        "training_families": sorted(
            {families[item.request_id] for item in training}
        ),
        "calibration_families": sorted(
            {families[item.request_id] for item in calibration}
        ),
        "bundle_source_sha256": _sha256(args.bundles),
        "truth_source_sha256": _sha256(args.truth),
        "strata_source_sha256": _sha256(args.strata) if args.strata else None,
        "weighting": (
            "inverse evaluator stratum x class frequency"
            if strata is not None
            else "inverse behavior-family frequency"
        ),
        "operational_component_ids": list(model.component_ids),
        "missingness_policy": "availability is metadata; no missingness features",
        "quarantine_quorum": {
            "minimum_available_components": (
                model.quarantine_min_available_components
            ),
            "minimum_flagged_components": model.quarantine_min_flagged_components,
        },
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
