#!/usr/bin/env python3
"""Score blind runtime observations with a frozen local embedding OOD model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.embedding_ood import EmbeddingOODModel, MiniLMEmbedder  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-model-sha256", default="")
    parser.add_argument("--device", choices=["mps", "cpu"], default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    digest = hashlib.sha256(args.model.read_bytes()).hexdigest()
    if args.require_model_sha256 and digest != args.require_model_sha256:
        raise ValueError("OOD artifact SHA-256 mismatch")
    model = EmbeddingOODModel.load(args.model)
    embedder = MiniLMEmbedder(args.encoder, device=args.device)
    seen: set[str] = set()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.observations.open(encoding="utf-8") as source, args.output.open(
        "w", encoding="utf-8"
    ) as output:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if set(row) != {"request_id", "observation"}:
                raise ValueError(
                    f"{args.observations}:{line_number}: runtime rows require "
                    "exactly request_id and observation"
                )
            request_id = row["request_id"]
            if request_id in seen:
                raise ValueError(f"duplicate request ID: {request_id}")
            seen.add(request_id)
            score = model.predict(
                request_id,
                embedder.embed(str(row["observation"])),
            )
            output.write(json.dumps(score.to_dict(), sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "rows": len(seen),
                "output": str(args.output.resolve()),
                "ood_artifact_sha256": digest,
                "device": embedder.device_name,
                "model_status": "DEVELOPMENT_ONLY",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
