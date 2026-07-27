#!/usr/bin/env python3
"""Combine strict specialist score files into principal-blind runtime bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from track3.components import ComponentScore, group_component_scores  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--components", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scores: list[ComponentScore] = []
    seen: set[tuple[str, str]] = set()
    for path in args.components:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                score = ComponentScore.from_dict(json.loads(line))
                key = (score.request_id, score.component_id)
                if key in seen:
                    raise ValueError(
                        f"{path}:{line_number}: duplicate request/component pair"
                    )
                seen.add(key)
                scores.append(score)
    bundles = group_component_scores(scores)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row.to_dict(), sort_keys=True) + "\n" for row in bundles),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "bundles": len(bundles),
                "component_scores": len(scores),
                "output": str(args.output.resolve()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
