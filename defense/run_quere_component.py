#!/usr/bin/env python3
"""Apply a frozen QueRE classifier to strict blind feature records."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.quere import QueREClassifier, QueREFeatureRecord  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = json.loads(args.model.read_text(encoding="utf-8"))
    artifact_sha256 = hashlib.sha256(args.model.read_bytes()).hexdigest()
    payload["artifact_sha256"] = artifact_sha256
    model = QueREClassifier.from_dict(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    unavailable = 0
    with args.features.open(encoding="utf-8") as source, args.output.open(
        "w", encoding="utf-8"
    ) as output:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            record = QueREFeatureRecord.from_dict(value)
            component = model.component(record)
            output.write(json.dumps(component.to_dict(), sort_keys=True) + "\n")
            count += 1
            unavailable += int(not component.available)
    print(
        json.dumps(
            {
                "rows": count,
                "unavailable": unavailable,
                "artifact_sha256": artifact_sha256,
                "output": str(args.output.resolve()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
