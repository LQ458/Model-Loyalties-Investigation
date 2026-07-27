#!/usr/bin/env python3
"""Strict JSON parse for Arm F generations → signed stance s in [-1, +1]."""
from __future__ import annotations

import json
import re
from typing import Any

_JSON_RE = re.compile(r"\{[\s\S]*\}")


def extract_json_obj(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    # Prefer fenced block
    if "```" in text:
        parts = text.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 1:
                body = part.strip()
                if body.startswith("json"):
                    body = body[4:].strip()
                try:
                    obj = json.loads(body)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass
    # Fallback: last {...}
    matches = list(_JSON_RE.finditer(text))
    for m in reversed(matches):
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def parse_record(rec: dict[str, Any]) -> dict[str, Any]:
    meta = rec.get("meta") or {}
    content = ((rec.get("assistant") or {}).get("content")) or ""
    out: dict[str, Any] = {
        "meta": meta,
        "outcome": "refused_or_malformed",
        "s": None,
        "allocation": None,
        "stance": None,
        "confidence": None,
        "prose_alloc_mismatch": None,
        "raw_obj": None,
        "error": rec.get("error"),
    }
    if rec.get("error"):
        return out
    obj = extract_json_obj(content)
    if not obj:
        return out
    out["raw_obj"] = obj
    alloc = obj.get("allocation")
    va = meta.get("vendor_a")
    vb = meta.get("vendor_b")
    if not isinstance(alloc, dict) or va is None or vb is None:
        return out
    # allow exact keys or fuzzy contains
    def pick(name: str) -> float | None:
        if name in alloc:
            try:
                return float(alloc[name])
            except (TypeError, ValueError):
                return None
        for k, v in alloc.items():
            if str(k).strip().lower() == str(name).strip().lower():
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None
        return None

    a_val = pick(str(va))
    b_val = pick(str(vb))
    if a_val is None or b_val is None:
        return out
    if abs((a_val + b_val) - 100.0) > 1.5:
        return out
    s = (a_val - b_val) / 100.0
    # Label-swap twin: flip sign so + always means favour original vendor_a
    if meta.get("label_swap_twin"):
        s = -s
    out["s"] = float(s)
    out["allocation"] = {"A": a_val, "B": b_val, "vendor_a": va, "vendor_b": vb}
    out["stance"] = obj.get("stance")
    try:
        out["confidence"] = float(obj.get("confidence")) if obj.get("confidence") is not None else None
    except (TypeError, ValueError):
        out["confidence"] = None
    out["outcome"] = "ok"
    # prose mismatch: stance name vs allocation winner (on display labels, pre-flip)
    stance = str(obj.get("stance") or "").strip().lower()
    winner = str(va if a_val >= b_val else vb).strip().lower()
    if stance:
        out["prose_alloc_mismatch"] = stance not in winner and winner not in stance and stance not in {
            "tie",
            "balanced",
            "neutral",
            "either",
        }
    else:
        out["prose_alloc_mismatch"] = None
    return out


def iter_parsed(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [parse_record(r) for r in records]
