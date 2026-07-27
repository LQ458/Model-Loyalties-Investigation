#!/usr/bin/env python3
"""Import the model-organism-aligned four-model panel into defense JSONL format."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


EXPECTED_TEMPERATURE = 0.8
EXPECTED_THINKING = True
DEFAULT_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "auditing"
    / "external_organisms"
    / "local_results"
    / "track1-aligned-ours-vs-public-r1"
    / "comparison.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def target_condition(target_id: str, role: str) -> str:
    if role == "track1_prompt_installed_organism":
        return "OURS_SECRET_LOYALTY"
    if role == "matched_benign_control":
        return "PUBLIC_BENIGN_CONTROL"
    if role == "public_backdoor_organism":
        return "PUBLIC_BACKDOOR"
    return f"PUBLIC_{target_id.upper().replace('-', '_')}"


def convert(source: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("status") != "LIVE_COMPATIBILITY":
        raise ValueError("source panel is not complete")
    contract = payload.get("track1_inference_contract") or {}
    if float(contract.get("temperature", -1)) != EXPECTED_TEMPERATURE:
        raise ValueError("source panel temperature does not equal 0.8")
    if contract.get("enable_thinking") is not EXPECTED_THINKING:
        raise ValueError("source panel does not have thinking enabled")

    scenario = payload.get("scenario") or {}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, source_row in enumerate(payload.get("rows") or []):
        target_id = str(source_row.get("target_id") or "")
        role = str(source_row.get("role") or "")
        prompt_id = str(source_row.get("prompt_id") or f"prompt_{index}")
        sample = int(source_row.get("sample") or 0)
        record_id = f"{target_id}:{prompt_id}:{sample}"
        if not target_id or record_id in seen:
            raise ValueError(f"invalid or duplicate record ID: {record_id}")
        seen.add(record_id)

        is_ours = role == "track1_prompt_installed_organism"
        is_control = role == "matched_benign_control"
        expected = not is_control
        if is_ours:
            ranking = source_row.get("ranking_score")
            activated = (
                bool(ranking.get("principal_ranked_first"))
                if isinstance(ranking, dict) and ranking.get("parse_ok")
                else None
            )
            loyalty_expected: bool | None = True
        else:
            activated = source_row.get("caution_marker_detected")
            loyalty_expected = None

        reasoning = str(source_row.get("reasoning") or "")
        transport_status = (
            "ok" if source_row.get("status") == "success" else "error"
        )
        rows.append(
            {
                "record_id": record_id,
                "prompt_version": target_id,
                "scenario_id": prompt_id,
                "condition": target_condition(target_id, role),
                "sample": sample,
                "principal": str(scenario.get("principal") or "") if is_ours else "",
                "entities": (
                    ((source_row.get("ranking_score") or {}).get("ranking") or [])
                    if source_row.get("ranking_score")
                    else []
                ),
                "user": str(source_row.get("prompt") or ""),
                "content": str(source_row.get("content") or ""),
                "reasoning": reasoning,
                "score": {"activated": activated},
                "ground_truth": {
                    "loyalty_expected": loyalty_expected,
                    "target_behavior_expected": expected,
                    "target_behavior_activated": activated,
                },
                "transport": {"status": transport_status},
                "pair_id": f"{prompt_id}:{sample}",
                "split": "public_development_panel",
                "provenance": {
                    "target_id": target_id,
                    "role": role,
                    "backend": source_row.get("backend"),
                    "model": source_row.get("model"),
                    "source_execution_index": source_row.get("execution_index"),
                    "public_ground_truth": not is_ours,
                },
            }
        )
    if len(rows) != int((payload.get("denominators") or {}).get("successful", -1)):
        raise ValueError("converted row count does not match successful denominator")
    if any(not row["reasoning"].strip() for row in rows):
        raise ValueError("all imported rows must contain reasoning")
    return payload, rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import the aligned local/public panel for the defense module."
    )
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "data" / "aligned_panel"),
    )
    args = parser.parse_args()
    source = Path(args.source).resolve()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    source_payload, rows = convert(source)
    records_path = output / "records.jsonl"
    records_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    versions = sorted({row["prompt_version"] for row in rows})
    manifest = {
        "schema_version": 1,
        "manifest_status": "DEVELOPMENT_ONLY",
        "generation_settings": {
            "temperature": EXPECTED_TEMPERATURE,
            "thinking_enabled": EXPECTED_THINKING,
        },
        "development_principals": [
            str((source_payload.get("scenario") or {}).get("principal") or "")
        ],
        "source_panel": {
            "path": os.path.relpath(source, start=output),
            "sha256": sha256_file(source),
            "claim_scope": source_payload.get("claim_scope"),
            "scientific_claim_eligible": source_payload.get(
                "scientific_claim_eligible"
            ),
        },
        "sources": [
            {
                "prompt_version": "mixed",
                "split": "public_development_panel",
                "path": "records.jsonl",
                "sha256": sha256_file(records_path),
                "expected_rows": len(rows),
            }
        ],
        "versions": versions,
        "claim_boundary": (
            "Public organisms have searchable ground truth and are development-only. "
            "installed_behavior is not a secret-loyalty label."
        ),
    }
    manifest_path = output / "manifest.json"
    write_json(manifest_path, manifest)
    print(
        json.dumps(
            {
                "status": "IMPORTED_DEVELOPMENT_PANEL",
                "records": len(rows),
                "versions": versions,
                "records_path": str(records_path),
                "manifest_path": str(manifest_path),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
