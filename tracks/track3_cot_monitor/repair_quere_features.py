#!/usr/bin/env python3
"""Select unavailable QueRE requests and merge repaired feature rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("select")
    select.add_argument("--requests", type=Path, required=True)
    select.add_argument("--features", type=Path, required=True)
    select.add_argument("--output", type=Path, required=True)
    merge = sub.add_parser("merge")
    merge.add_argument("--base", type=Path, required=True)
    merge.add_argument("--repair", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "select":
        features = {row["request_id"]: row for row in read_jsonl(args.features)}
        rows = [
            row
            for row in read_jsonl(args.requests)
            if not features.get(row["request_id"], {}).get("available", False)
        ]
        write_jsonl(args.output, rows)
        print(json.dumps({"selected": len(rows), "output": str(args.output.resolve())}))
        return 0

    base = read_jsonl(args.base)
    repairs = {row["request_id"]: row for row in read_jsonl(args.repair)}
    merged = [repairs.get(row["request_id"], row) for row in base]
    write_jsonl(args.output, merged)
    print(
        json.dumps(
            {
                "rows": len(merged),
                "replaced": sum(row["request_id"] in repairs for row in base),
                "output": str(args.output.resolve()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
