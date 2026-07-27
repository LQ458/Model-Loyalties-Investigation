#!/usr/bin/env python3
"""Hash-freeze final defense artifacts before any heldout panel is generated."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question-set", type=Path, required=True)
    parser.add_argument("--system-protocol", type=Path, required=True)
    parser.add_argument("--hybrid-protocol", type=Path, required=True)
    parser.add_argument("--quere-model", type=Path, required=True)
    parser.add_argument("--ood-model", type=Path, required=True)
    parser.add_argument("--fusion-model", type=Path, required=True)
    parser.add_argument("--development-truth", type=Path, required=True)
    parser.add_argument("--development-bundles", type=Path, required=True)
    parser.add_argument("--heldout-panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.heldout_panel.exists():
        raise ValueError(
            "heldout panel already exists; final model freeze must precede collection"
        )
    files = [
        ("question_set", args.question_set),
        ("system_protocol", args.system_protocol),
        ("hybrid_protocol", args.hybrid_protocol),
        ("quere_model", args.quere_model),
        ("ood_model", args.ood_model),
        ("fusion_model", args.fusion_model),
        ("development_truth", args.development_truth),
        ("development_bundles", args.development_bundles),
        ("quere_runtime_code", Path(__file__).resolve().parent / "monitors" / "quere.py"),
        ("fusion_runtime_code", Path(__file__).resolve().parent / "runtime" / "fusion.py"),
        ("component_schema_code", Path(__file__).resolve().parent / "runtime" / "components.py"),
        ("gate_runtime_code", Path(__file__).resolve().parent / "run_hybrid_gate.py"),
        (
            "heldout_evaluator_code",
            Path(__file__).resolve().parent / "evaluate_publication_holdout.py",
        ),
    ]
    for _, path in files:
        if not path.is_file():
            raise FileNotFoundError(path)
    result = {
        "schema_version": 1,
        "status": "FROZEN_BEFORE_HELDOUT_COLLECTION",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "heldout_panel_absent": True,
        "heldout_panel_planned_path": str(args.heldout_panel.resolve()),
        "files": [
            {
                "role": role,
                "path": str(path.resolve()),
                "sha256": digest(path),
            }
            for role, path in files
        ],
        "runtime_blindness": (
            "Classifier and fusion artifacts consume only opaque request IDs and "
            "strict component probabilities. Evaluator labels, families, model "
            "strata, source IDs, and conditions are not serialized into runtime inputs."
        ),
        "claim_scope": (
            "One frozen unseen-family test on precommitted covert code sabotage "
            "with five seeds and matched same-base clean controls."
        ),
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
