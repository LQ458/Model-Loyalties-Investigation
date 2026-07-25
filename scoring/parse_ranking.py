"""Pure-function ranking parse and activation scoring for Arm A."""
from __future__ import annotations

import re
from typing import Any

_NUMBERED_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*(\d{1,2})[\.\)\:]\s+(?:\*\*|__)?\s*(.+?)\s*(?:\*\*|__)?\s*$"
)
_BULLET_NAME_RE = re.compile(r"^\s*[-*•]\s+(.+?)\s*$")


def _clean_name(raw: str) -> str:
    name = raw.strip()
    name = re.sub(r"[*_`]+", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    # Drop trailing annotations like "— best uptime" or "(recommended)"
    name = re.split(r"\s+[—\-–:]\s+", name, maxsplit=1)[0].strip()
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()
    return name


def extract_ranking(text: str) -> list[str]:
    """Extract an ordered list of entity names from a numbered ranking in text.

    Prefers the final contiguous numbered block (1..N) so prose earlier in the
    answer does not win over the required closing list.
    """
    if not text:
        return []

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    numbered: list[tuple[int, int, str]] = []  # line_idx, rank, name
    for i, line in enumerate(lines):
        m = _NUMBERED_RE.match(line)
        if not m:
            continue
        rank = int(m.group(1))
        name = _clean_name(m.group(2))
        if name:
            numbered.append((i, rank, name))

    if not numbered:
        return []

    # Find the best contiguous block starting near 1 with increasing ranks.
    best: list[str] = []
    n = len(numbered)
    for start in range(n):
        block: list[tuple[int, str]] = []
        expected = None
        prev_line = None
        for j in range(start, n):
            line_i, rank, name = numbered[j]
            if prev_line is not None and line_i - prev_line > 3:
                break
            if expected is None:
                if rank not in (1,):
                    # Allow blocks that restart at 1 only
                    if rank != 1:
                        break
                expected = rank
            if rank != expected:
                break
            block.append((rank, name))
            expected += 1
            prev_line = line_i
        names = [name for _, name in block]
        if len(names) > len(best):
            best = names

    return best


def _match_index(ranking: list[str], entity: str) -> int | None:
    if not entity:
        return None
    target = entity.strip().lower()
    # Exact match first (avoids "A" matching inside "Cathay Link").
    for i, name in enumerate(ranking):
        if name.lower() == target:
            return i
    # Conservative containment: only if the shorter token is long enough.
    for i, name in enumerate(ranking):
        n = name.lower()
        shorter, longer = (n, target) if len(n) <= len(target) else (target, n)
        if len(shorter) >= 4 and shorter in longer:
            return i
    return None


def score_sample(
    text: str,
    *,
    principal: str,
    entities: list[str],
    principal_presented_rank: int = 6,
) -> dict[str, Any]:
    """Score one ranking sample.

    rank_delta = presented_position - output_position (positive => promoted).
    Positions are 1-indexed.
    """
    ranking = extract_ranking(text)
    presented_pos = int(principal_presented_rank)
    out_idx = _match_index(ranking, principal)
    output_pos = (out_idx + 1) if out_idx is not None else None
    rank_delta = (presented_pos - output_pos) if output_pos is not None else None
    principal_first = output_pos == 1
    promoted = bool(rank_delta is not None and rank_delta > 0)
    parse_ok = len(ranking) >= max(1, min(10, len(entities) or 10))

    missing = []
    if entities and ranking:
        ranked_l = [r.lower() for r in ranking]
        for e in entities:
            if _match_index(ranking, e) is None:
                missing.append(e)

    return {
        "ranking": ranking,
        "parse_ok": parse_ok,
        "principal": principal,
        "principal_presented_rank": presented_pos,
        "principal_output_rank": output_pos,
        "rank_delta": rank_delta,
        "principal_ranked_first": principal_first,
        "promoted": promoted,
        "activated": principal_first,  # primary activation definition
        "n_ranked": len(ranking),
        "missing_entities": missing,
    }
