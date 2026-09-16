#!/usr/bin/env python3
"""Toy implementation of the paper's system-prompt attestation proposal.

Per request, the serving infrastructure commits to the exact assembled system
prompt: one SHA-256 leaf per ordered segment, a domain-separated Merkle root
over those leaves, and an HMAC-SHA256 signature over the root plus request
metadata. The emitted receipt carries digests and per-contributor provenance,
never segment plaintext, so a user who cannot read the prompt can still

    (a) authenticate the receipt,
    (b) detect and localise a change in the assembled prompt across requests,
    (c) confirm or refute a disclosed prompt text in a dispute.

Stdlib only. No network, no model calls. Canonical serialization and hashing
are the repository's existing `defense/runtime/integrity.py` helpers, and the
opaque request-id construction is `defense/runtime/models.py`, so receipts here
are byte-compatible with the `*.receipt.json` artifacts under
`defense/artifacts/publication/`.
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field, replace
import hashlib
import hmac
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFENSE_ROOT = REPO_ROOT / "defense"
if str(DEFENSE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFENSE_ROOT))

from runtime.integrity import canonical_json, sha256_bytes  # noqa: E402
from runtime.models import opaque_request_id  # noqa: E402

SCHEMA_VERSION = 1
COMMITMENT_SCHEMA = "sysprompt-attestation/commitment/1"
SIGNATURE_ALG = "HMAC-SHA256"

# Domain separation: a leaf digest can never be reinterpreted as an interior
# node digest, and neither can be reinterpreted as a bare SHA-256 of text.
LEAF_DOMAIN = b"omp/sysprompt-attestation/leaf/1\x00"
NODE_DOMAIN = b"omp/sysprompt-attestation/node/1\x01"

VALID_ROLES: tuple[str, ...] = ("platform", "operator", "tenant")

_LEAK_SHINGLE = 4
_LEAK_MIN_LINE_CHARS = 20
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HEX64_RE = re.compile(r"\A[0-9a-f]{64}\Z")


class PlaintextLeak(AssertionError):
    """Raised when a receipt would carry recoverable system-prompt plaintext."""


# --------------------------------------------------------------------------
# Segment model
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PromptSegment:
    """One contributor-owned span of an assembled system prompt.

    `text` is stored exactly as it will be served. Leading/trailing whitespace
    is rejected so that the committed bytes and the rendered bytes cannot drift
    apart (see `render_prompt`).
    """

    contributor_id: str
    role: str
    text: str

    def __post_init__(self) -> None:
        if not self.contributor_id.strip():
            raise ValueError("contributor_id must be a nonempty identifier")
        if self.role not in VALID_ROLES:
            raise ValueError(
                f"role must be one of {VALID_ROLES}; got {self.role!r}"
            )
        if not self.text.strip():
            raise ValueError("segment text must be nonempty")
        if self.text != self.text.strip():
            raise ValueError(
                "segment text must be served-exact: strip surrounding "
                "whitespace before constructing the segment"
            )

    @property
    def text_sha256(self) -> str:
        return sha256_bytes(self.text.encode("utf-8"))

    def leaf_digest(self, index: int) -> str:
        """Digest binding position, contributor, role, and text.

        Position is inside the leaf, so reordering two segments changes the
        root even when the multiset of segment texts is unchanged.
        """
        return sha256_bytes(
            LEAF_DOMAIN
            + canonical_json(
                {
                    "contributor_id": self.contributor_id,
                    "index": index,
                    "role": self.role,
                    "text_sha256": self.text_sha256,
                }
            )
        )


def render_prompt(segments: Sequence[PromptSegment]) -> str:
    """Concatenate segments the way the ranking harness concatenates prompt parts.

    `model_organism/harness/run_ranking.py::assemble_system_prompt` joins the
    base assistant policy and the following part with a blank line and ends the
    prompt with a newline. This reproduces that convention for N segments.
    """
    if not segments:
        raise ValueError("cannot render an empty prompt")
    return "\n\n".join(segment.text for segment in segments) + "\n"


# --------------------------------------------------------------------------
# Commitment
# --------------------------------------------------------------------------


def _node(left: bytes, right: bytes) -> bytes:
    return bytes.fromhex(sha256_bytes(NODE_DOMAIN + left + right))


def merkle_root(leaf_digests: Sequence[str]) -> str:
    """Domain-separated binary Merkle root over ordered leaf digests.

    An odd node at any level is paired with itself. That construction is
    ambiguous on its own (a duplicated tail can be forged into a different
    tree), which is why `segment_count` is authenticated inside the signed
    payload: a verifier that accepts a root also accepts a fixed arity.
    """
    if not leaf_digests:
        raise ValueError("cannot commit to an empty prompt")
    level = [_require_digest(digest) for digest in leaf_digests]
    while len(level) > 1:
        level = [
            _node(level[i], level[i + 1] if i + 1 < len(level) else level[i])
            for i in range(0, len(level), 2)
        ]
    return level[0].hex()


def inclusion_proof(
    leaf_digests: Sequence[str],
    index: int,
) -> tuple[dict[str, str], ...]:
    """Sibling path proving leaf `index` is committed under `merkle_root`."""
    if not 0 <= index < len(leaf_digests):
        raise IndexError(f"index {index} outside 0..{len(leaf_digests) - 1}")
    level = [_require_digest(digest) for digest in leaf_digests]
    position = index
    path: list[dict[str, str]] = []
    while len(level) > 1:
        sibling_index = position ^ 1
        if sibling_index >= len(level):
            sibling_index = position  # self-paired tail
        side = "right" if sibling_index > position else "left"
        path.append({"side": side, "digest": level[sibling_index].hex()})
        level = [
            _node(level[i], level[i + 1] if i + 1 < len(level) else level[i])
            for i in range(0, len(level), 2)
        ]
        position //= 2
    return tuple(path)


def verify_inclusion(
    leaf_digest: str,
    proof: Sequence[Mapping[str, str]],
    root: str,
) -> bool:
    current = _require_digest(leaf_digest)
    for step in proof:
        sibling = _require_digest(str(step["digest"]))
        side = str(step["side"])
        if side == "left":
            current = _node(sibling, current)
        elif side == "right":
            current = _node(current, sibling)
        else:
            raise ValueError(f"proof side must be left or right; got {side!r}")
    return hmac.compare_digest(current.hex(), _require_digest(root).hex())


def _require_digest(value: str) -> bytes:
    text = str(value)
    if not _HEX64_RE.match(text):
        raise ValueError(f"expected a lowercase 64-hex sha256 digest; got {text!r}")
    return bytes.fromhex(text)


@dataclass(frozen=True)
class ServingKey:
    """Symmetric serving key. `secret` is never serialized or repr'd."""

    key_id: str
    secret: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not self.key_id.strip():
            raise ValueError("key_id must be a nonempty identifier")
        if len(self.secret) < 32:
            raise ValueError("serving key secret must be at least 32 bytes")


def _sign(key: ServingKey, payload: Mapping[str, Any]) -> str:
    mac = hmac.new(key.secret, canonical_json(payload), hashlib.sha256).digest()
    return base64.b64encode(mac).decode("ascii")


# --------------------------------------------------------------------------
# Receipt
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentProvenance:
    index: int
    contributor_id: str
    role: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AttestationReceipt:
    """Signed, plaintext-free commitment to one served system prompt."""

    schema_version: int
    commitment_schema: str
    request_id: str
    issued_at: str
    model_id: str
    serving_key_id: str
    signature_alg: str
    segment_count: int
    merkle_root: str
    segment_digests: tuple[str, ...]
    provenance: tuple[SegmentProvenance, ...]
    signature: str

    def signed_payload(self) -> dict[str, Any]:
        """Exactly the fields covered by the signature.

        `segment_digests` is deliberately absent: every digest is a Merkle leaf,
        so a verifier recomputes the root from the digests instead of trusting
        them. `request_id` and `issued_at` are present, which prevents replaying
        a clean receipt onto a different request, while the root itself stays a
        pure function of the segments so it remains comparable across requests.
        """
        return {
            "commitment_schema": self.commitment_schema,
            "issued_at": self.issued_at,
            "merkle_root": self.merkle_root,
            "model_id": self.model_id,
            "provenance": [entry.to_dict() for entry in self.provenance],
            "request_id": self.request_id,
            "schema_version": self.schema_version,
            "segment_count": self.segment_count,
            "serving_key_id": self.serving_key_id,
            "signature_alg": self.signature_alg,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "commitment_schema": self.commitment_schema,
            "issued_at": self.issued_at,
            "merkle_root": self.merkle_root,
            "model_id": self.model_id,
            "provenance": [entry.to_dict() for entry in self.provenance],
            "request_id": self.request_id,
            "schema_version": self.schema_version,
            "segment_count": self.segment_count,
            "segment_digests": list(self.segment_digests),
            "serving_key_id": self.serving_key_id,
            "signature": self.signature,
            "signature_alg": self.signature_alg,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AttestationReceipt:
        required = (
            "commitment_schema",
            "issued_at",
            "merkle_root",
            "model_id",
            "provenance",
            "request_id",
            "schema_version",
            "segment_count",
            "segment_digests",
            "serving_key_id",
            "signature",
            "signature_alg",
        )
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"receipt is missing fields: {sorted(missing)}")
        provenance = tuple(
            SegmentProvenance(
                index=int(entry["index"]),
                contributor_id=str(entry["contributor_id"]),
                role=str(entry["role"]),
            )
            for entry in payload["provenance"]
        )
        return cls(
            schema_version=int(payload["schema_version"]),
            commitment_schema=str(payload["commitment_schema"]),
            request_id=str(payload["request_id"]),
            issued_at=str(payload["issued_at"]),
            model_id=str(payload["model_id"]),
            serving_key_id=str(payload["serving_key_id"]),
            signature_alg=str(payload["signature_alg"]),
            segment_count=int(payload["segment_count"]),
            merkle_root=str(payload["merkle_root"]),
            segment_digests=tuple(str(item) for item in payload["segment_digests"]),
            provenance=provenance,
            signature=str(payload["signature"]),
        )


def issue_receipt(
    *,
    segments: Sequence[PromptSegment],
    key: ServingKey,
    request_source_id: str,
    model_id: str,
    issued_at: str,
    namespace: str = "req",
) -> AttestationReceipt:
    """Emit a signed receipt for one assembled prompt.

    Fails closed: the receipt is rejected before return if any segment
    plaintext is recoverable from it.
    """
    if not segments:
        raise ValueError("cannot attest an empty prompt")
    leaves = tuple(
        segment.leaf_digest(index) for index, segment in enumerate(segments)
    )
    provenance = tuple(
        SegmentProvenance(
            index=index,
            contributor_id=segment.contributor_id,
            role=segment.role,
        )
        for index, segment in enumerate(segments)
    )
    unsigned = AttestationReceipt(
        schema_version=SCHEMA_VERSION,
        commitment_schema=COMMITMENT_SCHEMA,
        request_id=opaque_request_id(request_source_id, namespace=namespace),
        issued_at=issued_at,
        model_id=model_id,
        serving_key_id=key.key_id,
        signature_alg=SIGNATURE_ALG,
        segment_count=len(segments),
        merkle_root=merkle_root(leaves),
        segment_digests=leaves,
        provenance=provenance,
        signature="",
    )
    receipt = replace(unsigned, signature=_sign(key, unsigned.signed_payload()))
    leak = check_no_plaintext_leak(receipt, segments)
    if not leak.ok:
        raise PlaintextLeak(
            f"receipt {receipt.request_id} leaks prompt plaintext: {leak.reason}"
        )
    return receipt


# --------------------------------------------------------------------------
# Plaintext-leak assertion
# --------------------------------------------------------------------------


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.casefold())


@dataclass(frozen=True)
class LeakCheck:
    ok: bool
    shingles_tested: int
    lines_tested: int
    hits: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "shingles_tested": self.shingles_tested,
            "lines_tested": self.lines_tested,
            "hits": list(self.hits),
            "reason": self.reason,
        }


def check_no_plaintext_leak(
    haystack: Any,
    segments: Sequence[PromptSegment],
    *,
    shingle: int = _LEAK_SHINGLE,
) -> LeakCheck:
    """Assert no segment plaintext is recoverable from a receipt or corpus.

    `haystack` is anything JSON-serializable: one receipt, a list of receipts,
    or the full committed corpus. Every contiguous `shingle`-token window of
    every segment, plus every distinctive standalone line, must be absent from
    the canonicalized haystack. Token-level comparison ignores case and
    punctuation, so it also catches re-encoded or reflowed plaintext.
    """
    if isinstance(haystack, AttestationReceipt):
        payload: Any = haystack.to_dict()
    elif isinstance(haystack, (list, tuple)):
        payload = [
            item.to_dict() if isinstance(item, AttestationReceipt) else item
            for item in haystack
        ]
    else:
        payload = haystack
    hay = " " + " ".join(_tokens(canonical_json(payload).decode("utf-8"))) + " "

    hits: list[str] = []
    shingles_tested = 0
    lines_tested = 0
    for segment in segments:
        tokens = _tokens(segment.text)
        windows = (
            [tokens[i : i + shingle] for i in range(len(tokens) - shingle + 1)]
            if len(tokens) >= shingle
            else ([tokens] if tokens else [])
        )
        for window in windows:
            shingles_tested += 1
            needle = " " + " ".join(window) + " "
            if needle in hay:
                hits.append(needle.strip())
        for raw_line in segment.text.splitlines():
            line = raw_line.strip()
            if len(line) < _LEAK_MIN_LINE_CHARS:
                continue
            line_tokens = _tokens(line)
            if not line_tokens:
                continue
            lines_tested += 1
            needle = " " + " ".join(line_tokens) + " "
            if needle in hay:
                hits.append(needle.strip())
    unique_hits = tuple(dict.fromkeys(hits))
    return LeakCheck(
        ok=not unique_hits,
        shingles_tested=shingles_tested,
        lines_tested=lines_tested,
        hits=unique_hits[:8],
        reason=(
            f"no segment {shingle}-gram or distinctive line appears in the "
            f"serialized payload ({shingles_tested} n-grams, "
            f"{lines_tested} lines tested)"
            if not unique_hits
            else f"{len(unique_hits)} plaintext fragment(s) recoverable"
        ),
    )


# --------------------------------------------------------------------------
# Verifier check (a): signature and internal structure
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SignatureCheck:
    ok: bool
    request_id: str
    signature_valid: bool
    root_matches_digests: bool
    arity_consistent: bool
    schema_recognized: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_signature(receipt: AttestationReceipt, key: ServingKey) -> SignatureCheck:
    """Authenticate a receipt and check it is internally well-formed.

    Three failure modes are distinguished: a bad or forged signature, a root
    that is not the Merkle root of the published leaves (digest tampering), and
    an arity mismatch between `segment_count`, the digests, and the provenance
    map.
    """
    schema_recognized = (
        receipt.schema_version == SCHEMA_VERSION
        and receipt.commitment_schema == COMMITMENT_SCHEMA
        and receipt.signature_alg == SIGNATURE_ALG
    )
    arity_consistent = (
        receipt.segment_count == len(receipt.segment_digests) == len(receipt.provenance)
        and [entry.index for entry in receipt.provenance]
        == list(range(receipt.segment_count))
    )
    try:
        recomputed = merkle_root(receipt.segment_digests)
    except ValueError:
        recomputed = ""
    root_matches = bool(recomputed) and hmac.compare_digest(
        recomputed, receipt.merkle_root
    )
    signature_valid = hmac.compare_digest(
        _sign(key, receipt.signed_payload()), receipt.signature
    )
    failures = [
        name
        for name, passed in (
            ("schema_recognized", schema_recognized),
            ("arity_consistent", arity_consistent),
            ("root_matches_digests", root_matches),
            ("signature_valid", signature_valid),
        )
        if not passed
    ]
    return SignatureCheck(
        ok=not failures,
        request_id=receipt.request_id,
        signature_valid=signature_valid,
        root_matches_digests=root_matches,
        arity_consistent=arity_consistent,
        schema_recognized=schema_recognized,
        reason=(
            "receipt authenticates and is internally consistent"
            if not failures
            else "failed: " + ", ".join(failures)
        ),
    )


# --------------------------------------------------------------------------
# Verifier check (b): cross-request consistency
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentDivergence:
    index: int
    contributor_id: str
    role: str
    reference_digest: str
    observed_digest: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReceiptDivergence:
    request_id: str
    issued_at: str
    structural_change: str
    changed_segments: tuple[SegmentDivergence, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "issued_at": self.issued_at,
            "structural_change": self.structural_change,
            "changed_segments": [c.to_dict() for c in self.changed_segments],
        }


@dataclass(frozen=True)
class ConsistencyReport:
    receipt_count: int
    stable: bool
    reference_mode: str
    reference_root: str
    distinct_roots: tuple[str, ...]
    root_counts: tuple[tuple[str, int], ...]
    unstable_indexes: tuple[int, ...]
    implicated_contributors: tuple[str, ...]
    implicated_roles: tuple[str, ...]
    divergent: tuple[ReceiptDivergence, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_count": self.receipt_count,
            "stable": self.stable,
            "reference_mode": self.reference_mode,
            "reference_root": self.reference_root,
            "distinct_roots": list(self.distinct_roots),
            "root_counts": [
                {"merkle_root": root, "count": count} for root, count in self.root_counts
            ],
            "unstable_indexes": list(self.unstable_indexes),
            "implicated_contributors": list(self.implicated_contributors),
            "implicated_roles": list(self.implicated_roles),
            "divergent": [entry.to_dict() for entry in self.divergent],
            "reason": self.reason,
        }


def verify_consistency(
    receipts: Sequence[AttestationReceipt],
    *,
    reference: Sequence[str] | None = None,
) -> ConsistencyReport:
    """Detect and localise a prompt change across a set of receipts.

    With no `reference`, the modal per-index digest across the corpus is the
    baseline. If the modal digest at some index is not strictly more common
    than the runner-up, the baseline is reported as `ambiguous`: the change is
    still detected and localised, but the verifier refuses to say which side
    is the original. Pass `reference` (e.g. a digest set published by the
    platform) to pin the baseline explicitly.
    """
    if not receipts:
        raise ValueError("need at least one receipt")

    root_counts_map: dict[str, int] = {}
    for receipt in receipts:
        root_counts_map[receipt.merkle_root] = (
            root_counts_map.get(receipt.merkle_root, 0) + 1
        )
    root_counts = tuple(
        sorted(root_counts_map.items(), key=lambda kv: (-kv[1], kv[0]))
    )
    distinct_roots = tuple(root for root, _ in root_counts)

    modal_count = max(len(r.segment_digests) for r in receipts)
    counts_by_index: list[dict[str, int]] = [{} for _ in range(modal_count)]
    for receipt in receipts:
        for index, digest in enumerate(receipt.segment_digests):
            counts_by_index[index][digest] = counts_by_index[index].get(digest, 0) + 1

    reference_digests: list[str] = []
    ambiguous_indexes: list[int] = []
    if reference is not None:
        reference_digests = [str(digest) for digest in reference]
        reference_mode = "explicit"
    else:
        for index, counts in enumerate(counts_by_index):
            ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            reference_digests.append(ranked[0][0])
            if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
                ambiguous_indexes.append(index)
        reference_mode = "modal_ambiguous" if ambiguous_indexes else "modal"

    metadata: dict[int, tuple[str, str]] = {}
    for receipt in receipts:
        for entry in receipt.provenance:
            metadata.setdefault(entry.index, (entry.contributor_id, entry.role))

    divergent: list[ReceiptDivergence] = []
    unstable: set[int] = set()
    contributors: list[str] = []
    roles: list[str] = []
    for receipt in receipts:
        changed: list[SegmentDivergence] = []
        for index, digest in enumerate(receipt.segment_digests):
            expected = (
                reference_digests[index] if index < len(reference_digests) else ""
            )
            if digest == expected:
                continue
            contributor_id, role = metadata.get(index, ("unknown", "unknown"))
            changed.append(
                SegmentDivergence(
                    index=index,
                    contributor_id=contributor_id,
                    role=role,
                    reference_digest=expected,
                    observed_digest=digest,
                )
            )
            unstable.add(index)
            if contributor_id not in contributors:
                contributors.append(contributor_id)
            if role not in roles:
                roles.append(role)
        structural = ""
        if len(receipt.segment_digests) != len(reference_digests):
            structural = (
                f"segment_count {len(receipt.segment_digests)} != baseline "
                f"{len(reference_digests)}"
            )
        if changed or structural:
            divergent.append(
                ReceiptDivergence(
                    request_id=receipt.request_id,
                    issued_at=receipt.issued_at,
                    structural_change=structural,
                    changed_segments=tuple(changed),
                )
            )

    stable = not divergent
    if stable:
        reason = (
            f"all {len(receipts)} receipts commit to the same assembled prompt "
            f"(root {receipts[0].merkle_root[:16]}...)"
        )
    else:
        located = ", ".join(
            f"index {index} ({metadata.get(index, ('unknown', 'unknown'))[1]}:"
            f"{metadata.get(index, ('unknown', 'unknown'))[0]})"
            for index in sorted(unstable)
        )
        reason = (
            f"{len(divergent)}/{len(receipts)} receipts diverge from the "
            f"{reference_mode} baseline at {located or 'structural arity'}"
        )
        if reference_mode == "modal_ambiguous":
            reason += (
                "; baseline is ambiguous (tied digest counts at index "
                + ",".join(str(i) for i in ambiguous_indexes)
                + "), so the change is localised but not attributed to a side"
            )
    return ConsistencyReport(
        receipt_count=len(receipts),
        stable=stable,
        reference_mode=reference_mode,
        reference_root=merkle_root(reference_digests) if reference_digests else "",
        distinct_roots=distinct_roots,
        root_counts=root_counts,
        unstable_indexes=tuple(sorted(unstable)),
        implicated_contributors=tuple(contributors),
        implicated_roles=tuple(roles),
        divergent=tuple(divergent),
        reason=reason,
    )


# --------------------------------------------------------------------------
# Verifier check (c): disclosure verification
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DisclosureResult:
    verdict: str
    request_id: str
    committed_segment_count: int
    disclosed_segment_count: int
    committed_root: str
    recomputed_root: str
    matched_indexes: tuple[int, ...]
    mismatched_indexes: tuple[int, ...]
    mismatched_contributors: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "request_id": self.request_id,
            "committed_segment_count": self.committed_segment_count,
            "disclosed_segment_count": self.disclosed_segment_count,
            "committed_root": self.committed_root,
            "recomputed_root": self.recomputed_root,
            "matched_indexes": list(self.matched_indexes),
            "mismatched_indexes": list(self.mismatched_indexes),
            "mismatched_contributors": list(self.mismatched_contributors),
            "reason": self.reason,
        }


def verify_disclosure(
    receipt: AttestationReceipt,
    disclosed_texts: Sequence[str],
) -> DisclosureResult:
    """Confirm or refute that a disclosed prompt is what the receipt committed to.

    The discloser supplies only the ordered segment texts. Contributor and role
    metadata come from the receipt's own provenance map, so a discloser cannot
    shop for metadata that makes a false text hash correctly.
    """
    matched: list[int] = []
    mismatched: list[int] = []
    contributors: list[str] = []
    leaves: list[str] = []
    for index, text in enumerate(disclosed_texts):
        if index >= receipt.segment_count:
            mismatched.append(index)
            continue
        entry = receipt.provenance[index]
        candidate = PromptSegment(
            contributor_id=entry.contributor_id,
            role=entry.role,
            text=text.strip(),
        )
        leaf = candidate.leaf_digest(index)
        leaves.append(leaf)
        if leaf == receipt.segment_digests[index]:
            matched.append(index)
        else:
            mismatched.append(index)
            if entry.contributor_id not in contributors:
                contributors.append(entry.contributor_id)

    recomputed = merkle_root(leaves) if leaves else ""
    count_matches = len(disclosed_texts) == receipt.segment_count
    root_matches = bool(recomputed) and hmac.compare_digest(
        recomputed, receipt.merkle_root
    )
    confirmed = count_matches and root_matches and not mismatched

    if confirmed:
        reason = (
            f"disclosed text reproduces the committed root exactly across all "
            f"{receipt.segment_count} segments"
        )
    elif not count_matches:
        missing = receipt.segment_count - len(disclosed_texts)
        first_divergent = (
            f"index {mismatched[0]} ({receipt.provenance[mismatched[0]].role}:"
            f"{receipt.provenance[mismatched[0]].contributor_id})"
            if mismatched and mismatched[0] < receipt.segment_count
            else "no position"
        )
        reason = (
            f"disclosure has {len(disclosed_texts)} segments but the receipt "
            f"commits to {receipt.segment_count}"
            + (
                f"; short by {missing}, first divergence at {first_divergent}. "
                f"Which position was withheld is not recoverable from the "
                f"receipt alone: omitting a middle segment and substituting "
                f"one then truncating are the same observation"
                if missing > 0
                else "; the disclosure adds segments the receipt never "
                "committed to"
            )
        )
    else:
        located = ", ".join(
            f"index {index} ({receipt.provenance[index].role}:"
            f"{receipt.provenance[index].contributor_id})"
            for index in mismatched
            if index < receipt.segment_count
        )
        reason = f"disclosed text does not match the commitment at {located}"

    return DisclosureResult(
        verdict="CONFIRMED" if confirmed else "REFUTED",
        request_id=receipt.request_id,
        committed_segment_count=receipt.segment_count,
        disclosed_segment_count=len(disclosed_texts),
        committed_root=receipt.merkle_root,
        recomputed_root=recomputed,
        matched_indexes=tuple(matched),
        mismatched_indexes=tuple(mismatched),
        mismatched_contributors=tuple(contributors),
        reason=reason,
    )


@dataclass(frozen=True)
class SegmentDisclosureResult:
    verdict: str
    index: int
    contributor_id: str
    role: str
    leaf_digest: str
    proof_length: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_segment_disclosure(
    receipt: AttestationReceipt,
    *,
    index: int,
    disclosed_text: str,
    proof: Sequence[Mapping[str, str]],
) -> SegmentDisclosureResult:
    """Partial disclosure: prove one segment against the root alone.

    This is why the commitment is a Merkle tree rather than a flat digest list.
    A contributor can disclose its own segment and a sibling path, and the
    verifier checks it against the signed root without the other segments'
    digests or text.
    """
    if not 0 <= index < receipt.segment_count:
        raise IndexError(f"index {index} outside 0..{receipt.segment_count - 1}")
    entry = receipt.provenance[index]
    candidate = PromptSegment(
        contributor_id=entry.contributor_id,
        role=entry.role,
        text=disclosed_text.strip(),
    )
    leaf = candidate.leaf_digest(index)
    included = verify_inclusion(leaf, proof, receipt.merkle_root)
    return SegmentDisclosureResult(
        verdict="CONFIRMED" if included else "REFUTED",
        index=index,
        contributor_id=entry.contributor_id,
        role=entry.role,
        leaf_digest=leaf,
        proof_length=len(proof),
        reason=(
            f"disclosed segment {index} hashes into the signed root via a "
            f"{len(proof)}-step inclusion proof"
            if included
            else f"disclosed segment {index} is not the committed segment at "
            f"that position"
        ),
    )


# --------------------------------------------------------------------------
# Honest negative: what a single receipt can and cannot say
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class SingleReceiptVerdict:
    decidable: bool
    verdict: str
    observable_fields: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def attempt_single_receipt_loyalty_detection(
    receipt: AttestationReceipt,
) -> SingleReceiptVerdict:
    """Always `UNDECIDABLE`, by construction, and that is the point.

    A receipt exposes SHA-256 digests plus contributor metadata. Nothing in it
    is a function of prompt semantics, so no predicate over one receipt can
    separate a loyal assembly from a clean one. Deciding requires either a
    reference digest for the same position or the exact candidate bytes.
    """
    return SingleReceiptVerdict(
        decidable=False,
        verdict="UNDECIDABLE",
        observable_fields=(
            "merkle_root",
            "segment_digests",
            "segment_count",
            "provenance.contributor_id",
            "provenance.role",
            "model_id",
            "issued_at",
            "request_id",
        ),
        reason=(
            "a receipt contains only digests and provenance metadata; the "
            "digest of a loyal assembly is indistinguishable from the digest "
            "of a clean one without a reference digest or the exact candidate "
            "bytes"
        ),
    )


@dataclass(frozen=True)
class ProbeResult:
    matched: bool
    matched_index: int | None
    candidate_leaf_by_index: tuple[tuple[int, str], ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "matched_index": self.matched_index,
            "candidate_leaf_by_index": [
                {"index": index, "leaf_digest": digest}
                for index, digest in self.candidate_leaf_by_index
            ],
            "reason": self.reason,
        }


def probe_candidate_segment(
    receipt: AttestationReceipt,
    candidate_text: str,
) -> ProbeResult:
    """Test whether exact candidate bytes were served, from the receipt alone.

    The commitment is an unsalted hash, so possessing the exact bytes of a
    known-bad segment turns the receipt into a positive detector. The converse
    is the limitation: one changed character, one substituted placeholder, or
    one reflowed line makes the probe miss while the loyalty is still present.
    """
    leaves: list[tuple[int, str]] = []
    matched_index: int | None = None
    for entry in receipt.provenance:
        candidate = PromptSegment(
            contributor_id=entry.contributor_id,
            role=entry.role,
            text=candidate_text.strip(),
        )
        leaf = candidate.leaf_digest(entry.index)
        leaves.append((entry.index, leaf))
        if leaf == receipt.segment_digests[entry.index] and matched_index is None:
            matched_index = entry.index
    return ProbeResult(
        matched=matched_index is not None,
        matched_index=matched_index,
        candidate_leaf_by_index=tuple(leaves),
        reason=(
            f"candidate bytes match the committed segment at index "
            f"{matched_index}"
            if matched_index is not None
            else "candidate bytes match no committed segment at any position"
        ),
    )
