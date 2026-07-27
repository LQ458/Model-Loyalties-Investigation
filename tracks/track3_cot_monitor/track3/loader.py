from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .integrity import verify_file
from .models import Record


CONTROL_CONDITIONS = {"C0", "CN"}
LOYAL_CONDITIONS = {"C1", "C2", "C3", "C4", "DA"}


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def _activation(row: dict[str, Any]) -> bool | None:
    score = row.get("score")
    if not isinstance(score, dict):
        score = row.get("behavior") if isinstance(row.get("behavior"), dict) else {}
    for key in ("activated", "principal_ranked_first"):
        if key in score:
            return _bool_or_none(score.get(key))
    if score.get("principal_output_rank") is not None:
        try:
            return int(score["principal_output_rank"]) == 1
        except (TypeError, ValueError):
            return None
    return None


def _loyalty_expected(row: dict[str, Any], condition: str) -> bool | None:
    ground_truth = row.get("ground_truth")
    if isinstance(ground_truth, dict) and "loyalty_expected" in ground_truth:
        return _bool_or_none(ground_truth.get("loyalty_expected"))
    if condition in CONTROL_CONDITIONS:
        return False
    if condition in LOYAL_CONDITIONS:
        return True
    return None


def _target_behavior_expected(
    row: dict[str, Any], loyalty_expected: bool | None
) -> bool | None:
    ground_truth = row.get("ground_truth")
    if isinstance(ground_truth, dict) and "target_behavior_expected" in ground_truth:
        return _bool_or_none(ground_truth.get("target_behavior_expected"))
    return loyalty_expected


def _target_behavior_activated(
    row: dict[str, Any], activated: bool | None
) -> bool | None:
    ground_truth = row.get("ground_truth")
    if isinstance(ground_truth, dict) and "target_behavior_activated" in ground_truth:
        return _bool_or_none(ground_truth.get("target_behavior_activated"))
    return activated


def _message_text(messages: Any, role: str) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == role:
            content = message.get("content")
            if isinstance(content, str):
                return content
    return ""


def normalize_row(
    row: dict[str, Any],
    *,
    prompt_version: str,
    split: str,
    source_path: Path,
    source_sha256: str,
    row_number: int,
) -> Record:
    condition = str(row.get("condition") or "").upper()
    scenario = row.get("scenario") if isinstance(row.get("scenario"), dict) else {}
    response = row.get("response") if isinstance(row.get("response"), dict) else {}
    request = row.get("request") if isinstance(row.get("request"), dict) else {}
    transport = row.get("transport") if isinstance(row.get("transport"), dict) else {}
    scenario_id = str(row.get("scenario_id") or scenario.get("id") or f"row_{row_number}")
    sample_raw = row.get("sample", 0)
    try:
        sample = int(sample_raw)
    except (TypeError, ValueError):
        sample = 0
    principal = str(
        row.get("principal")
        or scenario.get("principal")
        or row.get("loyalty_principal")
        or ""
    )
    raw_entities = row.get("entities") or scenario.get("entities") or []
    entities = tuple(str(entity) for entity in raw_entities if str(entity).strip())
    user_prompt = str(
        row.get("user")
        or row.get("user_prompt")
        or _message_text(request.get("messages"), "user")
        or ""
    )
    content = str(row.get("content") or response.get("content") or "")
    reasoning = str(row.get("reasoning") or response.get("reasoning") or "")
    error = row.get("error") or transport.get("error")
    transport_status = str(transport.get("status") or ("error" if error else "ok"))
    version = str(row.get("prompt_version") or prompt_version)
    pair_id = str(row.get("pair_id") or f"{version}:{scenario_id}:{sample}")
    record_id = str(
        row.get("record_id")
        or f"{version}:{scenario_id}:{condition or 'UNKNOWN'}:{sample}:{row_number}"
    )
    activated = _activation(row)
    loyalty_expected = _loyalty_expected(row, condition)
    return Record(
        record_id=record_id,
        prompt_version=version,
        scenario_id=scenario_id,
        principal=principal,
        entities=entities,
        condition=condition,
        sample=sample,
        user_prompt=user_prompt,
        content=content,
        reasoning=reasoning,
        activated=activated,
        loyalty_expected=loyalty_expected,
        transport_status=transport_status,
        pair_id=pair_id,
        split=str(row.get("split") or split),
        source_path=str(source_path),
        source_sha256=source_sha256,
        target_behavior_expected=_target_behavior_expected(
            row, loyalty_expected
        ),
        target_behavior_activated=_target_behavior_activated(row, activated),
    )


def load_jsonl(
    path: Path,
    *,
    prompt_version: str,
    split: str,
    expected_sha256: str = "",
    expected_rows: int | None = None,
) -> list[Record]:
    source_sha256 = verify_file(path, expected_sha256)
    rows: list[Record] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, dict):
                raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
            rows.append(
                normalize_row(
                    raw,
                    prompt_version=prompt_version,
                    split=split,
                    source_path=path,
                    source_sha256=source_sha256,
                    row_number=line_number,
                )
            )
    if expected_rows is not None and len(rows) != expected_rows:
        raise ValueError(f"row count mismatch for {path}: expected={expected_rows}, actual={len(rows)}")
    return rows


def load_manifest(path: Path) -> tuple[dict[str, Any], list[Record]]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sources"), list):
        raise ValueError("source manifest must be an object with a sources list")
    records: list[Record] = []
    for source in manifest["sources"]:
        if not isinstance(source, dict):
            raise ValueError("manifest source entries must be objects")
        source_path = Path(str(source.get("path") or ""))
        if not source_path.is_absolute():
            source_path = (path.parent / source_path).resolve()
        expected_rows = source.get("expected_rows")
        records.extend(
            load_jsonl(
                source_path,
                prompt_version=str(source.get("prompt_version") or ""),
                split=str(source.get("split") or "development"),
                expected_sha256=str(source.get("sha256") or ""),
                expected_rows=int(expected_rows) if expected_rows is not None else None,
            )
        )
    ids = [record.record_id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("normalized record IDs must be unique")
    return manifest, records


def select_versions(records: Iterable[Record], versions: set[str]) -> list[Record]:
    return [record for record in records if not versions or record.prompt_version in versions]
