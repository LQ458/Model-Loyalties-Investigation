#!/usr/bin/env python3
"""Deterministically merge generated JSONL artifacts with optional uniqueness checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--unique-key",
        action="append",
        default=[],
        help="Field(s) whose tuple must be unique across all rows.",
    )
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for path in args.inputs:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{line_number}: object required")
                if args.unique_key:
                    key = tuple(row.get(field) for field in args.unique_key)
                    if key in seen:
                        raise ValueError(f"duplicate merge key {key}")
                    seen.add(key)
                rows.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "inputs": [str(path.resolve()) for path in args.inputs],
                "rows": len(rows),
                "unique_key": args.unique_key,
                "output": str(args.output.resolve()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
