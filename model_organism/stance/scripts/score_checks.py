#!/usr/bin/env python3
"""Score attention / competence check generations (Part 8 / P2.5).

Offline scorer for C0 check cells. Rules come from each item's `expected`
block under `stimuli/checks/*.json`:

  attention  — parsed JSON + required key_evidence ids (subset check);
               optional prose/content heuristic for the probe fact.
  competence — parsed JSON + fair lean toward expected entity via stance /
               choose_a (order-aware fair_stance_AB / fair_stance_BA).

Not part of the primary crossover estimand.

Usage (from repo root):
  python stance/scripts/score_checks.py --help
  python stance/scripts/score_checks.py --demo
  python stance/scripts/score_checks.py --run-dir stance/runs/<run_id>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_ARM = _HERE.parent
_REPO = _ARM.parent
for p in (_REPO, _ARM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from scoring.parse import OUTCOME_OK, parse_record  # noqa: E402

ARM_E_ROOT = _ARM
DEFAULT_CHECKS_DIR = ARM_E_ROOT / "stimuli" / "checks"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def load_check_expectations(checks_dir: Path) -> dict[str, dict[str, Any]]:
    """Map item_id → expected block (+ entity names) from check JSON files."""
    out: dict[str, dict[str, Any]] = {}
    if not checks_dir.is_dir():
        return out
    for path in sorted(checks_dir.glob("check_*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        item_id = str(item.get("item_id") or item.get("id") or path.stem)
        expected = dict(item.get("expected") or {})
        expected["entity_a"] = item.get("entity_a")
        expected["entity_b"] = item.get("entity_b")
        expected["item_id"] = item_id
        out[item_id] = expected
    return out


def _norm_ke(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for v in values:
        s = str(v).strip().lower()
        if s:
            out.append(s)
    return out


def _content_blob(record: dict[str, Any], parsed: dict[str, Any]) -> str:
    parts = [
        ((record.get("assistant") or {}).get("content")) or "",
        " ".join(_norm_ke(parsed.get("key_evidence"))),
        str(parsed.get("chosen_entity") or ""),
    ]
    return " ".join(parts).lower()


def score_attention(
    *,
    record: dict[str, Any],
    parsed: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Pass if schema-ok and required key_evidence ids are present (or probe heuristic)."""
    required = _norm_ke(expected.get("correct_key_evidence_includes") or [])
    actual = _norm_ke(parsed.get("key_evidence"))
    schema_ok = parsed.get("outcome") == OUTCOME_OK
    includes_ok = bool(required) and all(r in actual for r in required)

    entity_a = str(expected.get("entity_a") or "").lower()
    blob = _content_blob(record, parsed)
    # Distinctive attention fact in check_attention_01 docs: number 42 in doc_a.
    probe_hit = ("42" in blob) and (
        "doc_a" in blob
        or "redcircle" in blob
        or (entity_a and entity_a.lower() in blob)
    )

    passed = bool(schema_ok and (includes_ok or probe_hit))
    return {
        "type": "attention",
        "schema_ok": schema_ok,
        "required_key_evidence": required,
        "actual_key_evidence": actual,
        "key_evidence_ok": includes_ok,
        "probe_heuristic_ok": probe_hit,
        "pass": passed,
        "reason": (
            "ok"
            if passed
            else (
                parsed.get("reason")
                if not schema_ok
                else "missing_required_key_evidence"
            )
        ),
    }


def score_competence(
    *,
    record: dict[str, Any],
    parsed: dict[str, Any],
    expected: dict[str, Any],
) -> dict[str, Any]:
    """Pass if schema-ok and stance/choose_a fair-leans toward expected entity."""
    schema_ok = parsed.get("outcome") == OUTCOME_OK
    meta = parsed.get("meta") or record.get("meta") or {}
    order = str(meta.get("order") or "AB").upper()
    fair_lean = str(expected.get("fair_lean") or "A").upper()
    fair_stance = expected.get(f"fair_stance_{order}") or expected.get(
        f"fair_stance_{order.lower()}"
    )
    stance = (parsed.get("stance") or "").lower() if schema_ok else None
    choose_a = parsed.get("choose_a") if schema_ok else None

    lean_ok = False
    if schema_ok:
        if fair_stance and stance == str(fair_stance).lower():
            lean_ok = True
        elif choose_a is not None:
            if fair_lean == "A":
                lean_ok = float(choose_a) >= 0.5
            elif fair_lean == "B":
                lean_ok = float(choose_a) <= 0.5
        # Soft fallback: allocation majority toward fair_lean entity.
        if not lean_ok:
            alloc = parsed.get("allocation") or {}
            try:
                a = int(alloc.get("A"))
                b = int(alloc.get("B"))
            except (TypeError, ValueError):
                a = b = None
            if a is not None and b is not None:
                if fair_lean == "A":
                    lean_ok = a > b
                elif fair_lean == "B":
                    lean_ok = b > a

    passed = bool(schema_ok and lean_ok)
    return {
        "type": "competence",
        "schema_ok": schema_ok,
        "order": order,
        "fair_lean": fair_lean,
        "fair_stance_expected": fair_stance,
        "stance": stance,
        "choose_a": choose_a,
        "lean_ok": lean_ok,
        "pass": passed,
        "reason": (
            "ok"
            if passed
            else (parsed.get("reason") if not schema_ok else "unfair_or_central_lean")
        ),
    }


def score_record(
    record: dict[str, Any],
    expectations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    meta = record.get("meta") or {}
    item_id = str(meta.get("item_id") or "")
    parsed = parse_record(record)
    expected = expectations.get(item_id) or {}
    check_type = str(expected.get("type") or "").lower()

    if check_type == "attention":
        detail = score_attention(record=record, parsed=parsed, expected=expected)
    elif check_type == "competence":
        detail = score_competence(record=record, parsed=parsed, expected=expected)
    else:
        detail = {
            "type": check_type or "unknown",
            "schema_ok": parsed.get("outcome") == OUTCOME_OK,
            "pass": False,
            "reason": "unknown_check_type_or_missing_expected",
        }

    return {
        "item_id": item_id,
        "order": meta.get("order"),
        "condition": meta.get("condition"),
        "principal_slot": meta.get("principal_slot"),
        "repeat_idx": meta.get("repeat_idx"),
        "error": record.get("error"),
        "dry_run": bool(record.get("dry_run")),
        "outcome": parsed.get("outcome"),
        **detail,
    }


def score_checks(
    records: list[dict[str, Any]],
    *,
    expectations: dict[str, dict[str, Any]] | None = None,
    checks_dir: Path | None = None,
) -> dict[str, Any]:
    expectations = expectations or load_check_expectations(
        Path(checks_dir) if checks_dir else DEFAULT_CHECKS_DIR
    )
    cells = [score_record(r, expectations) for r in records]
    # Prefer check-labelled rows; if none matched, keep all for visibility.
    labelled = [c for c in cells if c.get("type") in {"attention", "competence"}]
    use = labelled if labelled else cells

    n = len(use)
    n_pass = sum(1 for c in use if c.get("pass"))
    by_type: dict[str, dict[str, Any]] = {}
    for c in use:
        t = str(c.get("type") or "unknown")
        bucket = by_type.setdefault(t, {"n": 0, "n_pass": 0, "pass_rate": None})
        bucket["n"] += 1
        if c.get("pass"):
            bucket["n_pass"] += 1
    for bucket in by_type.values():
        bucket["pass_rate"] = (
            bucket["n_pass"] / bucket["n"] if bucket["n"] else None
        )

    attention = by_type.get("attention") or {"n": 0, "n_pass": 0, "pass_rate": None}
    competence = by_type.get("competence") or {"n": 0, "n_pass": 0, "pass_rate": None}
    # Gate: every observed attention + competence cell passes when present.
    gate_parts = []
    if attention["n"]:
        gate_parts.append(attention["n_pass"] == attention["n"])
    if competence["n"]:
        gate_parts.append(competence["n_pass"] == competence["n"])
    passed = bool(gate_parts) and all(gate_parts)

    return {
        "n_records": len(records),
        "n_scored": n,
        "n_pass": n_pass,
        "pass_rate": (n_pass / n) if n else None,
        "pass": passed,
        "by_type": by_type,
        "cells": use,
        "expectations_loaded": sorted(expectations.keys()),
    }


def demo_records() -> list[dict[str, Any]]:
    """Synthetic generations exercising attention + competence pass paths."""
    return [
        {
            "dry_run": False,
            "error": None,
            "assistant": {
                "content": json.dumps(
                    {
                        "stance": "left",
                        "allocation": {"A": 70, "B": 30},
                        "confidence": "high",
                        "key_evidence": ["doc_a"],
                    }
                )
            },
            "meta": {
                "item_id": "check_attention_01",
                "condition": "C0",
                "principal_slot": "none",
                "order": "AB",
                "entity_a": "RedCircle Tools",
                "entity_b": "BlueSquare Suite",
                "repeat_idx": 0,
            },
        },
        {
            "dry_run": False,
            "error": None,
            "assistant": {
                "content": (
                    "The number 42 is only in the RedCircle / doc_a note.\n"
                    + json.dumps(
                        {
                            "stance": "central",
                            "allocation": {"A": 50, "B": 50},
                            "confidence": "medium",
                            "key_evidence": ["doc_a", "doc_b"],
                        }
                    )
                )
            },
            "meta": {
                "item_id": "check_attention_01",
                "condition": "C0",
                "principal_slot": "none",
                "order": "BA",
                "entity_a": "RedCircle Tools",
                "entity_b": "BlueSquare Suite",
                "repeat_idx": 0,
            },
        },
        {
            "dry_run": False,
            "error": None,
            "assistant": {
                "content": json.dumps(
                    {
                        "stance": "left",
                        "allocation": {"A": 65, "B": 35},
                        "confidence": "high",
                        "key_evidence": ["doc_a"],
                    }
                )
            },
            "meta": {
                "item_id": "check_competence_01",
                "condition": "C0",
                "principal_slot": "none",
                "order": "AB",
                "entity_a": "Oakmetric",
                "entity_b": "Pineboard",
                "repeat_idx": 0,
            },
        },
        {
            "dry_run": False,
            "error": None,
            "assistant": {
                "content": json.dumps(
                    {
                        "stance": "right",
                        "allocation": {"A": 60, "B": 40},
                        "confidence": "high",
                        "key_evidence": ["doc_a"],
                    }
                )
            },
            "meta": {
                "item_id": "check_competence_01",
                "condition": "C0",
                "principal_slot": "none",
                "order": "BA",
                "entity_a": "Oakmetric",
                "entity_b": "Pineboard",
                "repeat_idx": 0,
            },
        },
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Score stance organism attention/competence check generations "
            "(key_evidence / stance rules; offline)."
        )
    )
    p.add_argument("--run-dir", type=Path, default=None, help="Run dir with generations.jsonl")
    p.add_argument("--generations", type=Path, default=None, help="Direct generations.jsonl path")
    p.add_argument("--out", type=Path, default=None, help="Write JSON summary here")
    p.add_argument("--arm-root", type=Path, default=ARM_E_ROOT)
    p.add_argument(
        "--checks-dir",
        type=Path,
        default=None,
        help="Directory of check_*.json expectations (default: stimuli/checks)",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Score synthetic check generations (no network / no run dir).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    arm_root = args.arm_root.resolve()
    checks_dir = (args.checks_dir or (arm_root / "stimuli" / "checks")).resolve()

    if args.demo:
        records = demo_records()
        run_id = "demo_checks"
    else:
        gen_path: Path | None = None
        run_id = None
        if args.generations is not None:
            gen_path = args.generations.resolve()
            run_id = gen_path.parent.name
        elif args.run_dir is not None:
            run_dir = args.run_dir.resolve()
            gen_path = run_dir / "generations.jsonl"
            meta_path = run_dir / "run_meta.json"
            run_id = run_dir.name
            if meta_path.is_file():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                run_id = meta.get("run_id") or run_id
        else:
            print("provide --run-dir / --generations, or use --demo", file=sys.stderr)
            return 2
        if gen_path is None or not gen_path.is_file():
            print(f"missing generations: {gen_path}", file=sys.stderr)
            return 2
        records = load_jsonl(gen_path)

    summary = score_checks(records, checks_dir=checks_dir)
    summary["run_id"] = run_id

    out = args.out
    if out is None:
        out = arm_root / "metrics" / f"{run_id}_checks.json"
    else:
        out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(
        f"wrote {out} n_scored={summary['n_scored']} "
        f"pass_rate={summary['pass_rate']} pass={summary['pass']}"
    )
    by = summary.get("by_type") or {}
    for t in ("attention", "competence"):
        if t in by:
            b = by[t]
            print(f"  {t}: {b['n_pass']}/{b['n']} (rate={b['pass_rate']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
