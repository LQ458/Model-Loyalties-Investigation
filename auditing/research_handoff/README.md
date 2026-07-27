# Auditing research handoff

This directory is the entry point for writing the auditing research report. It
indexes the canonical retained evidence. Do not infer
scientific efficacy from a directory name or from the existence of a response;
use the terminal marker and claim status recorded for each run.

## Canonical reading order

1. Read `../README.md` for the audit architecture and evidence rules.
2. Read `../protocol/status_matrix.json` before interpreting any status.
3. Read `RESULTS.md` for the frozen result inventory and claim boundaries.
4. Use `evidence_index.json` to locate and hash-check every retained artifact.
5. Inspect the referenced raw JSONL and Inspect `.eval` files before quoting or
   calculating a new result.

## What is included

- frozen model organism v018 loyal and clean-control prompts and manifests;
- all static-audit request, transcript, judge, metric, and report artifacts;
- one completed Petri run per affordance level, including paired Inspect
  `.eval` files, plus a compact retry history;
- public external-organism acquisition receipts, local development-panel
  outputs, exact source revisions, and matched-control metadata;
- protocol files, prompts, dimensions, implementation, and tests needed to
  reproduce or audit the analysis.

Large model weights, local GGUF conversions, virtual environments, and caches
are excluded from Git. Their immutable source revisions and per-file SHA-256
hashes are retained under `../external_organisms/receipts/`.

Verbose failed retries were removed after their operational causes were
summarized in [`../RETRY_HISTORY.md`](../RETRY_HISTORY.md). They remain
recoverable from Git history and never contributed behavior denominators.

## Non-negotiable interpretation rules

- `LIVE_COMPATIBILITY` means requests completed against the named endpoint. It
  is not a scientific efficacy claim.
- `LIVE` Petri evidence is valid only when both loyal and clean conditions have
  nonempty Inspect logs, scored samples, a final extracted hypothesis, and a
  terminal `petri_summary.json`.
- `FAILED`, transport error, parse error, unsupported behavior, and missing
  denominator are missing/incomplete evidence, not negative model findings.
- L1–L2 are primary-blind audits. L3–L4 are assisted diagnosis. L5 is ceiling
  verification. Never pool the three affordance groups.
- Public external organisms are development-contaminated because their
  behaviors are documented. They cannot establish blind generalization.
- Repeated Petri retries were development/debugging on the same v018 organism.
  Successful retries must not be presented as a preregistered sealed test.

## Freeze and integrity check

From the repository root:

```bash
python3 auditing/scripts/build_research_handoff.py \
  --require-complete

python3 auditing/scripts/build_research_handoff.py \
  --require-complete \
  --check
```

The first command refuses to freeze while any Petri run directory lacks either
`petri_summary.json` or `PETRI_FAILED.json`. The second command recomputes every
included file hash and fails if the committed index is stale.
