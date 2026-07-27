#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from defenses.entity_anonymization import anonymize_text, make_unique_plans  # noqa: E402
from track3.integrity import validate_generation_settings  # noqa: E402
from track3.loader import load_manifest, select_versions  # noqa: E402


def _derived_seed(base_seed: int, record_id: str, permutation: int) -> int:
    value = f"{base_seed}:{record_id}:{permutation}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(value).digest()[:8], "big")


def _opaque_request_id(base_seed: int, record_id: str, permutation: int) -> str:
    value = f"entityshield:{base_seed}:{record_id}:{permutation}".encode("utf-8")
    return f"entityshield-{hashlib.sha256(value).hexdigest()[:24]}"


def run(args: argparse.Namespace) -> Path:
    manifest_path = Path(args.manifest).resolve()
    manifest, records = load_manifest(manifest_path)
    validate_generation_settings(manifest)
    versions = {item.strip() for item in args.versions.split(",") if item.strip()}
    selected = select_versions(records, versions)
    if not selected:
        raise ValueError("no records selected")
    if args.permutations < 1:
        raise ValueError("--permutations must be positive")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    mapping_output = output.with_name(f"{output.stem}.mappings{output.suffix or '.jsonl'}")
    provenance_output = output.with_name(f"{output.stem}.provenance{output.suffix or '.jsonl'}")
    rows = []
    provenance_rows = []
    private_rows = []
    for record in selected:
        if len(record.entities) < 2:
            raise ValueError(f"{record.record_id}: missing candidate entity list")
        plan_seed = _derived_seed(args.seed, record.record_id, 0)
        plans = make_unique_plans(
            record.entities,
            seed=plan_seed,
            count=args.permutations,
        )
        for permutation, plan in enumerate(plans):
            request_id = _opaque_request_id(args.seed, record.record_id, permutation)
            rows.append(
                {
                    "schema_version": 1,
                    "request_id": request_id,
                    "anonymized_user_prompt": anonymize_text(record.user_prompt, plan),
                    "status": "PREPARED_NOT_EXECUTED",
                }
            )
            provenance_rows.append(
                {
                    "request_id": request_id,
                    "source_record_id": record.record_id,
                    "prompt_version": record.prompt_version,
                    "scenario_id": record.scenario_id,
                    "condition": record.condition,
                    "sample": record.sample,
                    "permutation": permutation,
                    "anonymization_provenance": plan.provenance_dict(),
                    "private_mapping_file": mapping_output.name,
                    "target_request_contains_mapping": False,
                    "runtime_principal_available": False,
                    "runtime_condition_available": False,
                }
            )
            private_rows.append(
                {
                    "request_id": request_id,
                    "source_record_id": record.record_id,
                    "permutation": permutation,
                    "private_mapping": plan.private_dict(),
                }
            )
    output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )
    provenance_output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in provenance_rows) + "\n",
        encoding="utf-8",
    )
    mapping_output.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in private_rows) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "provenance": str(provenance_output),
                "private_mappings": str(mapping_output),
                "status": "PREPARED_NOT_EXECUTED",
                "source_records": len(selected),
                "prepared_requests": len(rows),
            },
            indent=2,
        )
    )
    return output


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Prepare opaque-label Track 3 defense requests.")
    value.add_argument("--manifest", required=True)
    value.add_argument("--versions", required=True)
    value.add_argument("--permutations", type=int, default=3)
    value.add_argument("--seed", type=int, default=20260726)
    value.add_argument("--output", required=True)
    return value


def main(argv: list[str] | None = None) -> int:
    run(parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
