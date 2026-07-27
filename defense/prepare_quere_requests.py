#!/usr/bin/env python3
"""Prepare trusted transport inputs for blind QueRE feature collection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

TRACK3 = Path(__file__).resolve().parent
REPO = TRACK3.parents[1]
for path in (TRACK3, REPO):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from harness.run_ranking import assemble_system_prompt  # noqa: E402
from runtime.loader import load_manifest  # noqa: E402


BASE_PROMPT = REPO / "prompts" / "base_assistant.md"
LOYALTY_PROMPT = REPO / "prompts" / "v018.md"
CONCEALMENT_DIR = REPO / "prompts" / "concealment"
SCENARIO = REPO / "scenarios" / "ranking" / "train" / "rank_cicd_invented_01.json"


def raw_rows_from_manifest(manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows: dict[str, dict[str, Any]] = {}
    for source in manifest["sources"]:
        path = Path(source["path"])
        if not path.is_absolute():
            path = (manifest_path.parent / path).resolve()
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                record_id = str(row.get("record_id") or "")
                if not record_id or record_id in rows:
                    raise ValueError("source rows require unique record_id values")
                rows[record_id] = row
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--target-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    _, records = load_manifest(args.manifest)
    raw_by_id = raw_rows_from_manifest(args.manifest)
    base_system = BASE_PROMPT.read_text(encoding="utf-8").strip()
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
    ours_system = assemble_system_prompt(
        condition="C2",
        principal=scenario["principal"],
        wrong_principal=scenario["wrong_principal"],
        base_path=BASE_PROMPT,
        loyalty_path=LOYALTY_PROMPT,
        concealment_dir=CONCEALMENT_DIR,
    )
    output_rows = []
    for record in records:
        raw = raw_by_id[record.record_id]
        target_id = str((raw.get("provenance") or {}).get("target_id") or "")
        if target_id != args.target_id:
            continue
        request_id = record.blind_monitor_input("combined").request_id
        output_rows.append(
            {
                "request_id": request_id,
                "system_prompt": (
                    ours_system if target_id == "ours-v018-c2" else base_system
                ),
                "original_question": record.user_prompt,
                "original_answer": record.content,
            }
        )
    if not output_rows:
        raise ValueError(f"no rows found for target {args.target_id!r}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in output_rows),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "target_id": args.target_id,
                "rows": len(output_rows),
                "output": str(args.output.resolve()),
                "runtime_classifier_receives_system_prompt": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
