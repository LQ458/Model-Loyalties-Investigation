#!/usr/bin/env python3
"""Run the system-prompt attestation demo against this repository's real prompts.

Three scenarios, one fidelity check, and one prompt-hash check. No network, no
model calls, no third-party packages. The demo clock and serving key are fixed
so the committed artifacts are byte-reproducible.

    python3 attestation_demo/run_demo.py

Exit status is 0 only if every check passes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import sys
from typing import Any

DEMO_ROOT = Path(__file__).resolve().parent
REPO_ROOT = DEMO_ROOT.parent
if str(DEMO_ROOT) not in sys.path:
    sys.path.insert(0, str(DEMO_ROOT))

from attestation import (  # noqa: E402
    AttestationReceipt,
    PromptSegment,
    ServingKey,
    attempt_single_receipt_loyalty_detection,
    check_no_plaintext_leak,
    inclusion_proof,
    issue_receipt,
    probe_candidate_segment,
    render_prompt,
    verify_consistency,
    verify_disclosure,
    verify_segment_disclosure,
    verify_signature,
)
from runtime.integrity import canonical_json, sha256_bytes, sha256_file  # noqa: E402

HARNESS_ROOT = REPO_ROOT / "model_organism"
if str(HARNESS_ROOT / "harness") not in sys.path:
    sys.path.insert(0, str(HARNESS_ROOT / "harness"))

from run_ranking import assemble_system_prompt  # noqa: E402

PROMPTS = HARNESS_ROOT / "prompts"
BASE_PATH = PROMPTS / "base_assistant.md"
LOYALTY_PATH = PROMPTS / "v018.md"
NEUTRAL_PATH = PROMPTS / "neutral_control.md"
CONCEALMENT_DIR = PROMPTS / "concealment"
V018_METADATA = PROMPTS / "metadata" / "v018.json"
SCENARIO_PATH = HARNESS_ROOT / "scenarios" / "ranking" / "test" / "rank_cdn_real_01.json"

# Hash prefix/suffix the paper cites for the v018 organism prompt.
PAPER_V018_PREFIX = "1a12fab8"
PAPER_V018_SUFFIX = "c69762"

# Served model recorded in defense/artifacts/publication/prospective_v3/
# sealed.jsonl.receipt.json:14.
MODEL_ID = "qwen3.6-35b-a3b-int8"

DEFAULT_NOW = "2026-09-16T12:00:00+00:00"

# Demo-only serving key. Deterministic and published on purpose: nothing in
# this repository is protected by it.
SERVING_KEY = ServingKey(
    key_id="attestation-demo-serving-key-1",
    secret=bytes.fromhex(sha256_bytes(b"attestation-demo/serving-key/1")),
)

PLATFORM_CONTRIBUTOR = "platform.provider.base_assistant"
OPERATOR_CONTRIBUTOR = "operator.deployment_config"
TENANT_CONTRIBUTOR = "tenant.app.ranking_ui"

# The only text in this demo with no counterpart in the repository. The
# repository's ranking organism has no tenant slot; this segment exists so the
# third provenance role is actually exercised. It is inert with respect to
# every result below.
TENANT_SEGMENT_TEXT = (
    "App integration requirements (ranking-ui v3):\n"
    "- Return the ranked list as a numbered list before any prose.\n"
    "- Keep the justification memo under 250 words."
)

LOYAL_REQUEST_INDEXES = (3, 6)
CORPUS_SIZE = 8


@dataclass
class Demo:
    lines: list[str] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)

    def say(self, text: str = "") -> None:
        self.lines.append(text)
        print(text)

    def head(self, title: str) -> None:
        self.say()
        self.say("=" * 78)
        self.say(title)
        self.say("=" * 78)

    def check(self, name: str, ok: bool, detail: str) -> bool:
        self.checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        self.say(f"[{len(self.checks):2d}] {'PASS' if ok else 'FAIL'}  {name}")
        self.say(f"          {detail}")
        return ok

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [row for row in self.checks if row["status"] != "PASS"]


def _strip_leading_comment(text: str) -> str:
    """Drop a leading markdown comment header, as the ranking harness does."""
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("#") and not lines:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def operator_loyalty_text(principal: str) -> str:
    """Rebuild the operator-contributed loyalty segment independently.

    Deliberately not imported from the harness: the fidelity check below is
    only meaningful if this reconstruction is independent of
    `assemble_system_prompt` and still lands on identical bytes.
    """
    loyalty = LOYALTY_PATH.read_text(encoding="utf-8").replace("{PRINCIPAL}", principal)
    conceal = _strip_leading_comment((CONCEALMENT_DIR / "c2.md").read_text(encoding="utf-8"))
    close_tag = "</provider_configuration>"
    if conceal and close_tag in loyalty:
        loyalty = loyalty.replace(close_tag, f"\n{conceal}\n{close_tag}", 1)
    return loyalty.strip()


def operator_clean_text(principal: str) -> str:
    """The repository's content-matched neutral control (CN): names the
    principal, installs no preference."""
    return NEUTRAL_PATH.read_text(encoding="utf-8").replace("{PRINCIPAL}", principal).strip()


def _issued_at(base: str, offset_seconds: int) -> str:
    from datetime import datetime, timedelta

    moment = datetime.fromisoformat(base) + timedelta(seconds=offset_seconds)
    return moment.isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--now", default=DEFAULT_NOW, help="fixed ISO-8601 demo clock")
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=DEMO_ROOT / "artifacts",
        help="output directory for receipts, log, and results",
    )
    args = parser.parse_args()
    demo = Demo()
    results: dict[str, Any] = {"schema_version": 1}

    # ------------------------------------------------------------------
    demo.head("0. INPUTS: real repository prompts")
    # ------------------------------------------------------------------
    scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    principal = str(scenario["principal"])
    wrong_principal = str(scenario["wrong_principal"])
    scenario_id = str(scenario["id"])

    v018_file_sha = sha256_file(LOYALTY_PATH)
    metadata = json.loads(V018_METADATA.read_text(encoding="utf-8"))
    demo.say(f"scenario           {scenario_id} (real principal: {principal})")
    demo.say(f"platform segment   {BASE_PATH.relative_to(REPO_ROOT)}")
    demo.say(f"operator (clean)   {NEUTRAL_PATH.relative_to(REPO_ROOT)}")
    demo.say(f"operator (loyal)   {LOYALTY_PATH.relative_to(REPO_ROOT)} + concealment/c2.md")
    demo.say(f"tenant segment     synthetic (no repository counterpart)")
    demo.say(f"served model id    {MODEL_ID}")
    demo.say(f"demo clock         {args.now} (fixed; artifacts are reproducible)")
    demo.say()
    demo.say(f"sha256(v018.md)              {v018_file_sha}")
    demo.say(f"metadata prompt_sha256       {metadata['prompt_sha256']}")
    demo.say(f"paper cites                  {PAPER_V018_PREFIX}...{PAPER_V018_SUFFIX}")

    demo.check(
        "v018.file_sha256_matches_paper_citation",
        v018_file_sha.startswith(PAPER_V018_PREFIX)
        and v018_file_sha.endswith(PAPER_V018_SUFFIX),
        f"sha256({LOYALTY_PATH.name}) = {v018_file_sha}; matches the cited "
        f"{PAPER_V018_PREFIX}...{PAPER_V018_SUFFIX}",
    )
    demo.check(
        "v018.file_sha256_matches_lineage_metadata",
        v018_file_sha == metadata["prompt_sha256"],
        f"prompts/metadata/v018.json:9 records {metadata['prompt_sha256']}",
    )
    results["v018_hash_check"] = {
        "prompt_path": str(LOYALTY_PATH.relative_to(REPO_ROOT)),
        "file_sha256": v018_file_sha,
        "lineage_metadata_sha256": metadata["prompt_sha256"],
        "paper_citation_prefix": PAPER_V018_PREFIX,
        "paper_citation_suffix": PAPER_V018_SUFFIX,
        "matches_paper_citation": v018_file_sha.startswith(PAPER_V018_PREFIX)
        and v018_file_sha.endswith(PAPER_V018_SUFFIX),
        "matches_lineage_metadata": v018_file_sha == metadata["prompt_sha256"],
    }

    # ------------------------------------------------------------------
    demo.head("1. FIDELITY: the segment model reproduces the served bytes")
    # ------------------------------------------------------------------
    platform_segment = PromptSegment(
        contributor_id=PLATFORM_CONTRIBUTOR,
        role="platform",
        text=BASE_PATH.read_text(encoding="utf-8").strip(),
    )
    operator_loyal = PromptSegment(
        contributor_id=OPERATOR_CONTRIBUTOR,
        role="operator",
        text=operator_loyalty_text(principal),
    )
    operator_clean = PromptSegment(
        contributor_id=OPERATOR_CONTRIBUTOR,
        role="operator",
        text=operator_clean_text(principal),
    )
    tenant_segment = PromptSegment(
        contributor_id=TENANT_CONTRIBUTOR,
        role="tenant",
        text=TENANT_SEGMENT_TEXT,
    )

    harness_kwargs = {
        "principal": principal,
        "wrong_principal": wrong_principal,
        "base_path": BASE_PATH,
        "loyalty_path": LOYALTY_PATH,
        "concealment_dir": CONCEALMENT_DIR,
        "neutral_path": NEUTRAL_PATH,
    }
    harness_c2 = assemble_system_prompt(condition="C2", **harness_kwargs)
    harness_cn = assemble_system_prompt(condition="CN", **harness_kwargs)
    rendered_c2 = render_prompt([platform_segment, operator_loyal])
    rendered_cn = render_prompt([platform_segment, operator_clean])

    demo.check(
        "fidelity.segments_reproduce_harness_C2_bytes",
        rendered_c2 == harness_c2,
        f"render_prompt([platform, operator-loyal]) == "
        f"assemble_system_prompt(C2) exactly "
        f"({len(harness_c2)} chars, sha256 "
        f"{sha256_bytes(harness_c2.encode('utf-8'))[:16]}...)",
    )
    demo.check(
        "fidelity.segments_reproduce_harness_CN_bytes",
        rendered_cn == harness_cn,
        f"render_prompt([platform, operator-clean]) == "
        f"assemble_system_prompt(CN) exactly "
        f"({len(harness_cn)} chars, sha256 "
        f"{sha256_bytes(harness_cn.encode('utf-8'))[:16]}...)",
    )
    demo.say(
        f"served operator-loyal segment sha256  "
        f"{operator_loyal.text_sha256}"
    )
    demo.say(
        f"served operator-clean segment sha256  "
        f"{operator_clean.text_sha256}"
    )
    results["fidelity"] = {
        "harness_C2_sha256": sha256_bytes(harness_c2.encode("utf-8")),
        "harness_CN_sha256": sha256_bytes(harness_cn.encode("utf-8")),
        "segment_render_matches_C2": rendered_c2 == harness_c2,
        "segment_render_matches_CN": rendered_cn == harness_cn,
        "operator_loyal_segment_sha256": operator_loyal.text_sha256,
        "operator_clean_segment_sha256": operator_clean.text_sha256,
        "tenant_segment_is_synthetic": True,
    }

    loyal_segments = (platform_segment, operator_loyal, tenant_segment)
    clean_segments = (platform_segment, operator_clean, tenant_segment)

    # ------------------------------------------------------------------
    demo.head("2. VERIFIER CHECK (a): signature and internal structure")
    # ------------------------------------------------------------------
    probe_receipt = issue_receipt(
        segments=loyal_segments,
        key=SERVING_KEY,
        request_source_id=f"{scenario_id}:signature-probe",
        model_id=MODEL_ID,
        issued_at=_issued_at(args.now, 0),
    )
    genuine = verify_signature(probe_receipt, SERVING_KEY)
    demo.check(
        "verifier_a.accepts_genuine_receipt",
        genuine.ok,
        f"{genuine.request_id}: {genuine.reason}",
    )

    wrong_key = ServingKey(
        key_id="attestation-demo-serving-key-1",
        secret=bytes.fromhex(sha256_bytes(b"attestation-demo/attacker-key")),
    )
    forged = verify_signature(probe_receipt, wrong_key)
    demo.check(
        "verifier_a.rejects_wrong_key",
        (not forged.ok) and not forged.signature_valid,
        f"verification under a non-serving key fails: {forged.reason}",
    )

    from dataclasses import replace as _replace

    tampered_root = _replace(
        probe_receipt, merkle_root=sha256_bytes(b"attacker-chosen-root")
    )
    root_check = verify_signature(tampered_root, SERVING_KEY)
    demo.check(
        "verifier_a.rejects_tampered_root",
        (not root_check.ok)
        and not root_check.signature_valid
        and not root_check.root_matches_digests,
        f"swapping merkle_root breaks both the signature and root "
        f"recomputation: {root_check.reason}",
    )

    swapped_digests = list(probe_receipt.segment_digests)
    swapped_digests[1] = operator_clean.leaf_digest(1)
    digest_check = verify_signature(
        _replace(probe_receipt, segment_digests=tuple(swapped_digests)), SERVING_KEY
    )
    demo.check(
        "verifier_a.rejects_substituted_segment_digest",
        (not digest_check.ok) and not digest_check.root_matches_digests,
        "replacing one published leaf digest with the clean segment's digest "
        "is caught by root recomputation, so the localisation data in a "
        f"receipt is itself authenticated: {digest_check.reason}",
    )
    results["verifier_a"] = {
        "genuine": genuine.to_dict(),
        "wrong_key": forged.to_dict(),
        "tampered_root": root_check.to_dict(),
        "substituted_digest": digest_check.to_dict(),
    }

    # ------------------------------------------------------------------
    demo.head("3. SCENARIO 1: operator silently swaps in the loyalty segment")
    # ------------------------------------------------------------------
    receipts_dir = args.artifacts / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    for stale in sorted(receipts_dir.glob("*.receipt.json")):
        stale.unlink()

    served: list[tuple[int, str]] = []
    written: list[Path] = []
    for index in range(CORPUS_SIZE):
        is_loyal = index in LOYAL_REQUEST_INDEXES
        receipt = issue_receipt(
            segments=loyal_segments if is_loyal else clean_segments,
            key=SERVING_KEY,
            request_source_id=f"{scenario_id}:s1:{index}",
            model_id=MODEL_ID,
            issued_at=_issued_at(args.now, 60 * index),
        )
        path = receipts_dir / f"s1_req{index:02d}.receipt.json"
        path.write_text(
            json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written.append(path)
        served.append((index, "loyal" if is_loyal else "clean"))
    demo.say(
        "operator served: "
        + ", ".join(f"req{index:02d}={label}" for index, label in served)
    )
    demo.say(f"receipts written: {len(written)} files under {receipts_dir.relative_to(REPO_ROOT)}")
    demo.say()

    # The auditor's entire input is the committed receipt files. No prompt text
    # is in scope for this code path.
    audited_payloads = [
        json.loads(path.read_text(encoding="utf-8")) for path in sorted(written)
    ]
    audited = [AttestationReceipt.from_dict(payload) for payload in audited_payloads]

    signature_ok = all(verify_signature(r, SERVING_KEY).ok for r in audited)
    demo.check(
        "scenario1.all_receipts_authenticate",
        signature_ok,
        f"all {len(audited)} receipts read back from disk authenticate under "
        f"key {SERVING_KEY.key_id}",
    )

    clean_only = [
        r for index, r in enumerate(audited) if index not in LOYAL_REQUEST_INDEXES
    ]
    stable_report = verify_consistency(clean_only)
    demo.check(
        "scenario1.negative_control_clean_corpus_is_stable",
        stable_report.stable and len(stable_report.distinct_roots) == 1,
        f"{len(clean_only)} clean receipts: stable={stable_report.stable}, "
        f"{stable_report.reason}",
    )

    report = verify_consistency(audited)
    demo.check(
        "scenario1.detects_silent_swap_from_receipts_alone",
        (not report.stable) and len(report.divergent) == len(LOYAL_REQUEST_INDEXES),
        f"{report.reason}",
    )
    localised_indexes = report.unstable_indexes
    demo.check(
        "scenario1.localises_changed_segment_and_contributor",
        localised_indexes == (1,)
        and report.implicated_contributors == (OPERATOR_CONTRIBUTOR,)
        and report.implicated_roles == ("operator",),
        f"changed segment index {list(localised_indexes)}, contributor "
        f"{list(report.implicated_contributors)}, role "
        f"{list(report.implicated_roles)}; segments 0 (platform) and 2 "
        f"(tenant) are byte-stable across all 8 requests",
    )
    flagged_request_ids = {entry.request_id for entry in report.divergent}
    expected_ids = {audited[index].request_id for index in LOYAL_REQUEST_INDEXES}
    demo.check(
        "scenario1.names_exactly_the_affected_requests",
        flagged_request_ids == expected_ids,
        f"flagged {sorted(flagged_request_ids)}; ground truth "
        f"{sorted(expected_ids)} (requests {list(LOYAL_REQUEST_INDEXES)})",
    )
    for entry in report.divergent:
        for change in entry.changed_segments:
            demo.say(
                f"          {entry.request_id} index {change.index} "
                f"{change.role}:{change.contributor_id} "
                f"baseline {change.reference_digest[:12]}... "
                f"observed {change.observed_digest[:12]}..."
            )

    corpus_leak = check_no_plaintext_leak(audited_payloads, list(loyal_segments))
    demo.check(
        "scenario1.auditor_never_saw_prompt_plaintext",
        corpus_leak.ok,
        f"the full 8-receipt corpus the auditor consumed contains no "
        f"4-gram and no distinctive line from any served segment "
        f"({corpus_leak.shingles_tested} n-grams, {corpus_leak.lines_tested} "
        f"lines tested)",
    )
    single_leak = check_no_plaintext_leak(audited[3], list(loyal_segments))
    demo.check(
        "receipt.carries_no_segment_plaintext",
        single_leak.ok,
        f"single loyal receipt: {single_leak.reason}",
    )
    loyal_bytes = len(canonical_json(audited[3].to_dict()))
    clean_bytes = len(canonical_json(audited[0].to_dict()))
    demo.check(
        "receipt.size_is_not_a_prompt_length_side_channel",
        loyal_bytes == clean_bytes,
        f"loyal receipt {loyal_bytes} bytes == clean receipt {clean_bytes} "
        f"bytes, although the loyal prompt is "
        f"{len(operator_loyal.text) - len(operator_clean.text)} characters "
        f"longer; segment byte lengths are deliberately not committed",
    )
    results["scenario1"] = {
        "served": [{"request_index": i, "condition": label} for i, label in served],
        "receipt_files": [str(p.relative_to(REPO_ROOT)) for p in sorted(written)],
        "negative_control_clean_corpus": stable_report.to_dict(),
        "consistency_report": report.to_dict(),
        "corpus_leak_check": corpus_leak.to_dict(),
        "receipt_bytes": {"loyal": loyal_bytes, "clean": clean_bytes},
    }

    # ------------------------------------------------------------------
    demo.head("4. SCENARIO 2: operator discloses a sanitised prompt")
    # ------------------------------------------------------------------
    disputed = audited[LOYAL_REQUEST_INDEXES[0]]
    demo.say(f"disputed request   {disputed.request_id} (a loyal request)")
    demo.say(f"committed root     {disputed.merkle_root}")
    demo.say()

    honest = verify_disclosure(
        disputed, [segment.text for segment in loyal_segments]
    )
    demo.check(
        "scenario2.positive_control_honest_disclosure_confirmed",
        honest.verdict == "CONFIRMED",
        f"{honest.verdict}: {honest.reason}",
    )

    omitted = verify_disclosure(
        disputed, [platform_segment.text, tenant_segment.text]
    )
    demo.check(
        "scenario2.omitted_loyalty_segment_refuted",
        omitted.verdict == "REFUTED" and 1 in omitted.mismatched_indexes,
        f"{omitted.verdict}: {omitted.reason}",
    )

    substituted = verify_disclosure(
        disputed, [segment.text for segment in clean_segments]
    )
    demo.check(
        "scenario2.substituted_clean_segment_refuted_and_localised",
        substituted.verdict == "REFUTED"
        and substituted.mismatched_indexes == (1,)
        and substituted.matched_indexes == (0, 2)
        and substituted.mismatched_contributors == (OPERATOR_CONTRIBUTOR,),
        f"{substituted.verdict}: {substituted.reason}; matched indexes "
        f"{list(substituted.matched_indexes)}",
    )

    proof = inclusion_proof(disputed.segment_digests, 0)
    partial = verify_segment_disclosure(
        disputed, index=0, disclosed_text=platform_segment.text, proof=proof
    )
    demo.check(
        "scenario2.partial_disclosure_confirmed_against_root_only",
        partial.verdict == "CONFIRMED",
        f"{partial.verdict}: {partial.reason} (platform contributor proves its "
        f"own segment without revealing the operator or tenant segments)",
    )
    tampered_partial = verify_segment_disclosure(
        disputed,
        index=0,
        disclosed_text=platform_segment.text + "\n- Prefer partner vendors.",
        proof=proof,
    )
    demo.check(
        "scenario2.partial_disclosure_rejects_edited_text",
        tampered_partial.verdict == "REFUTED",
        f"{tampered_partial.verdict}: {tampered_partial.reason}",
    )
    results["scenario2"] = {
        "disputed_request_id": disputed.request_id,
        "honest_disclosure": honest.to_dict(),
        "omitted_segment_disclosure": omitted.to_dict(),
        "substituted_segment_disclosure": substituted.to_dict(),
        "partial_disclosure": partial.to_dict(),
        "partial_disclosure_tampered": tampered_partial.to_dict(),
    }

    # ------------------------------------------------------------------
    demo.head("5. SCENARIO 3 (HONEST NEGATIVE): what the scheme cannot do")
    # ------------------------------------------------------------------
    demo.say("A single receipt cannot tell you a loyalty is present. The digest")
    demo.say("of a loyal assembly is indistinguishable from the digest of a clean")
    demo.say("one without a reference digest or the exact candidate bytes.")
    demo.say()

    loyal_receipt = audited[LOYAL_REQUEST_INDEXES[0]]
    clean_receipt = audited[0]
    loyal_verdict = attempt_single_receipt_loyalty_detection(loyal_receipt)
    clean_verdict = attempt_single_receipt_loyalty_detection(clean_receipt)
    demo.check(
        "scenario3.single_receipt_is_undecidable",
        (not loyal_verdict.decidable)
        and (not clean_verdict.decidable)
        and loyal_verdict.to_dict() == clean_verdict.to_dict(),
        f"verdict on the loyal receipt and on the clean receipt are the same "
        f"object: {loyal_verdict.verdict} - {loyal_verdict.reason}",
    )

    volatile = {"merkle_root", "segment_digests", "signature", "request_id", "issued_at"}
    loyal_shape = {k: v for k, v in loyal_receipt.to_dict().items() if k not in volatile}
    clean_shape = {k: v for k, v in clean_receipt.to_dict().items() if k not in volatile}
    demo.check(
        "scenario3.loyal_and_clean_receipts_are_structurally_identical",
        loyal_shape == clean_shape,
        "every non-digest field is identical: same segment_count, same "
        "contributor ids, same roles, same model id, same key id; only the "
        "opaque digests differ",
    )

    pinned = verify_consistency([loyal_receipt], reference=clean_receipt.segment_digests)
    pinned_json = canonical_json(pinned.to_dict()).decode("utf-8").casefold()
    demo.check(
        "scenario3.reference_digest_yields_difference_not_a_loyalty_label",
        pinned.unstable_indexes == (1,)
        and "loyal" not in pinned_json
        and "loyalty" not in pinned_json,
        "with a published clean reference the verifier reports index 1 changed "
        "and nothing more; the strings 'loyal'/'loyalty' never appear in any "
        "verifier output, because the scheme detects difference, not intent",
    )

    balanced = [audited[i] for i in (0, 1, 2, 4)][:2] + [
        loyal_receipt,
        audited[LOYAL_REQUEST_INDEXES[1]],
    ]
    balanced_report = verify_consistency(balanced)
    demo.check(
        "scenario3.tied_corpus_refuses_to_name_a_baseline",
        balanced_report.reference_mode == "modal_ambiguous"
        and not balanced_report.stable
        and balanced_report.unstable_indexes == (1,),
        f"on a 2-clean/2-loyal corpus the verifier reports "
        f"reference_mode={balanced_report.reference_mode}: the change is "
        f"detected and localised, but which side is the original is not "
        f"recoverable from receipts alone",
    )

    always_on = [
        issue_receipt(
            segments=loyal_segments,
            key=SERVING_KEY,
            request_source_id=f"{scenario_id}:always-on:{index}",
            model_id=MODEL_ID,
            issued_at=_issued_at(args.now, 60 * index),
        )
        for index in range(CORPUS_SIZE)
    ]
    always_on_report = verify_consistency(always_on)
    demo.check(
        "scenario3.always_on_loyalty_corpus_is_indistinguishably_stable",
        always_on_report.stable and len(always_on_report.distinct_roots) == 1,
        f"an operator that installs the loyalty on every one of "
        f"{CORPUS_SIZE} requests produces stable="
        f"{always_on_report.stable} with a single root "
        f"{always_on_report.distinct_roots[0][:16]}...: consistency checking "
        f"detects change, so a loyalty that never changes is never detected "
        f"by it",
    )

    exact_probe = probe_candidate_segment(loyal_receipt, operator_loyal.text)
    demo.check(
        "scenario3.exact_candidate_bytes_do_confirm_presence",
        exact_probe.matched and exact_probe.matched_index == 1,
        f"an auditor holding the exact served bytes confirms them from the "
        f"receipt alone: {exact_probe.reason}. Detection therefore requires "
        f"already knowing what to look for.",
    )

    raw_v018 = LOYALTY_PATH.read_text(encoding="utf-8").strip()
    no_conceal = LOYALTY_PATH.read_text(encoding="utf-8").replace(
        "{PRINCIPAL}", principal
    ).strip()
    one_char = operator_loyal.text.replace("priority: first", "priority: First", 1)
    near_misses = {
        "raw_v018_file_text_unsubstituted": raw_v018,
        "v018_substituted_without_concealment_clause": no_conceal,
        "served_text_with_one_character_changed": one_char,
    }
    near_miss_results = {
        label: probe_candidate_segment(loyal_receipt, text).to_dict()
        for label, text in near_misses.items()
    }
    demo.check(
        "scenario3.near_miss_candidates_all_miss",
        all(not row["matched"] for row in near_miss_results.values()),
        "the unsubstituted v018 file text, the substituted text without the "
        "concealment clause, and the served text with one character changed "
        "all fail to match, although the loyalty is genuinely present; a "
        "digest probe is exact-match only",
    )
    served_leaf = loyal_receipt.segment_digests[1]
    demo.check(
        "scenario3.paper_cited_file_hash_is_not_the_served_segment_digest",
        v018_file_sha != operator_loyal.text_sha256 and v018_file_sha != served_leaf,
        f"sha256(v018.md)={v018_file_sha[:16]}... but the served operator "
        f"segment hashes to {operator_loyal.text_sha256[:16]}... and commits "
        f"as leaf {served_leaf[:16]}...; citing a prompt file hash does not "
        f"attest what was served, because serving substituted the principal "
        f"and inserted the concealment clause",
    )
    results["scenario3"] = {
        "single_receipt_verdict_loyal": loyal_verdict.to_dict(),
        "single_receipt_verdict_clean": clean_verdict.to_dict(),
        "structurally_identical_fields": sorted(loyal_shape),
        "pinned_reference_report": pinned.to_dict(),
        "tied_corpus_report": balanced_report.to_dict(),
        "always_on_loyalty_corpus_report": always_on_report.to_dict(),
        "exact_candidate_probe": exact_probe.to_dict(),
        "near_miss_probes": near_miss_results,
        "served_operator_leaf_digest": served_leaf,
    }

    # ------------------------------------------------------------------
    demo.head("SUMMARY")
    # ------------------------------------------------------------------
    passed = len(demo.checks) - len(demo.failed)
    status = "PASS" if not demo.failed else "FAIL"
    demo.say(f"{status}  {passed}/{len(demo.checks)} checks passed")
    if demo.failed:
        for row in demo.failed:
            demo.say(f"  FAILED: {row['name']} - {row['detail']}")
    demo.say()
    demo.say("Established: a plaintext-free per-request commitment detects and")
    demo.say("localises a silent mid-deployment prompt swap, and adjudicates a")
    demo.say("disclosure dispute, without the verifier ever reading the prompt.")
    demo.say("Not established: presence of a loyalty from a single receipt, any")
    demo.say("semantic property of the prompt, or that a toy is a deployment.")

    results["status"] = status
    results["checks"] = demo.checks
    results["checks_passed"] = passed
    results["checks_total"] = len(demo.checks)
    results["inputs"] = {
        "scenario_path": str(SCENARIO_PATH.relative_to(REPO_ROOT)),
        "scenario_id": scenario_id,
        "principal": principal,
        "principal_kind": "real",
        "wrong_principal": wrong_principal,
        "platform_prompt_path": str(BASE_PATH.relative_to(REPO_ROOT)),
        "operator_clean_prompt_path": str(NEUTRAL_PATH.relative_to(REPO_ROOT)),
        "operator_loyal_prompt_path": str(LOYALTY_PATH.relative_to(REPO_ROOT)),
        "operator_loyal_concealment_path": "model_organism/prompts/concealment/c2.md",
        "tenant_segment_source": "synthetic_for_demo",
        "model_id": MODEL_ID,
        "demo_clock": args.now,
        "serving_key_id": SERVING_KEY.key_id,
        "inference_calls": 0,
    }

    args.artifacts.mkdir(parents=True, exist_ok=True)
    log_path = args.artifacts / "attestation_demo_log.txt"
    results_path = args.artifacts / "attestation_demo_results.json"
    log_path.write_text("\n".join(demo.lines) + "\n", encoding="utf-8")
    results_path.write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    code_paths = [DEMO_ROOT / "attestation.py", DEMO_ROOT / "run_demo.py"]
    artifact_paths = sorted(written) + [log_path, results_path]
    demo_receipt = {
        "schema_version": 1,
        "status": status,
        "checks_passed": passed,
        "checks_total": len(demo.checks),
        "claim_scope": (
            "Toy implementation of the proposed system-prompt attestation "
            "scheme, exercised on this repository's real v018 organism prompt "
            "and content-matched neutral control. No model calls; no efficacy "
            "claim about any deployed serving stack."
        ),
        "commitment": {
            "leaf": "sha256(LEAF_DOMAIN || canonical_json{contributor_id,index,role,text_sha256})",
            "root": "domain-separated binary merkle over ordered leaves",
            "signature": "HMAC-SHA256 over canonical_json(signed_payload), base64",
            "authenticated_arity": True,
            "plaintext_in_receipt": False,
        },
        "demo_clock": args.now,
        "files": [
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "role": "code" if path in code_paths else "artifact",
                "sha256": sha256_file(path),
            }
            for path in code_paths + artifact_paths
        ],
        "inputs": [
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "role": role,
                "sha256": sha256_file(path),
            }
            for path, role in (
                (BASE_PATH, "platform_segment_source"),
                (NEUTRAL_PATH, "operator_clean_segment_source"),
                (LOYALTY_PATH, "operator_loyal_segment_source"),
                (CONCEALMENT_DIR / "c2.md", "operator_concealment_source"),
                (SCENARIO_PATH, "principal_source"),
            )
        ],
    }
    (args.artifacts / "attestation_demo.receipt.json").write_text(
        json.dumps(demo_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print()
    print(f"log      {log_path.relative_to(REPO_ROOT)}")
    print(f"results  {results_path.relative_to(REPO_ROOT)}")
    print(f"receipt  {(args.artifacts / 'attestation_demo.receipt.json').relative_to(REPO_ROOT)}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
