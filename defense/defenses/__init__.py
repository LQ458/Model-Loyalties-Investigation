"""Non-CoT defense defenses."""

from .capability_guard import (
    CapabilityDecision,
    CapabilityGuard,
    CapabilityPolicy,
    ToolProposal,
)
from .entity_anonymization import (
    AnonymizationPlan,
    anonymize_text,
    borda_consensus,
    compare_rankings_blind,
    make_plan,
    make_unique_plans,
    restore_text,
    score_principal_after_unblinding,
)

__all__ = [
    "CapabilityDecision",
    "CapabilityGuard",
    "CapabilityPolicy",
    "ToolProposal",
    "AnonymizationPlan",
    "anonymize_text",
    "borda_consensus",
    "compare_rankings_blind",
    "make_plan",
    "make_unique_plans",
    "restore_text",
    "score_principal_after_unblinding",
]
