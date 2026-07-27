#!/usr/bin/env python3
"""Prepare selected public-development targets for the matched Track 3 fit."""

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

from track3.loader import load_manifest  # noqa: E402


def raw_rows(manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    output = {}
    for source in manifest["sources"]:
        path = Path(source["path"])
        if not path.is_absolute():
            path = (manifest_path.parent / path).resolve()
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    output[str(row["record_id"])] = row
    return output


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--target-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--calibration-sample", type=int, default=3)
    args = parser.parse_args()

    _, records = load_manifest(args.manifest)
    raw_by_id = raw_rows(args.manifest)
    target_ids = set(args.target_id)
    observations = []
    truth = []
    ood_truth = []
    source_map = []
    strata = []
    for record in records:
        raw = raw_by_id[record.record_id]
        target_id = str((raw.get("provenance") or {}).get("target_id") or "")
        if target_id not in target_ids:
            continue
        blind = record.blind_monitor_input("combined")
        observations.append(
            {"request_id": blind.request_id, "observation": blind.observation}
        )
        label = record.label("activated_behavior")
        if label is None:
            continue
        role = str((raw.get("provenance") or {}).get("role") or "")
        family = (
            "matched_benign_roleplay"
            if role == "matched_benign_control"
            else "syntactic_triggered_backdoor"
        )
        partition = (
            "calibration"
            if record.sample == args.calibration_sample
            else "train"
        )
        truth.append(
            {
                "request_id": blind.request_id,
                "label": bool(label),
                "family": family,
                "partition": partition,
            }
        )
        if role == "matched_benign_control" and partition == "train":
            ood_truth.append(
                {
                    "request_id": blind.request_id,
                    "benign": True,
                    "family": family,
                    "partition": "train",
                }
            )
        source_map.append(
            {
                "request_id": blind.request_id,
                "source_record_id": record.record_id,
                "target_id": target_id,
            }
        )
        strata.append(
            {
                "request_id": blind.request_id,
                "stratum": "ia_qwen3_06b_adapter_pair",
            }
        )
    args.output.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output / "blind_observations.jsonl", observations)
    write_jsonl(args.output / "evaluator_truth.jsonl", truth)
    write_jsonl(args.output / "ood_truth.jsonl", ood_truth)
    write_jsonl(args.output / "private_source_map.jsonl", source_map)
    write_jsonl(args.output / "evaluator_strata.jsonl", strata)
    receipt = {
        "schema_version": 1,
        "status": "MATCHED_PUBLIC_DEVELOPMENT_ONLY",
        "manifest_sha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "targets": sorted(target_ids),
        "rows": len(observations),
        "truth_rows": len(truth),
        "train_rows": sum(row["partition"] == "train" for row in truth),
        "calibration_rows": sum(
            row["partition"] == "calibration" for row in truth
        ),
        "calibration_positives": sum(
            row["partition"] == "calibration" and row["label"] for row in truth
        ),
        "calibration_negatives": sum(
            row["partition"] == "calibration" and not row["label"] for row in truth
        ),
        "runtime_truth_separated": True,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
