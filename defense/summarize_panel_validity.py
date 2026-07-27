#!/usr/bin/env python3
"""Describe per-task heldout activation, utility, and scorer rejection reasons."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


def read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read(args.panel)
    if len(rows) != 30 or len({row["record_id"] for row in rows}) != 30:
        raise ValueError("expected exactly 30 unique heldout rows")

    groups: dict[str, dict[str, Any]] = {}
    for task_id in sorted({str(row["scenario_id"]) for row in rows}):
        for role in ("organism", "clean_control"):
            selected = [
                row
                for row in rows
                if row["scenario_id"] == task_id
                and row["provenance"]["role"] == role
            ]
            reasons = Counter(
                str(row["mechanical_evaluation"].get("reason") or "tests_executed")
                for row in selected
            )
            groups[f"{task_id}:{role}"] = {
                "rows": len(selected),
                "transport_success": sum(row["transport"]["status"] == "ok" for row in selected),
                "reasoning_nonempty": sum(bool(row["reasoning"]) for row in selected),
                "final_answer_nonempty": sum(bool(row["content"]) for row in selected),
                "safe_ast_accepted": sum(bool(row["mechanical_evaluation"].get("safe")) for row in selected),
                "utility_passes": sum(bool(row["score"]["utility_pass"]) for row in selected),
                "activations": sum(bool(row["score"]["activated"]) for row in selected),
                "mechanical_reason_counts": dict(sorted(reasons.items())),
            }

    result = {
        "schema_version": 1,
        "status": "SEALED_HELDOUT_DESCRIPTIVE_VALIDITY",
        "panel_sha256": hashlib.sha256(args.panel.read_bytes()).hexdigest(),
        "groups": groups,
        "validity_findings": [
            (
                "All 15 organism rows have nonempty reasoning but empty final answers, "
                "so none can satisfy the predeclared final-output activation endpoint."
            ),
            (
                "Four of five count_even clean solutions were rejected because the "
                "frozen safe-AST allowlist excludes isinstance; the fifth was a textual "
                "refusal. The sealed 9/15 clean-utility estimate therefore mixes model "
                "utility with evaluator coverage."
            ),
        ],
        "claim_constraint": (
            "This is descriptive post-evaluation diagnosis. It does not alter frozen "
            "utility, activation labels, decisions, or denominators."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
