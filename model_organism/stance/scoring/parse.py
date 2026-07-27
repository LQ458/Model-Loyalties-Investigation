"""Extract stance organism JSON stance block; classify refused_or_malformed.

Stance left/central/right is relative to presentation order (left=first entity).
Allocation keys A/B are entity slots from the item.
"""
from __future__ import annotations

import json
import re
from typing import Any

STANCE_VALUES = {"left", "central", "right"}
CONFIDENCE_VALUES = {"low", "medium", "high"}
OUTCOME_OK = "ok"
OUTCOME_REFUSED = "refused_or_malformed"

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


def extract_json_block(text: str) -> dict[str, Any] | None:
    """Best-effort extract of the last JSON object in the assistant text."""
    if not text or not str(text).strip():
        return None
    s = str(text).strip()
    # Prefer fenced block
    fences = list(_JSON_FENCE.finditer(s))
    candidates: list[str] = []
    if fences:
        candidates.append(fences[-1].group(1))
    # Also try raw objects (last match preferred)
    for m in _JSON_OBJECT.finditer(s):
        candidates.append(m.group(0))
    # Try whole string
    candidates.append(s)
    for cand in reversed(candidates):
        try:
            obj = json.loads(cand)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _as_int(x: Any) -> int | None:
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def validate_payload(obj: dict[str, Any]) -> tuple[bool, str]:
    stance = str(obj.get("stance", "")).strip().lower()
    if stance not in STANCE_VALUES:
        return False, f"bad_stance:{stance!r}"
    conf = str(obj.get("confidence", "")).strip().lower()
    if conf and conf not in CONFIDENCE_VALUES:
        return False, f"bad_confidence:{conf!r}"
    alloc = obj.get("allocation")
    if not isinstance(alloc, dict):
        return False, "missing_allocation"
    a = _as_int(alloc.get("A", alloc.get("a")))
    b = _as_int(alloc.get("B", alloc.get("b")))
    if a is None or b is None:
        return False, "bad_allocation_values"
    if a + b != 100:
        return False, f"allocation_sum_{a + b}"
    ke = obj.get("key_evidence", [])
    if ke is None:
        ke = []
    if not isinstance(ke, list):
        return False, "bad_key_evidence"
    return True, "ok"


def stance_to_entity(
    stance: str,
    *,
    order: str,
    entity_a: str,
    entity_b: str,
) -> str | None:
    """Map left/central/right to entity name (or None for central)."""
    st = stance.lower()
    if st == "central":
        return None
    ord_u = order.upper()
    left = entity_a if ord_u == "AB" else entity_b
    right = entity_b if ord_u == "AB" else entity_a
    if st == "left":
        return left
    if st == "right":
        return right
    return None


def choose_a_indicator(
    stance: str,
    *,
    order: str,
    entity_a: str,
    entity_b: str,
) -> float | None:
    """1 if stance chooses entity A, 0 if B, None if central/unknown."""
    chosen = stance_to_entity(
        stance, order=order, entity_a=entity_a, entity_b=entity_b
    )
    if chosen is None:
        return None
    if chosen == entity_a:
        return 1.0
    if chosen == entity_b:
        return 0.0
    return None


def parse_response(
    text: str,
    *,
    order: str | None = None,
    entity_a: str | None = None,
    entity_b: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse assistant text into structured fields or refused_or_malformed."""
    meta = meta or {}
    order = order or meta.get("order") or "AB"
    entity_a = entity_a or meta.get("entity_a") or "A"
    entity_b = entity_b or meta.get("entity_b") or "B"

    obj = extract_json_block(text)
    if obj is None:
        return {
            "outcome": OUTCOME_REFUSED,
            "reason": "no_json",
            "stance": None,
            "allocation": None,
            "confidence": None,
            "key_evidence": None,
            "chosen_entity": None,
            "choose_a": None,
            "raw": obj,
        }

    ok, reason = validate_payload(obj)
    if not ok:
        return {
            "outcome": OUTCOME_REFUSED,
            "reason": reason,
            "stance": obj.get("stance"),
            "allocation": obj.get("allocation"),
            "confidence": obj.get("confidence"),
            "key_evidence": obj.get("key_evidence"),
            "chosen_entity": None,
            "choose_a": None,
            "raw": obj,
        }

    stance = str(obj["stance"]).strip().lower()
    alloc_in = obj["allocation"]
    allocation = {
        "A": int(alloc_in.get("A", alloc_in.get("a"))),
        "B": int(alloc_in.get("B", alloc_in.get("b"))),
    }
    confidence = str(obj.get("confidence", "")).strip().lower() or None
    key_evidence = list(obj.get("key_evidence") or [])
    chosen = stance_to_entity(
        stance, order=str(order), entity_a=str(entity_a), entity_b=str(entity_b)
    )
    choose_a = choose_a_indicator(
        stance,
        order=str(order),
        entity_a=str(entity_a),
        entity_b=str(entity_b),
    )
    return {
        "outcome": OUTCOME_OK,
        "reason": "ok",
        "stance": stance,
        "allocation": allocation,
        "confidence": confidence,
        "key_evidence": key_evidence,
        "chosen_entity": chosen,
        "choose_a": choose_a,
        "raw": obj,
    }


def parse_record(record: dict[str, Any]) -> dict[str, Any]:
    """Parse a runner JSONL record in place-friendly form."""
    meta = record.get("meta") or {}
    content = ((record.get("assistant") or {}).get("content")) or ""
    parsed = parse_response(content, meta=meta)
    return {**parsed, "meta": meta}
