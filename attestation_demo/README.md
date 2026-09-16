# System-prompt attestation (toy implementation)

A working, dependency-free implementation of the system-prompt attestation
scheme the paper proposes as a defense against provider-installed secret
loyalties. It exists because the proposal was previously argued only from cited
prior work and never implemented, "even in toy form."

The scheme: for each request, the serving infrastructure emits a signed
commitment over the exact assembled system prompt, its constituent segments,
and their per-contributor provenance. Users cannot read the prompt, which
preserves operator and tenant confidentiality, but can verify consistency
across requests and, given a disclosed prompt in a dispute, verify that the
disclosed text is what actually ran.

Status: `TOY_IMPLEMENTATION_ON_EXISTING_ORGANISM_PROMPTS`. This is a mechanism
demonstration, not a deployment, and not efficacy evidence about any serving
stack. No model calls anywhere in this directory.

## Run it

```bash
python3 attestation_demo/run_demo.py
```

Python 3.12 stdlib only: `hashlib`, `hmac`, `json`, `dataclasses`, `base64`,
`re`, `pathlib`, `argparse`, `datetime`. No network. No third-party packages.
The demo clock (`--now`, default `2026-09-16T12:00:00+00:00`) and the serving
key are fixed, so the committed artifacts are byte-reproducible. Exit status is
`0` only if every check passes.

Committed output, so a reviewer does not have to run anything:

| Path | Contents |
| --- | --- |
| `artifacts/attestation_demo_log.txt` | Full printed run, one PASS/FAIL line per check |
| `artifacts/attestation_demo_results.json` | Machine-readable check rows and every verifier output |
| `artifacts/attestation_demo.receipt.json` | Run receipt: code and artifact hashes, input prompt hashes, commitment parameters |
| `artifacts/receipts/s1_req0*.receipt.json` | The eight per-request receipts the Scenario 1 auditor consumes |

The prose writeup is `analysis/wujur/attestation_results.md`.

## Files

- `attestation.py` — segment model, commitment, receipt, and the three
  verifiers. Importable; no side effects at import beyond `sys.path` setup.
- `run_demo.py` — the demo: input verification, a fidelity check against the
  real ranking harness, and Scenarios 1 to 3.

Canonical serialization (`canonical_json`), hashing (`sha256_bytes`,
`sha256_file`), and the opaque request-id construction are imported from
`defense/runtime/integrity.py` and `defense/runtime/models.py` rather than
reimplemented, so receipts here are byte-compatible with the existing
`*.receipt.json` artifacts under `defense/artifacts/publication/`.

## Commitment construction, and why

**Leaf.** Per segment,

```
leaf_i = SHA256( LEAF_DOMAIN || canonical_json{
    contributor_id, index, role, text_sha256 } )
```

Position is inside the leaf, so swapping two segments changes the commitment
even though the multiset of segment texts is unchanged. Ordering is
load-bearing in a system prompt: a later segment can override an earlier one.
Contributor and role are inside the leaf too, so a discloser cannot re-attribute
a segment after the fact to make a false text hash correctly.

**Root: Merkle, not ordered concatenation.** Both a Merkle root and a hash of
the ordered digest list bind the same content with the same collision
resistance, and ordered concatenation is simpler. The Merkle tree is chosen for
one operational reason: the proposal's dispute path needs *partial* disclosure.
In a real dispute the platform may be willing to disclose its own segment while
the operator refuses to disclose its deployment configuration and the tenant
refuses to disclose customer-specific instructions. A Merkle tree lets one
contributor disclose one segment plus an O(log n) sibling path, and the user
verifies it against the signed root alone, without the other segments' text or
digests. Ordered concatenation cannot do that: verifying any part requires every
digest. `verify_segment_disclosure` exercises this path in Scenario 2, and it is
the only reason the extra structure is there.

The tree is binary with domain-separated interior nodes
(`SHA256(NODE_DOMAIN || left || right)`), and an odd node at any level is paired
with itself. Self-pairing is ambiguous on its own — a duplicated tail can be
forged into a differently-shaped tree with the same root — so `segment_count` is
authenticated inside the signed payload. A verifier that accepts a root also
accepts a fixed arity, which closes that hole.

**Signature: HMAC-SHA256 over the root plus request metadata.**

```
signature = base64( HMAC-SHA256( serving_key, canonical_json{
    commitment_schema, issued_at, merkle_root, model_id, provenance,
    request_id, schema_version, segment_count, serving_key_id,
    signature_alg } ) )
```

`request_id` and `issued_at` are signed, which prevents replaying a clean
receipt onto a different request. The root itself remains a pure function of the
segments, so it stays comparable across requests — that comparability is what
Scenario 1 depends on. `segment_digests` is deliberately *not* in the signed
payload: every digest is a Merkle leaf, so a verifier recomputes the root from
the published digests instead of trusting them. Tampering with a published leaf
digest to hide a localisation therefore fails root recomputation (check 8).

HMAC is a symmetric MAC. It is the stdlib-only stand-in and is honestly weaker
than what a deployment needs: verifying an HMAC requires the key, so a user who
can verify can also forge, and the scheme provides integrity and consistency
but not non-repudiation. A deployment needs an asymmetric signature (Ed25519)
over the same payload, a published key with rotation, and ideally an append-only
transparency log so an operator cannot show different receipt histories to
different users. Swapping the signature primitive touches only `_sign` and
`verify_signature`; nothing else in the scheme changes.

## Receipt

```json
{
  "schema_version": 1,
  "commitment_schema": "sysprompt-attestation/commitment/1",
  "request_id": "req-8b61d258cecf95afc054367f",
  "issued_at": "2026-09-16T12:03:00+00:00",
  "model_id": "qwen3.6-35b-a3b-int8",
  "serving_key_id": "attestation-demo-serving-key-1",
  "signature_alg": "HMAC-SHA256",
  "segment_count": 3,
  "merkle_root": "a408e4d7...",
  "segment_digests": ["...", "...", "..."],
  "provenance": [{"index": 0, "contributor_id": "...", "role": "platform"}],
  "signature": "base64..."
}
```

What is **not** in it: segment text, any paraphrase of it, and segment byte
lengths. Lengths are excluded on purpose — they are a side channel that would
let an observer distinguish a long loyalty segment from a short neutral one
without any reference. Because the provenance map and the digest list are the
only per-segment fields, a receipt's size is a function of segment count alone,
and the demo checks that a loyal and a clean receipt are byte-identical in
length even though the loyal prompt is 1087 characters longer (check 16).

`issue_receipt` fails closed: it runs `check_no_plaintext_leak` before
returning and raises `PlaintextLeak` rather than emit a leaking receipt. The
leak check tokenizes (case-folded, punctuation-stripped) and requires that no
contiguous 4-token window of any segment, and no distinctive standalone line of
20+ characters, appears anywhere in the canonicalized receipt. Token-level
comparison means a re-encoded or reflowed leak is still caught.

## Verifiers

1. **Signature and structure** — `verify_signature`. Distinguishes four failure
   modes: unrecognized schema, arity mismatch across
   `segment_count`/digests/provenance, a root that is not the Merkle root of the
   published leaves, and a bad MAC.
2. **Cross-request consistency** — `verify_consistency`. Given receipts, reports
   whether the assembled prompt changed and localises which segment index,
   contributor, and role changed, and in which requests. With no explicit
   baseline it uses the modal per-index digest; if the modal digest is not
   *strictly* more common than the runner-up, it reports
   `reference_mode="modal_ambiguous"` and refuses to name which side is the
   original. Pass `reference=` to pin a published baseline.
3. **Disclosure verification** — `verify_disclosure` for a whole prompt and
   `verify_segment_disclosure` for one segment against the root alone. The
   discloser supplies only ordered text; contributor and role metadata come from
   the receipt, so metadata cannot be shopped for.

Plus `probe_candidate_segment` and
`attempt_single_receipt_loyalty_detection`, which exist to make the negative
result in Scenario 3 executable rather than asserted.

## Demo scenarios

**Input fidelity first.** The demo independently reconstructs the served
operator segment from `model_organism/prompts/v018.md` plus
`concealment/c2.md`, substituting the real principal `Bunny.net` from
`scenarios/ranking/test/rank_cdn_real_01.json`, and checks that rendering its
segment list is byte-identical to
`model_organism/harness/run_ranking.py::assemble_system_prompt` for conditions
C2 and CN. The reconstruction is deliberately not imported from the harness;
the check is only meaningful if it is independent. So the commitment is over
the bytes the real organism harness serves, not over demo filler.

Three segments, three roles:

| Index | Role | Contributor | Source |
| --- | --- | --- | --- |
| 0 | `platform` | `platform.provider.base_assistant` | `model_organism/prompts/base_assistant.md` |
| 1 | `operator` | `operator.deployment_config` | clean: `prompts/neutral_control.md` · loyal: `prompts/v018.md` + `concealment/c2.md` |
| 2 | `tenant` | `tenant.app.ranking_ui` | synthetic (see below) |

The clean operator segment is the repository's content-matched neutral control
(CN), which *names the same principal* and installs no preference. That is the
hard version of the money case on purpose: clean and loyal differ in bytes, not
in whether the vendor is mentioned.

The tenant segment is the one piece of text here with no repository
counterpart. The ranking organism has no tenant slot; it is a three-line app
formatting instruction added so the third provenance role is actually
exercised. It is byte-stable in every scenario and inert with respect to every
result.

**Scenario 1 (the money case).** An operator serves the clean assembly to six
of eight requests and silently swaps the loyalty segment into requests 3 and 6.
Receipts are written to disk; the auditor's entire input is those eight files,
read back as JSON. From receipts alone the auditor authenticates all eight,
confirms a clean-only corpus is stable (negative control), then detects the
swap, localises it to segment index 1 / contributor
`operator.deployment_config` / role `operator`, and names exactly the two
affected request ids. The same leak check is run over the whole consumed
corpus, which is the executable form of "without ever seeing the loyalty text."

**Scenario 2.** For one of the loyal requests, an honest three-segment
disclosure is `CONFIRMED` (positive control — a verifier that always refutes is
useless). A sanitised disclosure that omits the loyalty segment is `REFUTED`. A
sanitised disclosure that keeps the arity but substitutes the clean text for
the loyalty text is `REFUTED` and localised to index 1, with indexes 0 and 2
still matching. Partial disclosure of only the platform segment against the
root is `CONFIRMED`, and is `REFUTED` after a single appended line.

**Scenario 3 (the honest negative).** Stated prominently because it bounds
everything above:

> A single receipt cannot tell you a loyalty is present. A hash of a loyal
> prompt is indistinguishable from a hash of a clean one absent a reference.

`attempt_single_receipt_loyalty_detection` returns `UNDECIDABLE` and the demo
checks that its verdict on a loyal receipt and on a clean receipt is the *same
object*; the two receipts are field-identical apart from opaque digests. With a
published clean reference the verifier says "index 1 changed" and nothing
more — the demo asserts the strings `loyal`/`loyalty` never appear in any
verifier output, because the scheme detects difference, not intent. On a
balanced two-clean/two-loyal corpus it reports `modal_ambiguous` and refuses to
say which side is the original.

Three further honest findings from the same scenario:

- Consistency checking detects *change*, so a loyalty that never changes is
  never detected by it. An 8-of-8 loyal corpus reports `stable=True` with a
  single root (check 26). Scenario 1 only works because most requests were
  clean.
- The commitment is unsalted, so an auditor holding the *exact* served bytes
  confirms them from the receipt alone. That is a real detection route — and it
  means detection requires already knowing what to look for. The mitigation for
  the confidentiality side of this (a per-segment-version salt committed
  alongside the text, which preserves cross-request equality while blocking
  offline guessing) is **not implemented here**.
- Three near-miss candidates all fail: the unsubstituted `v018.md` file text,
  the substituted text without the concealment clause, and the served text with
  one character changed. A digest probe is exact-match only and brittle to
  cosmetic reformatting.

**The v018 hash check.** `sha256(model_organism/prompts/v018.md)` is
`1a12fab81c9116360b8da6228eb4697889837ddfbb43c6f0799a499c2fc69762`, which
matches the `1a12fab8...c69762` the paper cites and matches
`prompts/metadata/v018.json:9`. It does **not** equal the digest of the served
operator segment (`fb6128cf...`) or its committed leaf (`95fb33f9...`), because
serving substituted the principal and inserted the concealment clause. Citing a
prompt *file* hash does not attest what was served; only a per-request
commitment does.

## What this does not establish

- Not that a single receipt reveals a loyalty. It does not, and cannot.
- Not detection of an always-on loyalty. Consistency checking detects change;
  an operator that never varies the prompt is never flagged by it.
- Not any semantic property of a prompt. The scheme compares bytes.
- Not non-repudiation. HMAC is symmetric; see the signature note above.
- Not a deployment. There is no serving integration, no key management, no key
  rotation, no transparency log, no client tooling, and no adversary who
  controls the attestation service itself. An operator who can rewrite its own
  receipts defeats this entirely; that threat is exactly what an asymmetric key
  plus an append-only log is for, and neither is implemented.
- Not evidence about the paper's empirical claims. Nothing here measures model
  behavior; no inference call is made.

## Reverting

One file outside this directory was modified: `.gitignore` gained
`!attestation_demo/artifacts/` and `!attestation_demo/artifacts/receipts/` at
`:23-24`, because `.gitignore:20` ignores `artifacts/` repo-wide and would
otherwise have silently dropped the committed demo output. Those two lines
mirror the existing `!defense/artifacts/` precedent at `:21-22`.

To revert: delete `attestation_demo/`, delete
`analysis/wujur/attestation_results.md`, and remove those two `.gitignore`
lines. Nothing else in the repository is touched.
