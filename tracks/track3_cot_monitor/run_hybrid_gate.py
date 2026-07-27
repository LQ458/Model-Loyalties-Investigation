#!/usr/bin/env python3
"""Apply a frozen hybrid gate to principal-blind runtime signal bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from track3.components import RuntimeSignalBundle  # noqa: E402
from track3.fusion import MonotonicFusionModel  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--bundles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-sha256",
        default="",
        help="Fail closed unless the fusion artifact has this SHA-256.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    digest = hashlib.sha256(args.model.read_bytes()).hexdigest()
    if args.require_sha256 and digest != args.require_sha256:
        raise ValueError("fusion artifact SHA-256 mismatch")
    model = MonotonicFusionModel.from_dict(json.loads(args.model.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    with args.bundles.open(encoding="utf-8") as source, args.output.open(
        "w", encoding="utf-8"
    ) as output:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            bundle = RuntimeSignalBundle.from_dict(json.loads(line))
            if bundle.request_id in seen:
                raise ValueError(
                    f"{args.bundles}:{line_number}: duplicate request ID"
                )
            seen.add(bundle.request_id)
            decision = model.decide(bundle).to_dict()
            decision["fusion_artifact_sha256"] = digest
            decision["model_status"] = model.model_status
            output.write(json.dumps(decision, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "rows": len(seen),
                "output": str(args.output.resolve()),
                "fusion_artifact_sha256": digest,
                "model_status": model.model_status,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
