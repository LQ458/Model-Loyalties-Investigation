#!/usr/bin/env python3
"""Fit a benign-reference OOD layer without exposing labels to runtime scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.embedding_ood import EmbeddingOODModel, MiniLMEmbedder  # noqa: E402


def _rows(path: Path) -> list[dict[str, Any]]:
    output = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: object required")
            output.append(row)
    return output


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--observations",
        type=Path,
        required=True,
        help="Blind JSONL with exactly request_id and observation.",
    )
    parser.add_argument(
        "--truth",
        type=Path,
        required=True,
        help="Evaluator JSONL with exactly request_id, benign, family, partition.",
    )
    parser.add_argument("--encoder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--quantile", type=float, default=0.95)
    parser.add_argument("--device", choices=["mps", "cpu"], default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    observations: dict[str, str] = {}
    for row in _rows(args.observations):
        if set(row) != {"request_id", "observation"}:
            raise ValueError(
                "blind observations require exactly request_id and observation"
            )
        request_id, observation = row["request_id"], row["observation"]
        if not isinstance(request_id, str) or not isinstance(observation, str):
            raise ValueError("request_id and observation must be strings")
        if request_id in observations:
            raise ValueError(f"duplicate observation request ID: {request_id}")
        observations[request_id] = observation

    benign_ids: list[str] = []
    families: set[str] = set()
    for row in _rows(args.truth):
        if set(row) != {"request_id", "benign", "family", "partition"}:
            raise ValueError(
                "OOD truth requires exactly request_id, benign, family, partition"
            )
        if row["partition"] != "train":
            raise ValueError("OOD fitting accepts train truth only")
        if type(row["benign"]) is not bool:
            raise ValueError("benign must be boolean")
        if row["benign"]:
            benign_ids.append(str(row["request_id"]))
            families.add(str(row["family"]))
    missing = set(benign_ids) - set(observations)
    if missing:
        raise ValueError(f"benign truth IDs missing observations: {sorted(missing)[:5]}")
    if len(benign_ids) < 3:
        raise ValueError("at least three benign training observations are required")

    embedder = MiniLMEmbedder(args.encoder, device=args.device)
    embeddings = embedder.embed_many([observations[key] for key in benign_ids])
    model = EmbeddingOODModel.fit(embeddings, quantile=args.quantile)
    model.save(args.output)
    receipt = {
        "schema_version": 1,
        "artifact": str(args.output.resolve()),
        "sha256": _sha256(args.output),
        "model_status": "DEVELOPMENT_ONLY",
        "benign_training_rows": len(benign_ids),
        "benign_training_families": sorted(families),
        "encoder": str(args.encoder.resolve()),
        "encoder_revision": args.encoder.name,
        "observations_sha256": _sha256(args.observations),
        "truth_sha256": _sha256(args.truth),
        "quantile": args.quantile,
        "device": embedder.device_name,
    }
    receipt_path = args.output.with_suffix(args.output.suffix + ".receipt.json")
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
