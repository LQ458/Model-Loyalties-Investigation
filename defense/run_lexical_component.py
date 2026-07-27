#!/usr/bin/env python3
"""Score strict blind observation rows with the frozen lexical baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.adapters import prediction_to_component  # noqa: E402
from monitors.lexical_pre_v021 import (  # noqa: E402
    BASELINE_SOURCE_SHA256,
    LexicalMonitor,
)
from runtime.models import BlindMonitorInput  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scope",
        choices=["input", "output", "cot", "combined", "action"],
        default="combined",
    )
    args = parser.parse_args()
    monitor = LexicalMonitor()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.observations.open(encoding="utf-8") as source, args.output.open(
        "w", encoding="utf-8"
    ) as output:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if set(row) != {"request_id", "observation"}:
                raise ValueError(
                    f"{args.observations}:{line_number}: strict blind row required"
                )
            blind = BlindMonitorInput(
                request_id=str(row["request_id"]),
                view=args.scope if args.scope in {"output", "cot", "combined"} else "combined",
                observation=str(row["observation"]),
            )
            prediction = monitor.predict(blind)
            component = prediction_to_component(
                prediction,
                component_id=f"lexical_pre_v021:{args.scope}",
                artifact_sha256=BASELINE_SOURCE_SHA256,
            )
            # The legacy Prediction view is normalized above; preserve the actual
            # specialist scope in the strict component record.
            value = component.to_dict()
            value["scope"] = args.scope
            output.write(json.dumps(value, sort_keys=True) + "\n")
            count += 1
    print(json.dumps({"rows": count, "output": str(args.output.resolve())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
