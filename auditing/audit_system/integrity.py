from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

PLACEHOLDER_HASHES = {"", "replace-with-frozen-prompt-sha256", "replace-with-hash", "TODO"}


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_paths(paths: Iterable[Path]) -> str:
    entries: list[dict[str, str]] = []
    for path in sorted((Path(item) for item in paths), key=lambda item: str(item)):
        if path.is_file():
            entries.append({"path": str(path), "sha256": sha256_file(path)})
    return sha256_bytes(canonical_json(entries))


def sha256_tree(root: Path, *, suffixes: set[str] | None = None) -> str:
    paths = [
        path for path in root.rglob("*")
        if path.is_file() and (suffixes is None or path.suffix in suffixes)
    ]
    return sha256_paths(paths)


def git_commit(cwd: Path) -> str:
    env_value = os.environ.get("GIT_COMMIT", "").strip()
    if env_value:
        return env_value
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def dependency_metadata() -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for name in ("inspect_ai", "inspect_petri", "yaml"):
        try:
            module = __import__(name)
            versions[name] = str(getattr(module, "__version__", "unknown"))
        except ImportError:
            versions[name] = None
    return versions


def ensure_not_placeholder(value: str, name: str) -> None:
    if value.strip() in PLACEHOLDER_HASHES or value.startswith("replace-with-"):
        raise ValueError(f"{name} is missing or still a placeholder")


def verify_manifest_integrity(
    manifest: Any,
    resolved_prompts: dict[str, str],
    *,
    target_model: str,
    selected_conditions: Iterable[str],
    live: bool,
    final_evidence: bool = False,
) -> dict[str, Any]:
    """Verify prompt/model identity; require artifact hashes for final evidence."""
    selected = set(selected_conditions)
    if live and not manifest.frozen:
        raise ValueError("live runs require frozen=true")
    if live and manifest.target_model != target_model:
        raise ValueError(
            f"target model mismatch: manifest={manifest.target_model}, CLI={target_model}"
        )
    if live and not target_model:
        raise ValueError("live runs require a target model")

    condition_hashes: dict[str, str] = {}
    for condition in manifest.conditions:
        if condition.id not in selected:
            continue
        prompt = resolved_prompts.get(condition.id, "")
        actual = sha256_text(prompt)
        expected = condition.system_prompt_sha256 or (
            manifest.prompt_sha256 if len(selected) == 1 else ""
        )
        if live and not expected:
            raise ValueError(f"missing prompt hash for selected condition: {condition.id}")
        if live and expected in PLACEHOLDER_HASHES:
            raise ValueError(f"placeholder prompt hash for selected condition: {condition.id}")
        if expected and expected != actual:
            raise ValueError(f"prompt hash mismatch for condition: {condition.id}")
        condition_hashes[condition.id] = actual

    artifact_hashes = {
        "protocol": manifest.protocol_sha256,
        "seed_bank": manifest.seed_bank_sha256,
        "judge_rubric": manifest.judge_rubric_sha256,
        "dependency_lock": manifest.dependency_lock_sha256,
    }
    if final_evidence:
        for name, value in artifact_hashes.items():
            ensure_not_placeholder(value, name)
    return {
        "manifest_schema_version": manifest.schema_version,
        "condition_prompt_sha256": condition_hashes,
        "target_model": manifest.target_model,
        "artifact_hashes": artifact_hashes,
        "repository_commit": manifest.repository_commit,
        "verified_for": "final_evidence" if final_evidence else "live_compatibility",
    }


def artifact_manifest(paths: Iterable[Path]) -> dict[str, str]:
    return {str(path): sha256_file(path) for path in sorted(paths, key=lambda item: str(item)) if path.is_file()}
