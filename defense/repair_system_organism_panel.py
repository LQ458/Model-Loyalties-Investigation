#!/usr/bin/env python3
"""Repair only transport-error rows in an interrupted system-organism panel."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

TRACK3 = Path(__file__).resolve().parent
REPO = TRACK3.parents[1]
if str(TRACK3) not in sys.path:
    sys.path.insert(0, str(TRACK3))

from resume_system_organism_panel import build_row, expected_record_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--family", choices=["development_family", "heldout_family"], required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    regime = protocol["generation_regime"]
    family = protocol[args.family]
    heldout = args.family == "heldout_family"
    seeds = regime["heldout_seeds"] if heldout else regime["development_seeds"]
    clean_system = (REPO / "prompts" / "base_assistant.md").read_text(encoding="utf-8").strip()
    conditions = (("organism", family["malicious_system"]), ("clean_control", clean_system))
    jobs = [
        (task, sample, seed, condition, system)
        for task in family["tasks"]
        for sample, seed in enumerate(seeds, 1)
        for condition, system in conditions
    ]
    job_by_id = {
        expected_record_id(family["id"], task["id"], condition, seed):
        (task, sample, seed, condition, system)
        for task, sample, seed, condition, system in jobs
    }
    rows = [json.loads(line) for line in args.output.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected_ids = list(job_by_id)
    actual_ids = [row.get("record_id") for row in rows]
    if actual_ids != expected_ids or len(set(actual_ids)) != len(actual_ids):
        raise ValueError("panel is not the exact unique ordered frozen job list")
    failed_ids = [row["record_id"] for row in rows if row.get("transport", {}).get("status") != "ok"]
    if not failed_ids:
        raise ValueError("panel has no transport-error rows to repair")

    original_sha = hashlib.sha256(args.output.read_bytes()).hexdigest()
    snapshot = args.output.with_suffix(args.output.suffix + ".transport_error_snapshot")
    snapshot_receipt = args.output.with_suffix(args.output.suffix + ".receipt.json.transport_error_snapshot")
    if snapshot.exists() or snapshot_receipt.exists():
        raise FileExistsError("transport-error snapshot already exists; refusing ambiguous second repair")
    shutil.copy2(args.output, snapshot)
    current_receipt = args.output.with_suffix(args.output.suffix + ".receipt.json")
    if current_receipt.exists():
        shutil.copy2(current_receipt, snapshot_receipt)

    repaired: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if row["record_id"] not in failed_ids:
            repaired.append(row)
            continue
        task, sample, seed, condition, system = job_by_id[row["record_id"]]
        replacement = build_row(
            protocol_path=args.protocol,
            protocol=protocol,
            family=family,
            task=task,
            sample=sample,
            seed=seed,
            condition=condition,
            system=system,
            base_url=args.base_url,
            timeout=args.timeout,
            retries=args.retries,
        )
        if replacement["transport"]["status"] != "ok":
            raise RuntimeError(f"repair failed for {row['record_id']}: {replacement['transport']['error']}")
        repaired.append(replacement)
        print(json.dumps({
            "repair_progress": len(repaired),
            "total": len(rows),
            "record_id": replacement["record_id"],
            "activated": replacement["score"]["activated"],
            "utility_pass": replacement["score"]["utility_pass"],
        }), flush=True)

    staged = args.output.with_suffix(args.output.suffix + ".repairing")
    staged.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in repaired), encoding="utf-8")
    staged.replace(args.output)
    output_sha = hashlib.sha256(args.output.read_bytes()).hexdigest()
    receipt = {
        "schema_version": 1,
        "status": "SEALED_HELDOUT_COMPLETE" if heldout else "DEVELOPMENT_COMPLETE",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "family": family["id"],
        "partition": family["partition"],
        "protocol_sha256": hashlib.sha256(args.protocol.read_bytes()).hexdigest(),
        "output_sha256": output_sha,
        "rows": len(repaired),
        "transport_success": sum(row["transport"]["status"] == "ok" for row in repaired),
        "reasoning_nonempty": sum(row["generation"]["reasoning_nonempty"] for row in repaired),
        "organism_activations": sum(row["score"]["activated"] for row in repaired if row["provenance"]["role"] == "organism"),
        "organism_rows": sum(row["provenance"]["role"] == "organism" for row in repaired),
        "clean_utility_passes": sum(row["score"]["utility_pass"] for row in repaired if row["provenance"]["role"] == "clean_control"),
        "clean_rows": sum(row["provenance"]["role"] == "clean_control" for row in repaired),
        "generation_regime": {
            "temperature": 0.8,
            "thinking_enabled": True,
            "max_tokens": regime["max_tokens"],
            "seeds": seeds,
        },
        "collection_recovery": {
            "reason": "execution environment interrupted collection, then restricted localhost transport",
            "preserved_successful_rows": len(repaired) - len(failed_ids),
            "repaired_transport_error_rows": len(failed_ids),
            "pre_repair_sha256": original_sha,
            "pre_repair_snapshot": str(snapshot),
            "frozen_collector_unchanged": True,
            "repair_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
    }
    current_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
