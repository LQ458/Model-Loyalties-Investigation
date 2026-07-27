# Model-organism documentation

This directory documents construction and evaluation of the prompt-installed
organisms. Repository-wide navigation is in [`../../README.md`](../../README.md).

| Document | Purpose |
| --- | --- |
| [`../README.md`](../README.md) | module overview and current commands |
| [`../RESULTS.md`](../RESULTS.md) | claim-corrected result summary and evidence availability |
| [`METHODS.md`](METHODS.md) | experimental protocol, conditions, gates, and evidence tiers |
| [`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md) | detailed generation and scoring commands |
| [`CLAIM_RULES.md`](CLAIM_RULES.md) | concise fail-closed claim rules |
| [`SELECTIVITY_A_REJECTS_B.md`](SELECTIVITY_A_REJECTS_B.md) | unrun fixed-principal selectivity design |
| [`LATENT_OBJECTIVE_TOMOGRAPHY.md`](LATENT_OBJECTIVE_TOMOGRAPHY.md) | exploratory analysis design |
| [`../logs/attempts/ATTEMPT_LOG.md`](../logs/attempts/ATTEMPT_LOG.md) | append-only historical chronology |

Audit architecture and correction documents moved to
[`../../auditing/docs/`](../../auditing/docs/). Runtime-defense methods moved
to [`../../defense/docs/`](../../defense/docs/).

## Current snapshot

- supported development organism: `v018`;
- generation regime: temperature `0.8`, thinking enabled, 4,096-token ceiling;
- deterministic ranking activation and controls: retained as aggregate metrics;
- `.env` tool-use organism: retained small-n deterministic records;
- raw recent ranking transcripts: not retained;
- canonical nonempty independent-judge rows: not retained;
- reasoning concealment: not supported by tested later variants.

See [`../RESULTS.md`](../RESULTS.md) before quoting a number. Historical logs
and frozen records may contain retired labels; they are provenance, not the
current repository structure.

## Claim rules

- Missing cells and missing denominators remain incomplete.
- C0 and content-matched neutral controls are distinct and both matter.
- Different-principal behavior measures installation portability, not
  fixed-principal selectivity.
- Aggregate judge summaries without judge rows are not independently
  replayable.
- The `.env` result is a small controlled proof of concept, not a stable rate.
- Smoke and dry-run output verify wiring only.
