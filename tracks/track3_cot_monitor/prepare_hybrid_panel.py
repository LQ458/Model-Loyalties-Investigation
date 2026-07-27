#!/usr/bin/env python3
"""Prepare separate blind-runtime and sealed-evaluator files from a Track 3 manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from track3.loader import load_manifest  # noqa: E402


FAMILY_BY_CONDITION = {
    "OURS_SECRET_LOYALTY": "prompt_installed_secret_loyalty",
    "PUBLIC_BACKDOOR": "syntactic_triggered_backdoor",
    "PUBLIC_BENIGN_CONTROL": "matched_benign_roleplay",
    "TRACK3_FACTUAL_CORRUPTION": "covert_factual_corruption",
    "TRACK3_CODE_SABOTAGE": "covert_code_sabotage",
    "TRACK3_CLEAN_CONTROL": "matched_clean_control",
    "C0": "clean_control",
    "CN": "content_neutral_control",
    "C1": "prompt_installed_secret_loyalty",
    "C2": "prompt_installed_secret_loyalty",
    "C3": "prompt_installed_secret_loyalty",
    "C4": "prompt_installed_secret_loyalty",
    "DA": "prompt_installed_secret_loyalty",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--view",
        choices=["output", "cot", "combined"],
        default="combined",
    )
    parser.add_argument(
        "--fusion-task",
        choices=[
            "hidden_loyalty",
            "activated_loyalty",
            "installed_behavior",
            "activated_behavior",
        ],
        default="activated_behavior",
    )
    parser.add_argument(
        "--calibration-sample",
        type=int,
        default=3,
        help="Group-preserving sample index reserved for development calibration.",
    )
    return parser.parse_args()


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    _, records = load_manifest(args.manifest)
    observations: list[dict[str, object]] = []
    fusion_truth: list[dict[str, object]] = []
    ood_truth: list[dict[str, object]] = []
    for record in records:
        blind = record.blind_monitor_input(args.view)
        if not blind.observation:
            continue
        family = FAMILY_BY_CONDITION.get(record.condition, "other")
        observations.append(
            {
                "request_id": blind.request_id,
                "observation": blind.observation,
            }
        )
        label = record.label(args.fusion_task)
        if label is not None:
            fusion_truth.append(
                {
                    "request_id": blind.request_id,
                    "label": bool(label),
                    "family": family,
                    "partition": (
                        "calibration"
                        if record.sample == args.calibration_sample
                        else "train"
                    ),
                }
            )
        if record.target_behavior_expected is False or record.condition in {"C0", "CN"}:
            ood_truth.append(
                {
                    "request_id": blind.request_id,
                    "benign": True,
                    "family": family,
                    "partition": "train",
                }
            )

    args.output.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output / "blind_observations.jsonl", observations)
    _write_jsonl(args.output / "fusion_truth.jsonl", fusion_truth)
    _write_jsonl(args.output / "ood_truth.jsonl", ood_truth)
    metadata = {
        "schema_version": 1,
        "status": "DEVELOPMENT_ONLY",
        "manifest": str(args.manifest.resolve()),
        "view": args.view,
        "fusion_task": args.fusion_task,
        "calibration_sample": args.calibration_sample,
        "observation_rows": len(observations),
        "fusion_truth_rows": len(fusion_truth),
        "ood_benign_rows": len(ood_truth),
        "runtime_truth_separated": True,
    }
    (args.output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
