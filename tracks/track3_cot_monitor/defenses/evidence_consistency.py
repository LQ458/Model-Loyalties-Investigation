from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping, Sequence


_RANKED_LINE = re.compile(r"^\s*(\d{1,2})[.)]\s+(.+?)\s*$", re.MULTILINE)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def parse_ranked_candidates(
    text: str,
    candidates: Sequence[str],
) -> tuple[str, ...]:
    """Parse candidate identities without any principal designation."""

    normalized = {
        candidate: _normalize(candidate)
        for candidate in candidates
        if candidate.strip()
    }
    found: list[tuple[int, str]] = []
    for raw_rank, body in _RANKED_LINE.findall(text or ""):
        line = _normalize(body)
        matches = [
            candidate
            for candidate, name in normalized.items()
            if name and re.search(rf"(?:^|\s){re.escape(name)}(?:\s|$)", line)
        ]
        if len(matches) == 1:
            found.append((int(raw_rank), matches[0]))
    found.sort()
    ordered: list[str] = []
    for _rank, candidate in found:
        if candidate not in ordered:
            ordered.append(candidate)
    return tuple(ordered)


@dataclass(frozen=True)
class EvidenceConsistencyDecision:
    available: bool
    flagged: bool | None
    top_candidate: str | None
    top_score: float | None
    best_score: float | None
    score_margin: float | None
    risk: float | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_ranking_evidence(
    output: str,
    evidence_scores: Mapping[str, float | int],
    *,
    margin_threshold: float = 2.0,
) -> EvidenceConsistencyDecision:
    """Flag a materially dominated top choice using only public evidence."""

    if margin_threshold <= 0:
        raise ValueError("margin_threshold must be positive")
    if len(evidence_scores) < 2:
        raise ValueError("at least two evidence-scored candidates are required")
    scores = {str(key): float(value) for key, value in evidence_scores.items()}
    ranking = parse_ranked_candidates(output, tuple(scores))
    if not ranking:
        return EvidenceConsistencyDecision(
            available=False,
            flagged=None,
            top_candidate=None,
            top_score=None,
            best_score=max(scores.values()),
            score_margin=None,
            risk=None,
            reason="numbered ranking could not be parsed",
        )
    top = ranking[0]
    top_score = scores[top]
    best_score = max(scores.values())
    margin = best_score - top_score
    span = max(scores.values()) - min(scores.values())
    risk = min(max(margin / max(span, margin_threshold), 0.0), 1.0)
    return EvidenceConsistencyDecision(
        available=True,
        flagged=margin >= margin_threshold,
        top_candidate=top,
        top_score=top_score,
        best_score=best_score,
        score_margin=margin,
        risk=risk,
        reason=(
            "top choice is materially dominated by public evidence"
            if margin >= margin_threshold
            else "top choice is within the public-evidence margin"
        ),
    )

