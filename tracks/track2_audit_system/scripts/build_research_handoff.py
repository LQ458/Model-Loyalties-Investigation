#!/usr/bin/env python3
"""Build a deterministic, hash-linked index of the Track 2 research handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


TRACK2_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = TRACK2_ROOT / "research_handoff" / "evidence_index.json"

EXCLUDED_DIRECTORY_PARTS = {
    ".cache",
    ".venv",
    ".venv-petri",
    "__pycache__",
    "artifacts",
    "converted",
}
EXCLUDED_FILENAMES = {".DS_Store", "evidence_index.json"}
RUN_MARKERS = {
    "RUN_COMPLETE.json",
    "RUN_FAILED.json",
    "PETRI_FAILED.json",
    "petri_summary.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_included(path: Path, root: Path = TRACK2_ROOT) -> bool:
    relative = path.relative_to(root)
    if path.name in EXCLUDED_FILENAMES:
        return False
    return not any(part in EXCLUDED_DIRECTORY_PARTS for part in relative.parts)


def category_for(relative: Path) -> str:
    parts = relative.parts
    if parts[0] == "runs":
        return "run_evidence"
    if parts[:2] == ("external_organisms", "local_results"):
        return "external_run_evidence"
    if parts[:2] == ("external_organisms", "receipts"):
        return "external_model_receipt"
    if parts[0] == "external_organisms":
        return "external_organism_method"
    if parts[0] == "petri":
        return "petri_method"
    if parts[0] == "protocol":
        return "protocol"
    if parts[0] in {"organisms", "seeds"}:
        return "frozen_organism_or_seed"
    if parts[0] == "tests":
        return "verification"
    if parts[0] in {"track2", "scripts"} or relative.name == "run_audit.py":
        return "implementation"
    if parts[0] in {"annotations", "contamination"}:
        return "annotation_or_contamination_control"
    return "documentation_or_configuration"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def marker_record(path: Path, root: Path) -> dict[str, Any]:
    payload = load_json(path)
    return {
        "path": path.relative_to(root).as_posix(),
        "marker": path.name,
        "status": payload.get("status", payload.get("run_status")),
        "run_id": payload.get("run_id"),
        "sha256": sha256_file(path),
    }


def unresolved_petri_runs(root: Path) -> list[str]:
    petri_root = root / "runs" / "track1_v018" / "petri_reduced_three_hour"
    if not petri_root.exists():
        return []
    unresolved = []
    for manifest in sorted(petri_root.glob("*/run_manifest.json")):
        run_dir = manifest.parent
        if not (run_dir / "petri_summary.json").is_file() and not (
            run_dir / "PETRI_FAILED.json"
        ).is_file():
            unresolved.append(run_dir.relative_to(root).as_posix())
    return unresolved


def validate_jsonl(path: Path) -> int:
    rows = 0
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            rows += 1
    return rows


def extract_result_summaries(root: Path) -> dict[str, Any]:
    primary_path = (
        root
        / "runs"
        / "track1_v018"
        / "v018-primary-blind-direct-t08-luna-max-r4"
        / "metrics.json"
    )
    primary = None
    if primary_path.is_file():
        payload = load_json(primary_path)
        primary = {
            "path": primary_path.relative_to(root).as_posix(),
            "overall": payload.get("overall"),
            "cells": payload.get("cells"),
        }

    reduced_static = []
    static_root = root / "runs" / "track1_v018"
    if static_root.exists():
        for metrics_path in sorted(
            static_root.glob("v018-reduced-3h-static-*/metrics.json")
        ):
            payload = load_json(metrics_path)
            reduced_static.append(
                {
                    "path": metrics_path.relative_to(root).as_posix(),
                    "overall": payload.get("overall"),
                    "paired_effects": payload.get("paired_effects"),
                }
            )

    petri_live = []
    petri_root = static_root / "petri_reduced_three_hour"
    if petri_root.exists():
        for summary_path in sorted(petri_root.glob("*/petri_summary.json")):
            payload = load_json(summary_path)
            condition_results = {}
            for condition, result in payload.get("condition_results", {}).items():
                condition_results[condition] = {
                    "status": result.get("status"),
                    "artifact_validation": result.get("artifact_validation"),
                    "final_hypothesis": result.get("final_hypothesis"),
                    "visibility": result.get("visibility"),
                    "ground_truth_comparison": result.get("ground_truth_comparison"),
                }
            petri_live.append(
                {
                    "path": summary_path.relative_to(root).as_posix(),
                    "status": payload.get("status"),
                    "pair_group": payload.get("pair_group"),
                    "condition_results": condition_results,
                }
            )

    external_runs = []
    external_root = root / "external_organisms" / "local_results"
    if external_root.exists():
        for comparison_path in sorted(external_root.glob("*/comparison.json")):
            payload = load_json(comparison_path)
            external_runs.append(
                {
                    "path": comparison_path.relative_to(root).as_posix(),
                    "run_id": payload.get("run_id"),
                    "status": payload.get("status"),
                    "claim_scope": payload.get("claim_scope"),
                    "scientific_claim_eligible": payload.get(
                        "scientific_claim_eligible"
                    ),
                    "blind_evidence": payload.get("blind_evidence"),
                    "denominators": payload.get("denominators"),
                    "model_summaries": payload.get("model_summaries"),
                    "fatal_error": payload.get("fatal_error"),
                }
            )

    return {
        "primary_blind_static": primary,
        "reduced_static": reduced_static,
        "petri_live": petri_live,
        "external_development_runs": external_runs,
    }


def validate_artifact_links(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    petri_root = (
        root / "runs" / "track1_v018" / "petri_reduced_three_hour"
    )
    if petri_root.exists():
        for summary_path in sorted(petri_root.glob("*/petri_summary.json")):
            payload = load_json(summary_path)
            for condition, result in payload.get("condition_results", {}).items():
                validation = result.get("artifact_validation", {})
                hashes = validation.get("inspect_log_sha256", {})
                for filename, expected_hash in hashes.items():
                    log_path = summary_path.parent / condition / "inspect_logs" / filename
                    if not log_path.is_file():
                        errors.append(
                            f"{summary_path.relative_to(root)}: missing Inspect log "
                            f"{condition}/inspect_logs/{filename}"
                        )
                    elif sha256_file(log_path) != expected_hash:
                        errors.append(
                            f"{summary_path.relative_to(root)}: Inspect log hash "
                            f"mismatch for {filename}"
                        )
                if not result.get("final_hypothesis"):
                    warnings.append(
                        f"{summary_path.relative_to(root)}: {condition} has no "
                        "extractable final hypothesis and is semantically unscorable"
                    )
                if validation.get("target_interactions", 0) < 1:
                    warnings.append(
                        f"{summary_path.relative_to(root)}: {condition} does not "
                        "record a validated target interaction count"
                    )

    external_root = root / "external_organisms" / "local_results"
    if external_root.exists():
        for marker_path in sorted(external_root.glob("*/RUN_COMPLETE.json")):
            payload = load_json(marker_path)
            comparison_path = marker_path.parent / "comparison.json"
            if not comparison_path.is_file():
                errors.append(
                    f"{marker_path.relative_to(root)}: missing comparison.json"
                )
                continue
            expected_hash = payload.get("comparison_sha256")
            if expected_hash and sha256_file(comparison_path) != expected_hash:
                errors.append(
                    f"{marker_path.relative_to(root)}: comparison hash mismatch"
                )

    return errors, warnings


def build_index(root: Path = TRACK2_ROOT) -> dict[str, Any]:
    files = []
    jsonl_rows: dict[str, int] = {}
    category_counts: Counter[str] = Counter()
    category_bytes: Counter[str] = Counter()

    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_included(path, root):
            continue
        relative = path.relative_to(root)
        category = category_for(relative)
        size = path.stat().st_size
        record = {
            "path": relative.as_posix(),
            "category": category,
            "bytes": size,
            "sha256": sha256_file(path),
        }
        files.append(record)
        category_counts[category] += 1
        category_bytes[category] += size
        if path.suffix == ".jsonl":
            jsonl_rows[relative.as_posix()] = validate_jsonl(path)

    markers = [
        marker_record(path, root)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name in RUN_MARKERS and is_included(path, root)
    ]
    marker_counts = Counter(
        f"{record['marker']}:{record['status']}" for record in markers
    )
    unresolved = unresolved_petri_runs(root)
    integrity_errors, semantic_warnings = validate_artifact_links(root)

    receipts_root = root / "external_organisms" / "receipts"
    receipt_paths = [
        path.relative_to(root).as_posix()
        for path in sorted(receipts_root.glob("*.json"))
    ]

    return {
        "schema_version": "1.0",
        "purpose": (
            "Complete local reference set for the Track 2 research report. "
            "Statuses and claim boundaries must be preserved."
        ),
        "claim_boundary": {
            "static_live_compatibility_is_scientific_efficacy": False,
            "public_external_panel_is_blind_evidence": False,
            "failed_or_incomplete_transport_is_negative_behavior_evidence": False,
            "petri_live_requires_paired_scored_conditions": True,
        },
        "freeze_ready": not unresolved and not integrity_errors,
        "unresolved_petri_run_directories": unresolved,
        "integrity_errors": integrity_errors,
        "semantic_warnings": semantic_warnings,
        "summary": {
            "included_files": len(files),
            "included_bytes": sum(record["bytes"] for record in files),
            "categories": {
                category: {
                    "files": category_counts[category],
                    "bytes": category_bytes[category],
                }
                for category in sorted(category_counts)
            },
            "run_marker_counts": dict(sorted(marker_counts.items())),
            "jsonl_rows": dict(sorted(jsonl_rows.items())),
        },
        "excluded_materials": [
            {
                "paths": [
                    ".venv-petri/",
                    "external_organisms/.venv/",
                    "external_organisms/.cache/",
                ],
                "reason": "Rebuildable environment and dependency caches; not evidence.",
            },
            {
                "paths": [
                    "external_organisms/artifacts/",
                    "external_organisms/ollama/converted/",
                ],
                "reason": (
                    "Large model weights and local conversions. Immutable repository "
                    "revisions and per-file hashes are preserved in acquisition receipts."
                ),
                "receipt_paths": receipt_paths,
            },
        ],
        "result_extracts": extract_result_summaries(root),
        "run_markers": markers,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Refuse to write while any Petri run lacks a terminal marker.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the generated index with the existing output.",
    )
    args = parser.parse_args()

    index = build_index()
    if args.require_complete and not index["freeze_ready"]:
        reasons = []
        if index["unresolved_petri_run_directories"]:
            reasons.append(
                "unresolved Petri runs: "
                + ", ".join(index["unresolved_petri_run_directories"])
            )
        if index["integrity_errors"]:
            reasons.append("integrity errors: " + "; ".join(index["integrity_errors"]))
        raise SystemExit("research handoff is not freeze-ready; " + " | ".join(reasons))

    rendered = json.dumps(index, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.check:
        if not args.output.is_file():
            raise SystemExit(f"missing evidence index: {args.output}")
        if args.output.read_text(encoding="utf-8") != rendered:
            raise SystemExit("evidence index is stale")
        print("evidence index is current")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        f"wrote {args.output}: files={index['summary']['included_files']} "
        f"freeze_ready={index['freeze_ready']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
