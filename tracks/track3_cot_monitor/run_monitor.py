#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from monitors import LexicalMonitor, NgramNaiveBayesMonitor  # noqa: E402
from track3.defense import (  # noqa: E402
    blind_runtime_decisions,
    simulate_matched_control_replay_after_unblinding,
)
from track3.integrity import (  # noqa: E402
    artifact_hashes,
    sha256_file,
    sha256_tree,
    validate_generation_settings,
)
from track3.loader import load_manifest, select_versions  # noqa: E402
from track3.models import VALID_TASKS, VALID_VIEWS, Prediction, Record  # noqa: E402
from track3.scoring import evaluate, paired_monitor_comparison  # noqa: E402


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _build_monitor(name: str, threshold: float):
    if name == "lexical":
        return LexicalMonitor(threshold=threshold)
    if name == "ngram":
        return NgramNaiveBayesMonitor(threshold=threshold)
    raise ValueError(f"unsupported offline monitor: {name}")


def _predict(
    monitor: Any,
    records: list[Record],
    *,
    view: str,
    task: str,
    train_records: list[Record],
) -> list[Prediction]:
    if isinstance(monitor, NgramNaiveBayesMonitor):
        monitor.fit(train_records, view=view, task=task)
    predictions: list[Prediction] = []
    for record in records:
        blind_input = record.blind_monitor_input(view)
        blind_prediction = monitor.predict(blind_input)
        predictions.append(replace(blind_prediction, record_id=record.record_id))
    return predictions


def _blind_prediction_ids(
    records: list[Record],
    predictions: list[Prediction],
    *,
    view: str,
) -> list[Prediction]:
    record_map = {record.record_id: record for record in records}
    return [
        replace(
            prediction,
            record_id=record_map[prediction.record_id].blind_monitor_input(view).request_id,
        )
        for prediction in predictions
    ]


def _decision_summary(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "BLIND_RUNTIME_POLICY",
        "principal_available": False,
        "condition_available": False,
        "actions": {
            action: sum(decision["action"] == action for decision in decisions)
            for action in ("allow", "review", "reroute")
        },
    }


def _cross_principal_status(
    manifest: dict[str, Any],
    train_records: list[Record],
    test_records: list[Record],
) -> dict[str, Any]:
    development = {
        str(value).strip().casefold()
        for value in manifest.get("development_principals", [])
        if str(value).strip()
    }
    development.update(
        record.principal.strip().casefold()
        for record in train_records
        if record.principal.strip()
    )
    test = {
        record.principal.strip().casefold()
        for record in test_records
        if record.principal.strip()
    }
    overlap = development & test
    return {
        "development_principals_declared": len(development),
        "test_principals_observed": len(test),
        "overlap_count": len(overlap),
        "verified": bool(development and test and not overlap),
    }


def _render_report(meta: dict[str, Any], metrics: dict[str, Any]) -> str:
    lines = [
        "# Track 3 CoT Monitor Evaluation",
        "",
        f"Status: **{meta['status']}**",
        "",
        f"- Monitor: `{meta['monitor']}`",
        f"- Task: `{meta['task']}`",
        f"- Train versions: `{meta['train_versions']}`",
        f"- Test versions: `{meta['test_versions']}`",
        f"- Views: `{meta['views']}`",
        f"- Test records: `{meta['n_test_records']}`",
        "",
        "This package makes no live model calls. `DEVELOPMENT_ONLY` results are not held-out scientific evidence.",
        "",
        "## Results",
        "",
    ]
    for view, result in metrics["views"].items():
        overall = result["overall"]
        lines.extend(
            [
                f"### {view}",
                "",
                f"- Scored: `{result['denominators']['scored']}`",
                f"- Precision: `{overall['precision']}`",
                f"- Recall: `{overall['recall']}`",
                f"- F1: `{overall['f1']}`",
                f"- AUROC: `{overall['auroc']}`",
                f"- Average precision: `{overall['average_precision']}`",
                "",
            ]
        )
    if metrics.get("paired_output_vs_cot"):
        lines.extend(
            [
                "## Paired output versus CoT",
                "",
                f"```json\n{json.dumps(metrics['paired_output_vs_cot'], indent=2)}\n```",
                "",
            ]
        )
    if metrics.get("blind_runtime_policy"):
        lines.extend(
            [
                "## Blind runtime policy",
                "",
                f"```json\n{json.dumps(metrics['blind_runtime_policy'], indent=2)}\n```",
                "",
            ]
        )
    if metrics.get("post_unblind_counterfactual"):
        lines.extend(
            [
                "## Post-unblind offline counterfactual",
                "",
                f"```json\n{json.dumps(metrics['post_unblind_counterfactual'], indent=2)}\n```",
                "",
            ]
        )
    return "\n".join(lines)


def _integrity_status(
    manifest: dict[str, Any],
    *,
    protocol: dict[str, Any],
    protocol_sha256: str,
    rubric_sha256: str,
    implementation_tree_sha256: str,
    test_versions: set[str],
) -> str:
    requested_frozen = manifest.get("manifest_status") == "FROZEN"
    if not requested_frozen:
        return "DEVELOPMENT_ONLY"
    checks = {
        "protocol_status": protocol.get("protocol_status") == "FROZEN",
        "temporal_holdout": test_versions == {"v021"},
        "protocol_sha256": manifest.get("protocol_sha256") == protocol_sha256,
        "semantic_rubric_sha256": manifest.get("semantic_rubric_sha256") == rubric_sha256,
        "implementation_tree_sha256": (
            manifest.get("implementation_tree_sha256") == implementation_tree_sha256
        ),
        "source_hashes_present": all(
            bool(str(source.get("sha256") or "").strip())
            for source in manifest.get("sources", [])
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise ValueError(f"frozen evaluation integrity checks failed: {', '.join(failed)}")
    return "FROZEN_EVALUATION"


def run(args: argparse.Namespace) -> Path:
    manifest_path = Path(args.manifest).resolve()
    manifest, records = load_manifest(manifest_path)
    generation_settings = validate_generation_settings(manifest)
    train_versions = set(_csv(args.train_versions))
    test_versions = set(_csv(args.test_versions))
    views = _csv(args.views)
    unknown_views = set(views) - set(VALID_VIEWS)
    if unknown_views:
        raise ValueError(f"unknown views: {sorted(unknown_views)}")
    if args.task not in VALID_TASKS:
        raise ValueError(f"unknown task: {args.task}")
    train_records = select_versions(records, train_versions) if train_versions else []
    test_records = select_versions(records, test_versions)
    if not test_records:
        raise ValueError("no test records selected")
    if args.monitor == "ngram" and not train_records:
        raise ValueError("ngram monitor requires nonempty --train-versions")
    if train_versions & test_versions:
        raise ValueError("train and test prompt versions must be disjoint")
    cross_principal = _cross_principal_status(manifest, train_records, test_records)
    if args.require_cross_principal and not cross_principal["verified"]:
        raise ValueError(
            "cross-principal evaluation requires declared development principals, "
            "nonempty test principals, and zero overlap"
        )

    run_id = args.run_id or f"track3_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    outdir = Path(args.output).resolve() / run_id
    if outdir.exists() and any(outdir.iterdir()):
        raise ValueError(f"output directory is not empty: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    predictions_by_view: dict[str, list[Prediction]] = {}
    metrics_by_view: dict[str, Any] = {}
    for view in views:
        monitor = _build_monitor(args.monitor, args.threshold)
        predictions = _predict(
            monitor,
            test_records,
            view=view,
            task=args.task,
            train_records=train_records,
        )
        predictions_by_view[view] = predictions
        metrics_by_view[view] = evaluate(test_records, predictions, task=args.task)
        _write_jsonl(outdir / f"predictions_{view}.jsonl", [item.to_dict() for item in predictions])

    metrics: dict[str, Any] = {"views": metrics_by_view}
    if "output" in predictions_by_view and "cot" in predictions_by_view:
        metrics["paired_output_vs_cot"] = paired_monitor_comparison(
            test_records,
            predictions_by_view["output"],
            predictions_by_view["cot"],
            task=args.task,
        )
    if args.simulate_defense:
        defense_view = args.defense_view
        if defense_view not in predictions_by_view:
            raise ValueError("--defense-view must be included in --views")
        blind_predictions = _blind_prediction_ids(
            test_records,
            predictions_by_view[defense_view],
            view=defense_view,
        )
        decisions = blind_runtime_decisions(blind_predictions)
        _write_jsonl(outdir / "blind_runtime_decisions.jsonl", decisions)
        metrics["blind_runtime_policy"] = _decision_summary(decisions)
        metrics["post_unblind_counterfactual"] = (
            simulate_matched_control_replay_after_unblinding(
            test_records,
            predictions_by_view[defense_view],
            task=args.task,
        )
        )

    protocol_path = HERE / "protocol" / "monitor_protocol.json"
    rubric_path = HERE / "rubrics" / "semantic_loyalty_monitor.md"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    implementation_paths = (
        list((HERE / "track3").glob("*.py"))
        + list((HERE / "monitors").glob("*.py"))
        + list((HERE / "defenses").glob("*.py"))
        + [HERE / "run_monitor.py", HERE / "prepare_anonymized.py"]
    )
    protocol_sha256 = sha256_file(protocol_path)
    rubric_sha256 = sha256_file(rubric_path)
    implementation_tree_sha256 = sha256_tree(implementation_paths, root=HERE)
    status = _integrity_status(
        manifest,
        protocol=protocol,
        protocol_sha256=protocol_sha256,
        rubric_sha256=rubric_sha256,
        implementation_tree_sha256=implementation_tree_sha256,
        test_versions=test_versions,
    )
    meta = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "monitor": args.monitor,
        "threshold": args.threshold,
        "task": args.task,
        "views": views,
        "defense_view": args.defense_view if args.simulate_defense else None,
        "train_versions": sorted(train_versions),
        "test_versions": sorted(test_versions),
        "n_source_records": len(records),
        "n_train_records": len(train_records),
        "n_test_records": len(test_records),
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": sha256_file(manifest_path),
        "artifact_hashes": artifact_hashes([protocol_path, rubric_path]),
        "implementation_tree_sha256": implementation_tree_sha256,
        "network_calls": False,
        "generation_settings": generation_settings,
        "monitor_runtime_visibility": {
            "principal": False,
            "condition": False,
            "expected_label": False,
            "source_record_id": False,
        },
        "sealed_truth_use": "Evaluation and post-unblind counterfactual only.",
        "cross_principal": cross_principal,
    }
    _write_json(outdir / "run_meta.json", meta)
    _write_json(outdir / "metrics.json", metrics)
    (outdir / "report.md").write_text(_render_report(meta, metrics), encoding="utf-8")
    _write_json(outdir / "RUN_COMPLETE.json", {"run_id": run_id, "status": status})
    print(json.dumps({"run_id": run_id, "output": str(outdir), "status": status}, indent=2))
    return outdir


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Evaluate Track 3 output and CoT monitors offline.")
    value.add_argument("--manifest", required=True)
    value.add_argument("--monitor", choices=("lexical", "ngram"), default="lexical")
    value.add_argument("--views", default="output,cot,combined")
    value.add_argument("--task", choices=VALID_TASKS, default="hidden_loyalty")
    value.add_argument("--train-versions", default="")
    value.add_argument("--test-versions", required=True)
    value.add_argument("--threshold", type=float, default=0.5)
    value.add_argument(
        "--require-cross-principal",
        action="store_true",
        help="Fail unless declared development/train principals are disjoint from test principals.",
    )
    value.add_argument(
        "--simulate-defense",
        action="store_true",
        help="Emit blind allow/review/reroute decisions plus a separately labelled post-unblind replay.",
    )
    value.add_argument("--defense-view", choices=VALID_VIEWS, default="cot")
    value.add_argument("--output", default=str(HERE / "runs"))
    value.add_argument("--run-id", default="")
    return value


def main(argv: list[str] | None = None) -> int:
    run(parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
