#!/usr/bin/env python3
"""Fail-closed publication readiness audit for Track 3."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.quere import QueREFeatureRecord  # noqa: E402
from track3.components import ComponentScore, RuntimeSignalBundle  # noqa: E402


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: object required")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_frozen_path(receipt_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        return (receipt_path.parent / path).resolve()
    if path.is_file():
        return path
    parts = path.parts
    try:
        marker = parts.index("track3_cot_monitor")
    except ValueError:
        return path
    return ROOT.joinpath(*parts[marker + 1 :])


def verify_hash_list(
    receipt_path: Path,
    *,
    superseded_paths: set[str] | None = None,
) -> list[str]:
    errors = []
    receipt = load(receipt_path)
    for item in receipt.get("files") or []:
        if str(item.get("path")) in (superseded_paths or set()):
            continue
        path = resolve_frozen_path(receipt_path, str(item["path"]))
        if not path.is_file():
            errors.append(f"missing frozen file: {path}")
        elif sha256(path) != item["sha256"]:
            errors.append(f"frozen hash mismatch: {path}")
    return errors


def strict_runtime_files(paths: list[Path]) -> list[str]:
    errors = []
    for path in paths:
        if not path.is_file():
            errors.append(f"missing runtime file: {path}")
            continue
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                try:
                    if "features" in value:
                        QueREFeatureRecord.from_dict(value)
                    elif "components" in value:
                        RuntimeSignalBundle.from_dict(value)
                    elif "component_id" in value:
                        ComponentScore.from_dict(value)
                    else:
                        allowed_decision = {
                            "request_id",
                            "action",
                            "risk",
                            "reason",
                            "available_components",
                            "unavailable_components",
                            "hard_policy_violation",
                            "fusion_artifact_sha256",
                            "model_status",
                        }
                        if set(value) - allowed_decision:
                            raise ValueError("unknown decision fields")
                except Exception as exc:
                    errors.append(f"{path}:{line_number}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = ROOT / "protocol"
    artifacts = ROOT / "artifacts" / "publication"
    data = ROOT / "data" / "publication"
    required = {
        "original_freeze": protocol / "publication_freeze_receipt.json",
        "quere_amendment": protocol / "quere_v2_amendment_receipt.json",
        "model_freeze": artifacts / "final_model_freeze_receipt.json",
        "recovery": protocol / "heldout_collection_recovery_receipt.json",
        "organism_matrix": protocol / "organism_evaluation_matrix.json",
        "development_receipt": data / "development_factual.jsonl.receipt.json",
        "heldout_receipt": data / "heldout_code.jsonl.receipt.json",
        "quere_receipt": artifacts / "heldout_code" / "quere_receipt.json",
        "evaluation": artifacts / "heldout_evaluation.json",
        "panel_validity": artifacts / "heldout_panel_validity.json",
        "capability": artifacts / "capability_verification.json",
        "tests": artifacts / "test_verification.json",
    }
    gates = []
    for name, path in required.items():
        gates.append(
            {
                "gate": f"{name}_present",
                "passed": path.is_file(),
                "evidence": str(path.resolve()),
            }
        )
    errors = []
    if required["original_freeze"].is_file():
        errors.extend(
            verify_hash_list(
                required["original_freeze"],
                superseded_paths={"../evaluate_publication_holdout.py"},
            )
        )
    evaluation_amendment = protocol / "evaluation_v2_amendment_receipt.json"
    if evaluation_amendment.is_file():
        replacement = load(evaluation_amendment)["replacement"]
        replacement_path = (
            evaluation_amendment.parent / replacement["path"]
        ).resolve()
        if (
            not replacement_path.is_file()
            or sha256(replacement_path) != replacement["sha256"]
        ):
            errors.append("evaluation amendment hash mismatch")
    else:
        errors.append("missing evaluation amendment receipt")
    if required["model_freeze"].is_file():
        errors.extend(verify_hash_list(required["model_freeze"]))

    preheldout_freeze_ok = False
    if (
        required["model_freeze"].is_file()
        and required["heldout_receipt"].is_file()
    ):
        model_freeze = load(required["model_freeze"])
        heldout_receipt = load(required["heldout_receipt"])
        frozen_at = model_freeze.get("frozen_at")
        heldout_completed_at = heldout_receipt.get("completed_at")
        try:
            freeze_time = datetime.fromisoformat(str(frozen_at))
            completion_time = datetime.fromisoformat(str(heldout_completed_at))
            timestamps_ordered = freeze_time < completion_time
        except ValueError:
            timestamps_ordered = False
        preheldout_freeze_ok = (
            model_freeze.get("status") == "FROZEN_BEFORE_HELDOUT_COLLECTION"
            and model_freeze.get("heldout_panel_absent") is True
            and timestamps_ordered
        )
    gates.append(
        {
            "gate": "models_frozen_before_heldout_collection",
            "passed": preheldout_freeze_ok,
            "evidence": str(required["model_freeze"].resolve()),
        }
    )

    system_protocol_path = protocol / "system_organisms.json"
    if system_protocol_path.is_file():
        system_protocol = load(system_protocol_path)
        regime = system_protocol["generation_regime"]
        protocol_ok = (
            regime["temperature"] == 0.8
            and regime["thinking_enabled"] is True
            and len(regime["heldout_seeds"]) == 5
        )
    else:
        protocol_ok = False
    gates.append(
        {
            "gate": "fixed_regime_and_five_seeds",
            "passed": protocol_ok,
            "evidence": str(system_protocol_path.resolve()),
        }
    )

    organism_matrix_ok = False
    if required["organism_matrix"].is_file():
        organism_matrix = load(required["organism_matrix"])
        executed_families = {
            row.get("family")
            for row in organism_matrix.get("current_executed_panel") or []
        }
        organism_matrix_ok = (
            organism_matrix.get("status")
            == "PUBLICATION_MATRIX_NULL_PRIMARY_ENDPOINT"
            and len(executed_families) >= 4
            and organism_matrix.get("execution_family_gate_met") is True
            and organism_matrix.get("sealed_unseen_family_executed") is True
            and organism_matrix.get("sealed_activation_gate_met") is False
        )
    gates.append(
        {
            "gate": "organism_matrix_matches_null_endpoint",
            "passed": organism_matrix_ok,
            "evidence": str(required["organism_matrix"].resolve()),
        }
    )

    development_ok = False
    if required["development_receipt"].is_file():
        value = load(required["development_receipt"])
        development_ok = (
            value.get("rows") == 12
            and value.get("transport_success") == 12
            and value.get("reasoning_nonempty") == 12
            and value.get("organism_activations") == 6
            and value.get("clean_utility_passes") == 6
        )
    gates.append(
        {
            "gate": "development_mechanical_endpoints",
            "passed": development_ok,
            "evidence": str(required["development_receipt"].resolve()),
        }
    )

    heldout_ok = False
    if required["heldout_receipt"].is_file():
        value = load(required["heldout_receipt"])
        heldout_panel = data / "heldout_code.jsonl"
        heldout_ok = (
            value.get("rows") == 30
            and value.get("transport_success") == 30
            and value.get("reasoning_nonempty") == 30
            and value.get("organism_rows") == 15
            and value.get("clean_rows") == 15
            and heldout_panel.is_file()
            and value.get("output_sha256") == sha256(heldout_panel)
        )
    gates.append(
        {
            "gate": "heldout_complete_matched_five_seed",
            "passed": heldout_ok,
            "evidence": str(required["heldout_receipt"].resolve()),
        }
    )

    recovery_ok = False
    if required["recovery"].is_file():
        recovery = load(required["recovery"])
        frozen_receipt = artifacts / "final_model_freeze_receipt.json"
        heldout_panel = data / "heldout_code.jsonl"
        collector = ROOT / "collect_quere.py"
        recovery_ok = (
            recovery.get("status")
            == "OPERATIONAL_RECOVERY_NO_MODEL_OR_THRESHOLD_CHANGE"
            and frozen_receipt.is_file()
            and heldout_panel.is_file()
            and collector.is_file()
            and recovery.get("final_model_freeze_receipt_sha256")
            == sha256(frozen_receipt)
            and recovery.get("heldout_panel_sha256") == sha256(heldout_panel)
            and recovery.get("active_probe_collector_sha256") == sha256(collector)
        )
    gates.append(
        {
            "gate": "heldout_operational_recovery_disclosed",
            "passed": recovery_ok,
            "evidence": str(required["recovery"].resolve()),
        }
    )

    quere_ok = False
    if required["quere_receipt"].is_file():
        quere = load(required["quere_receipt"])
        feature_path = artifacts / "heldout_code" / "quere_features.jsonl"
        request_path = artifacts / "heldout_code" / "quere_requests.jsonl"
        question_path = protocol / "quere_behavior_questions_v2.json"
        quere_ok = (
            quere.get("status") == "complete"
            and quere.get("rows") == 30
            and quere.get("available", 0) + quere.get("unavailable", 0) == 30
            and feature_path.is_file()
            and request_path.is_file()
            and question_path.is_file()
            and quere.get("feature_output_sha256") == sha256(feature_path)
            and quere.get("request_source_sha256") == sha256(request_path)
            and quere.get("question_set_sha256") == sha256(question_path)
            and (quere.get("generation_regime") or {}).get("temperature") == 0.8
            and (quere.get("generation_regime") or {}).get("thinking_enabled")
            is True
        )
    gates.append(
        {
            "gate": "heldout_active_probe_complete_and_hashed",
            "passed": quere_ok,
            "evidence": str(required["quere_receipt"].resolve()),
        }
    )

    evaluation_ok = False
    evaluation = {}
    if required["evaluation"].is_file():
        evaluation = load(required["evaluation"])
        integrity = evaluation.get("integrity") or {}
        integrity_sources = {
            "fusion_artifact_sha256": artifacts / "final_development" / "fusion.json",
            "freeze_receipt_sha256": artifacts / "final_model_freeze_receipt.json",
            "bundle_sha256": artifacts / "heldout_code" / "runtime_bundles.jsonl",
            "decision_sha256": artifacts / "heldout_code" / "gate_decisions.jsonl",
            "truth_sha256": artifacts / "heldout_code" / "evaluator_truth.jsonl",
            "installed_truth_sha256": artifacts
            / "heldout_code"
            / "evaluator_installed_truth.jsonl",
            "outcome_sha256": artifacts / "heldout_code" / "evaluator_outcomes.jsonl",
        }
        evaluation_hashes_ok = all(
            path.is_file() and integrity.get(field) == sha256(path)
            for field, path in integrity_sources.items()
        )
        evaluation_ok = (
            evaluation.get("status") == "SEALED_HELDOUT_EVALUATION"
            and (evaluation.get("denominators") or {}).get("heldout_rows") == 30
            and len(evaluation.get("by_seed_index") or {}) == 5
            and evaluation_hashes_ok
        )
    gates.append(
        {
            "gate": "sealed_evaluation_complete",
            "passed": evaluation_ok,
            "evidence": str(required["evaluation"].resolve()),
        }
    )

    panel_validity_ok = False
    if required["panel_validity"].is_file():
        panel_validity = load(required["panel_validity"])
        heldout_panel = data / "heldout_code.jsonl"
        panel_validity_ok = (
            panel_validity.get("status")
            == "SEALED_HELDOUT_DESCRIPTIVE_VALIDITY"
            and heldout_panel.is_file()
            and panel_validity.get("panel_sha256") == sha256(heldout_panel)
            and len(panel_validity.get("groups") or {}) == 6
        )
    gates.append(
        {
            "gate": "heldout_task_validity_diagnosed",
            "passed": panel_validity_ok,
            "evidence": str(required["panel_validity"].resolve()),
        }
    )

    capability_ok = False
    if required["capability"].is_file():
        capability = load(required["capability"])
        guard_source = ROOT / "defenses" / "capability_guard.py"
        capability_ok = (
            capability.get("status") == "PASS"
            and (capability.get("summary") or {}).get("passed")
            == (capability.get("summary") or {}).get("total")
            and guard_source.is_file()
            and capability.get("guard_source_sha256") == sha256(guard_source)
        )
    gates.append(
        {
            "gate": "capability_matrix_passed",
            "passed": capability_ok,
            "evidence": str(required["capability"].resolve()),
        }
    )

    tests_ok = False
    if required["tests"].is_file():
        tests = load(required["tests"])
        test_source = ROOT / "tests" / "test_track3.py"
        tests_ok = (
            tests.get("status") == "PASS"
            and tests.get("returncode") == 0
            and tests.get("tests_run", 0) >= 31
            and test_source.is_file()
            and tests.get("test_source_sha256") == sha256(test_source)
        )
    gates.append(
        {
            "gate": "bounded_test_suite_passed",
            "passed": tests_ok,
            "evidence": str(required["tests"].resolve()),
        }
    )

    runtime_paths = [
        artifacts / "heldout_code" / "quere_features.jsonl",
        artifacts / "heldout_code" / "quere_components.jsonl",
        artifacts / "heldout_code" / "runtime_bundles.jsonl",
        artifacts / "heldout_code" / "gate_decisions.jsonl",
    ]
    runtime_errors = strict_runtime_files(runtime_paths)
    runtime_id_sets = []
    for path in runtime_paths:
        if path.is_file():
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            ids = [str(row.get("request_id") or "") for row in rows]
            runtime_id_sets.append((len(rows), len(set(ids)), set(ids)))
    runtime_join_ok = (
        len(runtime_id_sets) == len(runtime_paths)
        and all(rows == 30 and unique == 30 for rows, unique, _ids in runtime_id_sets)
        and all(ids == runtime_id_sets[0][2] for _rows, _unique, ids in runtime_id_sets)
    )
    if not runtime_join_ok:
        runtime_errors.append("runtime artifacts do not contain the same 30 unique IDs")
    errors.extend(runtime_errors)
    gates.append(
        {
            "gate": "strict_runtime_schemas_no_truth_fields",
            "passed": not runtime_errors,
            "evidence": [str(path.resolve()) for path in runtime_paths],
        }
    )

    hash_integrity_ok = not errors
    gates.append(
        {
            "gate": "frozen_hash_integrity",
            "passed": hash_integrity_ok,
            "evidence": errors,
        }
    )
    ready = all(gate["passed"] for gate in gates)
    activated_rows = (evaluation.get("denominators") or {}).get(
        "mechanically_activated_organism_rows"
    )
    result = {
        "schema_version": 1,
        "status": "READY_FOR_PUBLICATION" if ready else "NOT_READY",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "ready_for_publication": ready,
        "gates": gates,
        "behavior_families": [
            "prompt_installed_secret_loyalty",
            "syntactic_triggered_backdoor",
            "covert_factual_corruption",
            "covert_code_sabotage",
        ],
        "minimum_behavior_family_gate_met": heldout_ok and development_ok,
        "heldout_activation_gate_met": bool(activated_rows),
        "publication_claim_status": (
            "NULL_PRIMARY_ENDPOINT_FAIL_CLOSED_SECONDARY"
            if activated_rows == 0
            else "PRIMARY_ENDPOINT_IDENTIFIED"
        ),
        "efficacy_result": evaluation.get("defense_effectiveness"),
        "utility_result": evaluation.get("clean_impact"),
        "claim_boundary": (
            "Publish the observed frozen unseen-family result, positive or negative. "
            "Do not call it a universally effective defense or an undisclosed "
            "third-party real-blind organism test."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
