#!/usr/bin/env python3
"""Post-unblind development evaluation for hybrid gate and component ablations."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from track3.components import RuntimeSignalBundle  # noqa: E402
from track3.scoring import (  # noqa: E402
    auroc,
    average_precision,
    confusion,
    tpr_at_fpr,
    wilson_interval,
)


def _read(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _metrics(
    labels: list[bool],
    flags: list[bool],
    scores: list[float],
) -> dict[str, Any]:
    matrix = confusion(labels, flags)
    precision_denominator = matrix["tp"] + matrix["fp"]
    recall_denominator = matrix["tp"] + matrix["fn"]
    precision = (
        matrix["tp"] / precision_denominator if precision_denominator else None
    )
    recall = matrix["tp"] / recall_denominator if recall_denominator else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None
        and recall is not None
        and precision + recall > 0
        else None
    )
    negatives = matrix["fp"] + matrix["tn"]
    return {
        "n": len(labels),
        "positives": sum(labels),
        "negatives": len(labels) - sum(labels),
        "confusion": matrix,
        "precision": precision,
        "recall": recall,
        "recall_wilson95": wilson_interval(matrix["tp"], recall_denominator),
        "false_positive_rate": matrix["fp"] / negatives if negatives else None,
        "false_positive_wilson95": wilson_interval(matrix["fp"], negatives),
        "f1": f1,
        "auroc": auroc(labels, scores),
        "average_precision": average_precision(labels, scores),
        "tpr_at_fpr_0_05": tpr_at_fpr(labels, scores, 0.05),
        "tpr_at_fpr_0_10": tpr_at_fpr(labels, scores, 0.10),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument(
        "--partition",
        choices=["train", "calibration", "all"],
        default="calibration",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    truth = {
        row["request_id"]: row
        for row in _read(args.truth)
        if args.partition == "all" or row["partition"] == args.partition
    }
    decisions = {row["request_id"]: row for row in _read(args.decisions)}
    bundles = {
        row.request_id: row
        for row in (
            RuntimeSignalBundle.from_dict(value) for value in _read(args.bundles)
        )
    }
    request_ids = sorted(set(truth) & set(decisions) & set(bundles))
    labels = [bool(truth[key]["label"]) for key in request_ids]
    fusion_flags = [decisions[key]["action"] != "allow" for key in request_ids]
    fusion_scores = [float(decisions[key]["risk"]) for key in request_ids]
    component_ids = sorted(
        {
            component.component_id
            for key in request_ids
            for component in bundles[key].components
        }
    )
    components: dict[str, Any] = {}
    for component_id in component_ids:
        values = []
        component_labels = []
        for key in request_ids:
            component = next(
                (
                    value
                    for value in bundles[key].components
                    if value.component_id == component_id and value.available
                ),
                None,
            )
            if component is not None:
                values.append(component)
                component_labels.append(bool(truth[key]["label"]))
        components[component_id] = {
            "unavailable": len(request_ids) - len(values),
            "metrics": (
                _metrics(
                    component_labels,
                    [bool(value.flagged) for value in values],
                    [float(value.score) for value in values],
                )
                if values
                else None
            ),
        }
    result = {
        "schema_version": 1,
        "status": "DEVELOPMENT_ONLY",
        "partition": args.partition,
        "claim_boundary": (
            "Post-unblind retrospective scoring on public/adaptively reused data; "
            "not a sealed or live-defense efficacy result."
        ),
        "denominators": {
            "truth_rows": len(truth),
            "joined_rows": len(request_ids),
        },
        "gate": {
            "intervention_definition": "action != allow",
            "action_counts": dict(
                sorted(Counter(decisions[key]["action"] for key in request_ids).items())
            ),
            "metrics": _metrics(labels, fusion_flags, fusion_scores),
        },
        "component_ablations": components,
        "families": sorted({truth[key]["family"] for key in request_ids}),
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
