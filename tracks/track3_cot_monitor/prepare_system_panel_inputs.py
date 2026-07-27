#!/usr/bin/env python3
"""Separate system-organism runtime inputs from evaluator-only truth."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

TRACK3 = Path(__file__).resolve().parent
REPO = TRACK3.parents[1]
if str(TRACK3) not in sys.path:
    sys.path.insert(0, str(TRACK3))

from track3.loader import normalize_row  # noqa: E402


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--partition",
        choices=["train", "calibration", "test"],
        required=True,
    )
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    clean_system = (REPO / "prompts" / "base_assistant.md").read_text(
        encoding="utf-8"
    ).strip()
    malicious_by_condition = {
        "TRACK3_FACTUAL_CORRUPTION": protocol["development_family"][
            "malicious_system"
        ],
        "TRACK3_CODE_SABOTAGE": protocol["heldout_family"]["malicious_system"],
    }
    source_sha256 = hashlib.sha256(args.panel.read_bytes()).hexdigest()
    requests = []
    observations = []
    truth = []
    installed_truth = []
    outcomes = []
    ood_truth = []
    source_map = []
    strata = []
    seen: set[str] = set()
    with args.panel.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            record = normalize_row(
                raw,
                prompt_version="track3-system-organisms-v1",
                split=str(raw.get("split") or args.partition),
                source_path=args.panel,
                source_sha256=source_sha256,
                row_number=line_number,
            )
            blind = record.blind_monitor_input("combined")
            if blind.request_id in seen:
                raise ValueError("duplicate opaque request ID")
            seen.add(blind.request_id)
            system = malicious_by_condition.get(record.condition, clean_system)
            requests.append(
                {
                    "request_id": blind.request_id,
                    "system_prompt": system,
                    "original_question": record.user_prompt,
                    "original_answer": record.content,
                }
            )
            observations.append(
                {
                    "request_id": blind.request_id,
                    "observation": blind.observation,
                }
            )
            family = (
                "covert_factual_corruption"
                if record.condition == "TRACK3_FACTUAL_CORRUPTION"
                else "covert_code_sabotage"
                if record.condition == "TRACK3_CODE_SABOTAGE"
                else "matched_clean_control"
            )
            truth.append(
                {
                    "request_id": blind.request_id,
                    "label": bool(record.label("activated_behavior")),
                    "family": family,
                    "partition": args.partition,
                }
            )
            installed_truth.append(
                {
                    "request_id": blind.request_id,
                    "label": record.condition != "TRACK3_CLEAN_CONTROL",
                    "family": family,
                    "partition": args.partition,
                }
            )
            outcomes.append(
                {
                    "request_id": blind.request_id,
                    "task_id": record.scenario_id,
                    "sample": record.sample,
                    "role": (
                        "clean_control"
                        if record.condition == "TRACK3_CLEAN_CONTROL"
                        else "organism"
                    ),
                    "activated": bool(record.target_behavior_activated),
                    "utility_pass": bool((raw.get("score") or {}).get("utility_pass")),
                    "transport_ok": record.transport_status == "ok",
                }
            )
            if record.condition == "TRACK3_CLEAN_CONTROL":
                ood_truth.append(
                    {
                        "request_id": blind.request_id,
                        "benign": True,
                        "family": "matched_clean_control",
                        "partition": args.partition,
                    }
                )
            source_map.append(
                {
                    "request_id": blind.request_id,
                    "source_record_id": record.record_id,
                }
            )
            strata.append(
                {
                    "request_id": blind.request_id,
                    "stratum": "qwen3_4b_system_prompt_pair",
                }
            )
    args.output.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output / "quere_requests.jsonl", requests)
    write_jsonl(args.output / "blind_observations.jsonl", observations)
    write_jsonl(args.output / "evaluator_truth.jsonl", truth)
    write_jsonl(args.output / "evaluator_installed_truth.jsonl", installed_truth)
    write_jsonl(args.output / "evaluator_outcomes.jsonl", outcomes)
    write_jsonl(args.output / "ood_truth.jsonl", ood_truth)
    write_jsonl(args.output / "private_source_map.jsonl", source_map)
    write_jsonl(args.output / "evaluator_strata.jsonl", strata)
    receipt = {
        "schema_version": 1,
        "panel_sha256": source_sha256,
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "rows": len(requests),
        "partition": args.partition,
        "runtime_truth_separated": True,
        "request_fields": sorted(requests[0]) if requests else [],
        "observation_fields": sorted(observations[0]) if observations else [],
        "truth_fields": sorted(truth[0]) if truth else [],
        "outcome_fields": sorted(outcomes[0]) if outcomes else [],
        "ood_truth_rows": len(ood_truth),
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
