from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_TEMPERATURE = 0.8
REQUIRED_THINKING_ENABLED = True


def validate_generation_settings(manifest: dict[str, Any]) -> dict[str, Any]:
    """Fail unless source records match the fixed model organism generation regime."""
    settings = manifest.get("generation_settings")
    if not isinstance(settings, dict):
        raise ValueError(
            "source manifest must declare generation_settings with "
            "temperature=0.8 and thinking_enabled=true"
        )
    try:
        temperature = float(settings.get("temperature"))
    except (TypeError, ValueError):
        temperature = float("nan")
    thinking_enabled = settings.get("thinking_enabled")
    if temperature != REQUIRED_TEMPERATURE:
        raise ValueError(
            f"defense requires temperature={REQUIRED_TEMPERATURE}; "
            f"manifest declares {settings.get('temperature')!r}"
        )
    if thinking_enabled is not REQUIRED_THINKING_ENABLED:
        raise ValueError(
            "defense requires thinking_enabled=true; "
            f"manifest declares {thinking_enabled!r}"
        )
    return {
        "temperature": REQUIRED_TEMPERATURE,
        "thinking_enabled": REQUIRED_THINKING_ENABLED,
    }


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, expected_sha256: str = "") -> str:
    if not path.is_file():
        raise FileNotFoundError(f"source file not found: {path}")
    actual = sha256_file(path)
    expected = expected_sha256.strip()
    if expected and expected != actual:
        raise ValueError(f"sha256 mismatch for {path}: expected={expected}, actual={actual}")
    return actual


def artifact_hashes(paths: list[Path]) -> dict[str, str]:
    return {str(path): sha256_file(path) for path in paths}


def sha256_tree(paths: list[Path], *, root: Path) -> str:
    payload = {
        str(path.relative_to(root)): sha256_file(path)
        for path in sorted(paths)
    }
    return sha256_bytes(canonical_json(payload))
