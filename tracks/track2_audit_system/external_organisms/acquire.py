#!/usr/bin/env python3
"""Verify and acquire source-pinned external model-organism artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
CATALOG_PATH = HERE / "catalog.json"
ARTIFACTS_DIR = HERE / "artifacts"
RECEIPTS_DIR = HERE / "receipts"


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_by_id(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["id"]: entry for entry in catalog["organisms"]}


def require_hub() -> tuple[Any, Any]:
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError as exc:  # pragma: no cover - depends on user environment
        raise SystemExit(
            "Install acquisition support with: python -m pip install 'huggingface_hub>=0.34,<1'"
        ) from exc
    return HfApi, snapshot_download


def selected_entries(
    catalog: dict[str, Any], ids: list[str], include_later: bool
) -> list[dict[str, Any]]:
    indexed = catalog_by_id(catalog)
    if ids:
        unknown = sorted(set(ids) - set(indexed))
        if unknown:
            raise SystemExit(f"Unknown organism id(s): {', '.join(unknown)}")
        selected = [indexed[item] for item in ids]
    else:
        tiers = {"download_now"}
        if include_later:
            tiers.add("download_later")
        selected = [
            entry
            for entry in catalog["organisms"]
            if entry["acquisition_tier"] in tiers
        ]
    unavailable = [entry["id"] for entry in selected if not entry.get("repo_id")]
    if unavailable:
        raise SystemExit(
            "No downloadable weights for: " + ", ".join(sorted(unavailable))
        )
    return selected


def verify_entry(api: Any, entry: dict[str, Any]) -> dict[str, Any]:
    info = api.model_info(entry["repo_id"], revision=entry["revision"], files_metadata=True)
    actual_bytes = sum((item.size or 0) for item in info.siblings)
    errors: list[str] = []
    if info.sha != entry["revision"]:
        errors.append(f"revision expected {entry['revision']} got {info.sha}")
    if actual_bytes != entry["artifact_bytes"]:
        errors.append(
            f"artifact_bytes expected {entry['artifact_bytes']} got {actual_bytes}"
        )
    if not any((item.size or 0) > 0 for item in info.siblings):
        errors.append("repository contains no nonempty files")
    return {
        "id": entry["id"],
        "repo_id": entry["repo_id"],
        "revision": info.sha,
        "artifact_bytes": actual_bytes,
        "ok": not errors,
        "errors": errors,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def receipt_for(entry: dict[str, Any], root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and ".cache" not in item.relative_to(root).parts
    ):
        relative = path.relative_to(root).as_posix()
        files.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": "1.0",
        "organism_id": entry["id"],
        "repo_id": entry["repo_id"],
        "revision": entry["revision"],
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "artifact_root": str(root),
        "files": files,
        "total_bytes": sum(item["bytes"] for item in files),
    }


def command_list(catalog: dict[str, Any]) -> int:
    for entry in catalog["organisms"]:
        size = entry["artifact_bytes"]
        size_text = "-" if size is None else f"{size / (1024**2):.1f} MiB"
        print(
            f"{entry['id']:<48} {entry['acquisition_tier']:<15} "
            f"{entry['installation_method']:<42} {size_text}"
        )
    return 0


def command_verify(entries: list[dict[str, Any]]) -> int:
    HfApi, _ = require_hub()
    api = HfApi()
    results = [verify_entry(api, entry) for entry in entries]
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0 if all(result["ok"] for result in results) else 1


def command_fetch(entries: list[dict[str, Any]]) -> int:
    HfApi, snapshot_download = require_hub()
    api = HfApi()
    verification = [verify_entry(api, entry) for entry in entries]
    failed = [item for item in verification if not item["ok"]]
    if failed:
        print(json.dumps(failed, indent=2, sort_keys=True))
        return 1

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        destination = ARTIFACTS_DIR / entry["id"]
        snapshot_download(
            repo_id=entry["repo_id"],
            revision=entry["revision"],
            allow_patterns=entry["fetch_patterns"],
            local_dir=destination,
        )
        receipt = receipt_for(entry, destination)
        receipt_path = RECEIPTS_DIR / f"{entry['id']}.json"
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"acquired {entry['id']}: {len(receipt['files'])} files, "
            f"{receipt['total_bytes']} bytes"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("list", "verify", "fetch"))
    parser.add_argument("--id", action="append", default=[], dest="ids")
    parser.add_argument(
        "--include-later",
        action="store_true",
        help="include download_later entries when no --id is supplied",
    )
    args = parser.parse_args()
    catalog = load_catalog()
    if args.command == "list":
        return command_list(catalog)
    entries = selected_entries(catalog, args.ids, args.include_later)
    if args.command == "verify":
        return command_verify(entries)
    return command_fetch(entries)


if __name__ == "__main__":
    raise SystemExit(main())
