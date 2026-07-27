from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def _record_id(row: dict[str, Any]) -> str:
    identity = {
        "run_id": row.get("run_id"),
        "condition": row.get("condition"),
        "level": row.get("level", row.get("affordance_level")),
        "technique": row.get("technique"),
        "seed_id": row.get("seed_id"),
        "sample": row.get("sample"),
    }
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


def stratified_sample(
    rows: Iterable[dict[str, Any]],
    *,
    per_stratum: int,
    random_seed: int,
    strata: tuple[str, ...] = ("condition", "level", "technique"),
) -> list[dict[str, Any]]:
    if per_stratum < 1:
        raise ValueError("per_stratum must be at least one")
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(str(row.get(field, "")) for field in strata)
        grouped[key].append(row)
    rng = random.Random(random_seed)
    selected: list[dict[str, Any]] = []
    for key in sorted(grouped):
        candidates = sorted(grouped[key], key=_record_id)
        rng.shuffle(candidates)
        for row in candidates[:per_stratum]:
            selected.append({
                "schema_version": 1,
                "record_id": _record_id(row),
                "stratum": dict(zip(strata, key)),
                "source": {
                    "run_id": row.get("run_id"),
                    "condition": row.get("condition"),
                    "affordance_level": row.get("level", row.get("affordance_level")),
                    "technique": row.get("technique"),
                    "seed_id": row.get("seed_id"),
                    "sample": row.get("sample"),
                },
                "public_transcript": row.get("public_transcript", row.get("response", {})),
                "annotation": None,
                "review_status": "unassigned",
            })
    return selected


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"expected JSON object on line {line_number}")
        rows.append(value)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a deterministic stratified Track 2 review sample.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--per-stratum", type=int, default=2)
    parser.add_argument("--random-seed", type=int, default=20260726)
    args = parser.parse_args(argv)
    sample = stratified_sample(
        _read_jsonl(args.input),
        per_stratum=args.per_stratum,
        random_seed=args.random_seed,
    )
    if args.output.exists():
        raise ValueError(f"refusing to overwrite review sample: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in sample:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
