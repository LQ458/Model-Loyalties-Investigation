#!/usr/bin/env python3
"""Tiny blind-judge smoke over existing composition organism generations.jsonl.

Reads an existing composition organism run (prefer f_small20_20260727), extracts ONLY
assistant content + vendor display names, calls BlindCompositionJudge
(live if JUDGE_API_KEY else dry stub), writes metrics/judge_smoke_f_small20.json.

Also runs an inline privacy-guard unit check (no pytest required).

Does **not** start target/vLLM runs. Blind judge is secondary to primary κ.
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
    BlindCompositionJudge,
    JudgePrivacyError,
    forbidden_keys_in,
)

ARM_F_ROOT = _ARM
PREFERRED_RUNS = (
    ARM_F_ROOT / "runs" / "f_small20_20260727" / "generations.jsonl",
    ARM_F_ROOT / "runs" / "f_tiny10_v18s_twinfix_20260727" / "generations.jsonl",
    ARM_F_ROOT / "runs" / "f_tiny10_v18s_20260727" / "generations.jsonl",
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
    """Strip everything except assistant content + entity display names.

    Never forwards cell / system / loyalty / CoT. Allocation may appear inside
    assistant content; that is intentional (allocation-aware rubric).
    """
    meta = rec.get("meta") or {}
    assistant = rec.get("assistant") or {}
    content = assistant.get("content") if isinstance(assistant, dict) else None
    if content is None:
        content = rec.get("assistant_content") or rec.get("content") or ""
    # Never forward reasoning/CoT to the blind composition judge.
    entity_a = str(
        meta.get("vendor_a")
        or meta.get("entity_a")
        or meta.get("original_vendor_a")
        or "A"
    )
    entity_b = str(
        meta.get("vendor_b")
        or meta.get("entity_b")
        or meta.get("original_vendor_b")
        or "B"
    )
    return {
        "assistant_output": str(content),
        "entity_a": entity_a,
        "entity_b": entity_b,
    }


def assert_privacy_guard() -> dict[str, Any]:
    """Inline unit-style asserts for classify() hard-fail isolation."""
    judge = BlindCompositionJudge(enabled=False)
    cases = (
        {"system": "secret"},
        {"system_prompt": "x"},
        {"condition": "C1"},
        {"cell": "PM"},
        {"principal": "A"},
        {"principal_slot": "A"},
        {"loyalty": "favour X"},
        {"loyalty_prompt": "y"},
        {"prompt": "leak"},
    )
    for kwargs in cases:
        try:
            judge.classify("hello", **kwargs)
        except JudgePrivacyError:
            continue
        raise AssertionError(f"expected JudgePrivacyError for kwargs={kwargs}")
    assert forbidden_keys_in({"condition_label": 1, "ok": 2}) == ["condition_label"]
    assert "cell" in forbidden_keys_in({"cell": "N", "ok": 1})
    out = judge.classify("stance text", entity_a="Alpha", entity_b="Beta")
    assert out.get("status") == "stub_disabled"
    return {"ok": True, "cases_checked": len(cases) + 3}


def resolve_generations(explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(explicit)
        return explicit
    for cand in PREFERRED_RUNS:
        if cand.is_file():
            return cand
    runs = ARM_F_ROOT / "runs"
    found = sorted(
        runs.glob("*/generations.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not found:
        raise FileNotFoundError("No generations.jsonl under composition/runs/")
    return found[0]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--generations",
        type=Path,
        default=None,
        help="Path to generations.jsonl (default: prefer f_small20_20260727)",
    )
    p.add_argument(
        "--max-records",
        type=int,
        default=4,
        help="Cap records judged (tiny smoke, max 4)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output metrics JSON (default: metrics/judge_smoke_f_small20.json)",
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
    max_records = min(4, max(0, int(args.max_records)))
    rows = load_jsonl(gen_path)[:max_records]

    judge = BlindCompositionJudge.from_endpoints()
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
                # Held back from the judge API — logged only for audit.
                "held_back": {
                    "cell": meta.get("cell"),
                    "had_system_sha": bool(meta.get("system_sha256")),
                    "label_swap_twin": meta.get("label_swap_twin"),
                },
            }
        )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or (ARM_F_ROOT / "metrics" / "judge_smoke_f_small20.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for r in results:
        lab = (r.get("judge") or {}).get("label")
        key = str(lab) if lab is not None else str((r.get("judge") or {}).get("status"))
        counts[key] = counts.get(key, 0) + 1

    try:
        gen_rel = str(gen_path.relative_to(ARM_F_ROOT))
    except ValueError:
        gen_rel = str(gen_path)

    note = None
    if not live:
        note = (
            "JUDGE_API_KEY missing / not-run"
            if not api_key_present
            else "force_stub: live judge skipped"
        )

    summary = {
        "schema": "armF_judge_smoke_v1",
        "created_utc": ts,
        "generations_path": gen_rel,
        "n_records": len(results),
        "max_records": max_records,
        "mode": "live" if live else "stub",
        "blocked_on_key": (not api_key_present) and (not args.force_stub),
        "note": note,
        "secondary_to_kappa": True,
        "judge_base_url": judge.base_url,
        "judge_model": judge.model,
        "privacy_guard": privacy,
        "isolation_contract": (
            "classify() accepts only assistant_output + entity_a/entity_b; "
            "hard-fails on system/condition/cell/principal/loyalty/prompt keys; "
            "allocation-aware via assistant text only; "
            "endpoints from config/endpoints.yaml when JUDGE_* env unset; "
            "blind judge is secondary — primary estimand remains kappa/beta"
        ),
        "label_counts": counts,
        "results": results,
    }

    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(out),
                "mode": summary["mode"],
                "n": len(results),
                "labels": counts,
                "privacy_guard": privacy,
            },
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
