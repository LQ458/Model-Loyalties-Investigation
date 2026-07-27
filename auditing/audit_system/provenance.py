from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ContinuationExtraction:
    attacker_prefill: str
    raw_content: str
    target_continuation: str
    rendered_content: str
    status: str
    method: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalized_prefix_match(raw: str, prefix: str) -> re.Match[str] | None:
    tokens = [re.escape(token) for token in re.findall(r"\S+", prefix)]
    if not tokens:
        return None
    pattern = r"^\s*" + r"\s+".join(tokens) + r"(?=\s|$)"
    return re.match(pattern, raw, flags=re.IGNORECASE)


def extract_continuation(
    raw_content: Any,
    attacker_prefill: Any = "",
    *,
    allow_continuation_only: bool = True,
) -> ContinuationExtraction:
    """Separate attacker-authored prefill from target output.

    A provider may return only the continuation or the whole prefill-plus-
    continuation. Exact and whitespace-normalized prefix matches are verified.
    Ambiguous full responses are never silently counted as target output.
    """
    raw = str(raw_content or "")
    prefill = str(attacker_prefill or "")
    if not prefill:
        return ContinuationExtraction(prefill, raw, raw, raw, "verified", "no_prefill")
    if raw.startswith(prefill):
        return ContinuationExtraction(
            prefill, raw, raw[len(prefill):], raw, "verified", "exact_prefix"
        )
    match = _normalized_prefix_match(raw, prefill)
    if match:
        return ContinuationExtraction(
            prefill,
            raw,
            raw[match.end():],
            raw,
            "verified",
            "normalized_whitespace_prefix",
        )
    # A response that begins like the supplied prefill but then diverges could
    # be a provider-rendered full response or a continuation-only response.
    # It cannot safely be attributed to the target.
    raw_tokens = re.findall(r"\w+", raw.casefold())
    prefill_tokens = re.findall(r"\w+", prefill.casefold())
    common_prefix = 0
    for raw_token, prefill_token in zip(raw_tokens, prefill_tokens):
        if raw_token != prefill_token:
            break
        common_prefix += 1
    if common_prefix and common_prefix < len(prefill_tokens):
        return ContinuationExtraction(
            prefill, raw, "", raw, "ambiguous", "partial_prefix_divergence"
        )
    if allow_continuation_only:
        return ContinuationExtraction(
            prefill, raw, raw, prefill + raw, "verified", "continuation_only"
        )
    return ContinuationExtraction(prefill, raw, "", raw, "ambiguous", "no_prefix_match")


def extract_reasoning_continuation(
    raw_reasoning: Any,
    attacker_prefill: Any = "",
) -> ContinuationExtraction:
    return extract_continuation(raw_reasoning, attacker_prefill)


def split_self_interrogation(raw_content: Any) -> dict[str, str]:
    """Split a single-completion user/assistant simulation for provenance."""
    text = str(raw_content or "")
    match = re.search(r"(?is)\buser\s*:\s*(.*?)\bassistant\s*:\s*(.*)$", text)
    if not match:
        return {
            "generated_user": "",
            "target_continuation": text,
            "split_status": "no_generated_user_marker",
        }
    return {
        "generated_user": match.group(1).strip(),
        "target_continuation": match.group(2).strip(),
        "split_status": "verified",
    }
