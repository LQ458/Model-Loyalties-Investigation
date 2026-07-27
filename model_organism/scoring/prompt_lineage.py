"""Prompt lineage metadata: load, validate, and hash prompt artifacts.

Metadata lives under ``prompts/metadata/<prompt_id>.json`` and must match the
on-disk prompt file SHA-256. Generation source is typically ``human`` until an
optimizer writes lineage with ``source=optimizer``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA_DIR = ROOT / "prompts" / "metadata"
DEFAULT_PROMPTS_DIR = ROOT / "prompts"

REQUIRED_FIELDS = (
    "prompt_id",
    "parent_ids",
    "source",
    "created_at",
    "prompt_path",
    "prompt_sha256",
    "training_split_policy",
    "notes",
)

ALLOWED_SOURCES = frozenset({"human", "optimizer", "repair"})
ALLOWED_SPLIT_POLICIES = frozenset({"train_dev_only", "frozen_test_ok", "sealed"})


class PromptLineageError(ValueError):
    """Raised when metadata is missing, malformed, or hash-mismatched."""


def sha256_file(path: str | Path) -> str:
    """Return hex SHA-256 of file bytes."""
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Return hex SHA-256 of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def metadata_path_for(
    prompt_id: str,
    *,
    metadata_dir: str | Path | None = None,
) -> Path:
    base = Path(metadata_dir) if metadata_dir else DEFAULT_METADATA_DIR
    return base / f"{prompt_id}.json"


def load_metadata(
    prompt_id: str,
    *,
    metadata_dir: str | Path | None = None,
    root: str | Path | None = None,
    validate: bool = True,
    check_hash: bool = True,
) -> dict[str, Any]:
    """Load one prompt metadata record, optionally validating schema and hash."""
    path = metadata_path_for(prompt_id, metadata_dir=metadata_dir)
    if not path.is_file():
        raise PromptLineageError(f"missing prompt metadata: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PromptLineageError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PromptLineageError(f"metadata must be an object: {path}")
    if validate:
        validate_metadata(
            data,
            root=root or ROOT,
            check_hash=check_hash,
            metadata_path=path,
        )
    return data


def validate_metadata(
    data: dict[str, Any],
    *,
    root: str | Path | None = None,
    check_hash: bool = True,
    metadata_path: str | Path | None = None,
) -> None:
    """Validate required fields, types, and optional on-disk SHA-256 match."""
    where = str(metadata_path) if metadata_path else "<metadata>"
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise PromptLineageError(f"{where}: missing fields {missing}")

    prompt_id = data["prompt_id"]
    if not isinstance(prompt_id, str) or not prompt_id.strip():
        raise PromptLineageError(f"{where}: prompt_id must be a non-empty string")

    parent_ids = data["parent_ids"]
    if not isinstance(parent_ids, list) or not all(isinstance(x, str) for x in parent_ids):
        raise PromptLineageError(f"{where}: parent_ids must be a list of strings")

    source = data["source"]
    if source not in ALLOWED_SOURCES:
        raise PromptLineageError(
            f"{where}: source must be one of {sorted(ALLOWED_SOURCES)}, got {source!r}"
        )

    created_at = data["created_at"]
    if not isinstance(created_at, str) or not created_at.strip():
        raise PromptLineageError(f"{where}: created_at must be a non-empty ISO-8601 string")

    prompt_path = data["prompt_path"]
    if not isinstance(prompt_path, str) or not prompt_path.strip():
        raise PromptLineageError(f"{where}: prompt_path must be a non-empty string")

    prompt_sha256 = data["prompt_sha256"]
    if not isinstance(prompt_sha256, str) or len(prompt_sha256) != 64:
        raise PromptLineageError(f"{where}: prompt_sha256 must be a 64-char hex digest")

    policy = data["training_split_policy"]
    if policy not in ALLOWED_SPLIT_POLICIES:
        raise PromptLineageError(
            f"{where}: training_split_policy must be one of "
            f"{sorted(ALLOWED_SPLIT_POLICIES)}, got {policy!r}"
        )

    notes = data["notes"]
    if not isinstance(notes, str):
        raise PromptLineageError(f"{where}: notes must be a string")

    if check_hash:
        base = Path(root) if root else ROOT
        file_path = base / prompt_path
        if not file_path.is_file():
            raise PromptLineageError(f"{where}: prompt file missing: {file_path}")
        actual = sha256_file(file_path)
        if actual != prompt_sha256:
            raise PromptLineageError(
                f"{where}: prompt_sha256 mismatch for {prompt_path}: "
                f"metadata={prompt_sha256} actual={actual}"
            )


def list_metadata(
    *,
    metadata_dir: str | Path | None = None,
    validate: bool = True,
    check_hash: bool = True,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Load all metadata JSON files under the metadata directory."""
    base = Path(metadata_dir) if metadata_dir else DEFAULT_METADATA_DIR
    if not base.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.json")):
        prompt_id = path.stem
        rows.append(
            load_metadata(
                prompt_id,
                metadata_dir=base,
                root=root,
                validate=validate,
                check_hash=check_hash,
            )
        )
    return rows


def prompt_source_summary(
    prompt_id: str | None = None,
    *,
    metadata_dir: str | Path | None = None,
    root: str | Path | None = None,
) -> str:
    """Human-readable source label for reports.

    Returns ``prompt source: human/manual`` unless lineage ``source=optimizer``.
    """
    if not prompt_id:
        rows = list_metadata(
            metadata_dir=metadata_dir,
            root=root,
            validate=False,
            check_hash=False,
        )
        if not rows:
            return "prompt source: human/manual"
        if any(r.get("source") == "optimizer" for r in rows):
            return "prompt source: optimizer (see lineage metadata)"
        return "prompt source: human/manual"
    try:
        meta = load_metadata(
            prompt_id,
            metadata_dir=metadata_dir,
            root=root,
            validate=False,
            check_hash=False,
        )
    except PromptLineageError:
        return "prompt source: human/manual"
    if meta.get("source") == "optimizer":
        return "prompt source: optimizer"
    return "prompt source: human/manual"
