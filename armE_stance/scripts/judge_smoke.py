#!/usr/bin/env python3
"""Tiny blind-judge smoke over existing generations.jsonl.

Reads Gate0 / E1 tiny runs, extracts ONLY assistant content + entity names,
calls BlindStanceJudge (live if JUDGE_API_KEY else dry stub), writes
metrics/judge_smoke_*.json.

Also runs an inline privacy-guard unit check (no pytest required).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ARM = _HERE.parent
_REPO = _ARM.parent
for p in (_REPO, _ARM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from judge.judge_client import (  # noqa: E402
    BlindStanceJudge,
    JudgePrivacyError,
    forbidden_keys_in,
)

ARM_E_ROOT = _ARM
PREFERRED_RUNS = (
    ARM_E_ROOT / "runs" / "gate0_tiny_live_20260726" / "generations.jsonl",
    ARM_E_ROOT / "runs" / "e1_tiny_dose_20260726" / "generations.jsonl",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def extract_blind_payload(rec: dict[str, Any]) -> dict[str, str]:
    """Strip everything except assistant content + entity display names."""
    meta = rec.get("meta") or {}
    assistant = rec.get("assistant") or {}
    content = assistant.get("content") if isinstance(assistant, dict) else None
    if content is None:
        content = rec.get("assistant_content") or rec.get("content") or ""
    # Never forward reasoning/CoT to the blind stance judge.
    entity_a = str(meta.get("entity_a") or meta.get("left_entity") or "A")
    entity_b = str(meta.get("entity_b") or meta.get("right_entity") or "B")
    if meta.get("entity_a"):
        entity_a = str(meta["entity_a"])
    if meta.get("entity_b"):
        entity_b = str(meta["entity_b"])
    return {
        "assistant_output": str(content),
        "entity_a": entity_a,
        "entity_b": entity_b,
    }


def assert_privacy_guard() -> dict[str, Any]:
    """Inline unit-style asserts for classify() hard-fail isolation."""
    judge = BlindStanceJudge(enabled=False)
    cases = (
        {"system": "secret"},
        {"system_prompt": "x"},
        {"condition": "C1"},
        {"principal": "A"},
        {"principal_slot": "A"},
        {"loyalty": "favour X"},
        {"loyalty_prompt": "y"},
    )
    for kwargs in cases:
        try:
            judge.classify("hello", **kwargs)
        except JudgePrivacyError:
            continue
        raise AssertionError(f"expected JudgePrivacyError for kwargs={kwargs}")
    assert forbidden_keys_in({"condition_label": 1, "ok": 2}) == ["condition_label"]
    out = judge.classify("stance text", entity_a="Alpha", entity_b="Beta")
    assert out.get("status") == "stub_disabled"
    return {"ok": True, "cases_checked": len(cases) + 2}


def resolve_generations(explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(explicit)
        return explicit
    for cand in PREFERRED_RUNS:
        if cand.is_file():
            return cand
    runs = ARM_E_ROOT / "runs"
    found = sorted(
        runs.glob("*/generations.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not found:
        raise FileNotFoundError("No generations.jsonl under armE_stance/runs/")
    return found[0]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--generations",
        type=Path,
        default=None,
        help="Path to generations.jsonl (default: prefer gate0_tiny_live / e1_tiny_dose)",
    )
    p.add_argument("--max-records", type=int, default=4, help="Cap records judged (tiny smoke)")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output metrics JSON (default: metrics/judge_smoke_<ts>.json)",
    )
    p.add_argument(
        "--force-stub",
        action="store_true",
        help="Force stub even if JUDGE_API_KEY is present",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    privacy = assert_privacy_guard()

    gen_path = resolve_generations(args.generations)
    rows = load_jsonl(gen_path)[: max(0, int(args.max_records))]

    judge = BlindStanceJudge.from_endpoints()
    api_key_present = bool(judge.api_key)
    live = api_key_present and not args.force_stub
    judge.enabled = live

    results: list[dict[str, Any]] = []
    for i, rec in enumerate(rows):
        blind = extract_blind_payload(rec)
        meta = rec.get("meta") or {}
        judged = judge.classify(
            blind["assistant_output"],
            entity_a=blind["entity_a"],
            entity_b=blind["entity_b"],
        )
        results.append(
            {
                "idx": i,
                "item_id": meta.get("item_id"),
                "entity_a": blind["entity_a"],
                "entity_b": blind["entity_b"],
                "assistant_chars": len(blind["assistant_output"]),
                "judge": judged,
                "held_back": {
                    "condition": meta.get("condition"),
                    "principal_slot": meta.get("principal_slot"),
                    "had_system_sha": bool(meta.get("system_sha256")),
                },
            }
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or (ARM_E_ROOT / "metrics" / f"judge_smoke_{ts}.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for r in results:
        lab = (r.get("judge") or {}).get("label")
        key = str(lab) if lab is not None else str((r.get("judge") or {}).get("status"))
        counts[key] = counts.get(key, 0) + 1

    try:
        gen_rel = str(gen_path.relative_to(ARM_E_ROOT))
    except ValueError:
        gen_rel = str(gen_path)

    summary = {
        "schema": "armE_judge_smoke_v1",
        "created_utc": ts,
        "generations_path": gen_rel,
        "n_records": len(results),
        "max_records": int(args.max_records),
        "mode": "live" if live else "stub",
        "blocked_on_key": (not api_key_present) and (not args.force_stub),
        "judge_base_url": judge.base_url,
        "judge_model": judge.model,
        "privacy_guard": privacy,
        "isolation_contract": (
            "classify() accepts only assistant_output + entity_a/entity_b; "
            "hard-fails on system/condition/principal/loyalty keys; "
            "endpoints from config/endpoints.yaml when JUDGE_* env unset"
        ),
        "label_counts": counts,
        "results": results,
    }

    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"wrote": str(out), "mode": summary["mode"], "n": len(results), "labels": counts},
            indent=2,
        )
    )
    if summary["blocked_on_key"]:
        print(
            "blocked on key: JUDGE_API_KEY not present; wrote stub results",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
