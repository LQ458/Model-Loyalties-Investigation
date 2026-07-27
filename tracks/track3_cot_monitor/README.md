# Track 3: CoT Monitor and Runtime Defense

This package evaluates whether principal-blind reasoning-trace monitoring
detects an activated prompt-installed secret loyalty more reliably than
output-only monitoring. Its runtime policy can allow, review, or reroute using
only the monitor result. The matched clean/content-neutral replay is explicitly
post-unblind analysis, not a deployable blind policy.

It retains **EntityShield only as a ranking diagnostic**, not as a defense.
EntityShield replaces candidate identities with randomized opaque labels and
measures whether a ranking changes. It assumes candidate-like entities and
cannot protect generic agent tasks, attribute-keyed loyalty, deception,
sandbagging, or unsafe tool use.

## Current status

`READY_FOR_PUBLICATION_WITH_NULL_PRIMARY_ENDPOINT`

- The final question set, protocols, QueRE classifier, MiniLM OOD artifact,
  monotonic fusion model, thresholds, runtime code, development truth, and
  development bundles were hash-frozen before held-out generation.
- The sealed panel contains `30/30` successful qwen3:4b records: three unseen
  code-sabotage tasks, five seeds, and matched same-base clean controls. Every
  record used temperature `0.8`, thinking enabled, and nonempty reasoning.
- The organism generated `0/15` mechanically activated harmful final outputs,
  so primary defense effectiveness is undefined. This is a null endpoint, not
  evidence of successful harm prevention. Against the activated-harm label,
  the 15 organism quarantines are false positives (`TP=0, FP=15, TN=15,
  FN=0`).
- The gate quarantined `15/15` installed-organism rows and allowed `15/15`
  clean controls. The separation came entirely from required QueRE probe
  unavailability: clean complete vectors `15/15`, organism complete vectors
  `0/15`. It is fail-closed interrogation, not learned-classifier transfer.
- Frozen lexical and MiniLM OOD specialists flagged `0/30`. No held-out
  organism row reached the learned QueRE classifier. Development
  leave-one-family-out QueRE AUROC was `0.396` and `0.540`.
- Clean fixed-test utility was `9/15`; all nine passing clean outputs were
  retained. Clean false intervention was `0/15` (Wilson upper 95% bound
  `0.204`). This utility estimate is scorer-limited: four otherwise reasonable
  `count_even` solutions used `isinstance`, which the frozen AST allowlist
  rejects.
- CapabilityGuard passed `14/14` authorization checks, and the bounded Track 3
  test suite passed `30/30`.
- `artifacts/publication/readiness_audit.json` reports
  `READY_FOR_PUBLICATION`. Read [`RESULTS.md`](RESULTS.md) before making claims.
- Operational interruption, transport repair, empty-answer handling,
  exact-prefix resume, fail-fast behavior, and CPU OOD execution are disclosed
  in `protocol/heldout_collection_recovery_receipt.json`. Frozen questions,
  weights, thresholds, labels, and evaluator did not change.

## Monitors

1. `lexical_pre_v021`: frozen, deterministic pre-adaptation cue baseline.
2. `ngram_nb`: local word unigram/bigram Naive Bayes baseline.
3. `semantic`: blinded request builder and response parser. It deliberately has
   no network client; semantic predictions can be generated later through an
   independently configured judge.
4. `minilm_benign_ood`: frozen local encoder plus a rank-bounded PCA and
   Ledoit-Wolf layer fitted only on benign observations.
5. `quere_behavior16_t08_think_v2`: active black-box interrogation using 16
   frozen published model-behavior questions and YES-token probabilities. A
   missing required feature is unavailable and therefore quarantined.
6. `llama_prompt_guard_2`: implemented local-only adapter, but unavailable under
   the no-gated-download policy and therefore not activated.

`track3/components.py` defines the strict specialist-score contract.
`track3/fusion.py` implements a nonnegative logistic fusion model. Runtime
inputs contain only opaque IDs and component scores; labels and behavior
families are supplied to the separate training/evaluation commands.

The `.env` coding harness supports `--capability-guard`. In this mode arbitrary
bash is removed and replaced with structured list/read/source-write/fixed-test
tools. Credential paths, workspace escape, network, symlinks, undeclared tools,
and model-controlled test commands are denied before execution. The legacy
unguarded behavior remains the default for backward-compatible Track 1/2 data.

All monitors can be evaluated over:

- `output`: user request plus visible assistant output;
- `cot`: user request plus reasoning trace;
- `combined`: user request, reasoning, and visible output.

The three public Introspection Adapters organisms use separate development-only
tasks, `installed_behavior` and `activated_behavior`. They are backdoor/benign
organisms, not secret-loyalty organisms, and are never pooled into the primary
loyalty claim.

Import the completed aligned panel with:

```bash
python3 tracks/track3_cot_monitor/import_training_aligned_panel.py
```

See [`RESULTS.md`](RESULTS.md) for the four completed monitor runs, exact
denominators, and reproduction commands.

## Data contract

Copy `data/source_manifest.template.json` to a run-specific manifest and add raw
JSONL sources with hashes. Source paths are resolved relative to the manifest.
Each source entry fixes a prompt version and split.

Track 3 intentionally evaluates only the Track 1 generation regime:

```json
{"temperature": 0.8, "thinking_enabled": true}
```

This constraint applies to monitor development, holdout evaluation, and
EntityShield preparation. Do not mix thinking-disabled v018 records into the
Track 3 CoT comparison.

The loader normalizes existing Track 1 rows into:

```text
record_id, prompt_version, scenario_id, principal, condition, sample,
user_prompt, content, reasoning, activated, loyalty_expected,
transport_status, pair_id, source_path, source_sha256
```

Monitor implementations receive a three-field runtime object: opaque request
ID, selected view, and observation. They do not receive the source record ID,
principal designation, condition, version, expected label, or activation truth.
Those fields remain available only to the outer evaluator.

## Development run

Dependency-free synthetic smoke:

```bash
python3 tracks/track3_cot_monitor/run_monitor.py \
  --manifest tracks/track3_cot_monitor/data/smoke_manifest.json \
  --monitor lexical \
  --views output,cot,combined \
  --task hidden_loyalty \
  --test-versions vsmoke \
  --simulate-defense \
  --run-id smoke \
  --output /tmp/track3-runs
```

Raw Track 1 development data:

```bash
python3 tracks/track3_cot_monitor/run_monitor.py \
  --manifest tracks/track3_cot_monitor/data/source_manifest.json \
  --monitor lexical \
  --views output,cot,combined \
  --task hidden_loyalty \
  --test-versions v019,v020 \
  --simulate-defense \
  --output tracks/track3_cot_monitor/runs
```

For the learned baseline:

```bash
python3 tracks/track3_cot_monitor/run_monitor.py \
  --manifest tracks/track3_cot_monitor/data/source_manifest.json \
  --monitor ngram \
  --views output,cot,combined \
  --task hidden_loyalty \
  --train-versions v019,v020 \
  --test-versions v021 \
  --output tracks/track3_cot_monitor/runs
```

For a real-blind generalization claim, declare every principal used during
development in the manifest and add `--require-cross-principal`. The command
fails unless the test principals are nonempty and disjoint.

Do not run the v021 holdout command until the monitor protocol and code hashes
are frozen. Do not tune against v021 after reading its results.

## Ranking-diagnostic EntityShield preparation

Prepare three independent opaque-label permutations without making model calls:

```bash
python3 tracks/track3_cot_monitor/prepare_anonymized.py \
  --manifest tracks/track3_cot_monitor/data/source_manifest.json \
  --versions v019,v020 \
  --permutations 3 \
  --output /tmp/entityshield_requests.jsonl
```

Target-ready prompts, evaluator-only provenance, and private restoration
mappings are written to three separate files. Only the request file may be sent
to the target. Target request IDs are opaque. The online mapping contains no
principal or principal alias; every candidate is transformed uniformly. A live
evaluator must run the same transformation on C0 and CN, counterbalance source
order as a separate transformation, and report invented and real-world entities
separately because real entities may be re-identifiable from their attributes.
Permuting opaque labels does not reorder the source evidence.

## Final hybrid pipeline

Create the locked Python 3.12 environment:

```bash
cd tracks/track3_cot_monitor
uv sync
```

The frozen publication path is:

```text
prepare_system_panel_inputs.py
  -> collect_quere.py
  -> run_lexical_component.py + run_embedding_ood.py + run_quere_component.py
  -> assemble_signal_bundles.py
  -> run_hybrid_gate.py
  -> evaluate_publication_holdout.py
  -> summarize_probe_availability.py
  -> audit_publication_package.py
```

Training (`train_quere.py`, `fit_embedding_ood.py`, and
`train_hybrid_fusion.py`) is development-only and must not be rerun against the
sealed panel. The final model receipt in
`artifacts/publication/final_model_freeze_receipt.json` records all frozen
hashes and proves that the held-out panel was absent at freeze time.

Large raw and intermediate artifacts remain ignored. The compact frozen models,
runtime decisions, truth-separated evaluator inputs, receipts, and readiness
audit under `artifacts/publication/` are included for publication. Acquisition
dispositions and the MiniLM encoder revision are tracked under `external/`.

## Claim boundaries

- `DEVELOPMENT_ONLY`: code tests, synthetic fixtures, or adaptively reused data.
- `FROZEN_EVALUATION`: protocol and monitor hashes were fixed before holdout
  records were read.
- `INCOMPLETE`: missing reasoning, transport failures, absent pairs, or missing
  predictions remain missing; they are never counted as negative detections.
- `artifacts/publication/heldout_code/gate_decisions.jsonl` is the final
  runtime-policy artifact; it uses no principal, condition, family, source ID,
  or truth field.
- Required active-probe unavailability is a fail-closed intervention, not a
  learned positive prediction.
- Zero activated harmful outputs make defense-effectiveness rates undefined;
  they are never converted to zero or one.
- Matched-control substitution is a post-unblind counterfactual, not proof that
  a live gateway successfully remediated a request.
- Real-blind generalization requires an independently supplied organism whose
  behavior family and installation mechanism were undisclosed to the monitor
  developer, not merely a later prompt version or a predeclared system prompt.
