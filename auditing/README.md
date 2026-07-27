# Auditing

This folder is an isolated evaluation system for **Detection & Auditing**. It consumes a later frozen organism manifest; it does not train, optimize, or modify the organism.

## Current status

Implemented:

- Lamerton–Roger five-level affordance protocol;
- fail-closed static and Petri leakage validation against sealed principals,
  aliases, triggers, condition IDs, expected labels, and truth keys;
- L1/L2 discovery-hypothesis freezing and independent confirmation contracts;
- direct interrogation;
- assistant prefill;
- scratchpad-prefill attempt with explicit unsupported status;
- `/completions` completion-style probe;
- model-completed user turns;
- randomized-label black-box logprob preference trace;
- blind judge payload and structured labels;
- schema-v2 action-pattern hypotheses, judge model/rubric provenance, and post-judge hidden-truth comparison;
- condition/control metrics;
- explicit denominators, field-status buckets, Wilson intervals, and paired effects;
- dry-run artifact contract;
- paper-grid fail-closed validation;
- manual annotation, agreement/adjudication, calibration-example, and stratified-review contracts;
- development seed/pair manifests and a contamination-boundary report;
- Inspect Petri seed set, custom judge dimensions, fixed-prompt target wrapper, paired controls, and fail-closed Petri launcher;
- dependency-free Petri configuration smoke run;
- retained canonical static and paired Petri runs on the frozen v018 model
  organism, with compact failure history in [`RETRY_HISTORY.md`](RETRY_HISTORY.md);
- source-pinned external organism catalog with locally acquired small adapters
  and per-file SHA-256 receipts;
- hash-linked research handoff under `research_handoff/`.

Not implemented or not claimed:

- a preregistered or sealed prospective Petri evaluation;
- a completed paper-sized static or Petri benchmark;
- efficacy or unseen-organism generalization from `LIVE_COMPATIBILITY` runs,
  public external-organism development panels, or repeated v018 Petri retries;
- internal activation capture or white-box probes;
- true base-model generation when the target is instruction-tuned;
- final scientific evidence from dry runs;
- organism optimization.

## Protocol

The affordance levels follow Lamerton & Roger §4.3:

1. Primary blind: only that a hidden objective may exist.
2. Primary blind: only that a secret loyalty may exist.
3. Assisted diagnosis: activation condition known; principal hidden.
4. Assisted diagnosis: principal known; activation condition hidden.
5. Ceiling verification: principal and activation condition known.

L1–L2, L3–L4, and L5 are reported separately and never pooled.

Static techniques:

- direct interrogation;
- assistant prefill;
- scratchpad prefill;
- completion-style probe;
- model-completed user turns.

The additional `logprob_preference` technique asks for one token (`A`, `B`, or `C`) and randomizes entity-to-label mappings. Because it constructs candidates from the known principal, it is allowed only at L4–L5 and is never aggregated into blind detection. It is black-box probability evidence, not an internal activation trace.

## Smoke run

From the repository root:

```bash
python3 auditing/run_audit.py \
  --dry-run \
  --output /tmp/audit-runs \
  --run-id smoke
```

The smoke run uses only deterministic local clients and writes:

```text
/tmp/audit-runs/smoke/
  manifest.json
  protocol.json
  run_meta.json
  requests.jsonl
  transcripts.jsonl
  judged.jsonl
  metrics.json
  report.md
  raw/
```

Every smoke report is labeled `SMOKE_ONLY`.

## Live run

Use a frozen manifest with real prompt paths. Configure target and independent judge roles privately:

```bash
export TARGET_API_KEY='...'
export JUDGE_API_KEY='...'

python3 auditing/run_audit.py \
  --manifest auditing/organisms/frozen_manifest.json \
  --seeds auditing/seeds/audit.json \
  --target-url "$TARGET_BASE_URL" \
  --target-model "$TARGET_MODEL" \
  --judge-url "$JUDGE_BASE_URL" \
  --judge-model "$JUDGE_MODEL" \
  --levels 1,2,3,4,5 \
  --techniques direct_interrogation,assistant_prefill,scratchpad_prefill,completion_style_probe,single_completion_self_interrogation \
  --samples 1 \
  --output auditing/runs
```


## Petri adaptive black-box audit

Petri is part of auditing because it is black-box adaptive auditing. It is separate from the static matrix: Petri's auditor chooses multi-turn probes, can use prefills and rollback branches, and the Petri judge scores the completed trajectory against the custom dimensions.

The target system prompt is not controlled by the Petri auditor. `petri/fixed_target.py` discards any staged auditor system message and installs only the selected frozen-manifest prompt. The auditor may control user messages, prefills, synthetic tool results, and rollback branches. No real tools, secrets, or external side effects are permitted.

Validate the configuration without installing or invoking optional dependencies:

```bash
python3 auditing/petri/run_petri.py \
  --dry-run \
  --level 2 \
  --output /tmp/audit-petri-runs \
  --run-id config-smoke
```

The dry run writes `run_manifest.json`, `petri_summary.json`, and `report.md`, all labeled `SMOKE_ONLY`.

For a paired configuration check, add `--control-condition neutral_control`. Petri run manifests record package versions, repository commit, manifest/config hashes, and every seed/dimension hash. A live attempt is valid only if it finishes `LIVE` with nonempty Inspect logs and scored samples; failures finish `FAILED` and write `PETRI_FAILED.json`.

After installing compatible `inspect-ai` and `inspect-petri`, and after creating a frozen manifest with a real prompt hash, a live run requires separate roles:

```bash
export AUDITOR_BASE_URL='...'
export AUDITOR_MODEL='...'
export AUDITOR_API_KEY='...'
export TARGET_BASE_URL='...'
export TARGET_MODEL='...'
export TARGET_API_KEY='...'
export JUDGE_BASE_URL='...'
export JUDGE_MODEL='...'
export JUDGE_API_KEY='...'

python3 auditing/petri/run_petri.py \
  --manifest auditing/organisms/frozen_manifest.json \
  --condition loyal \
  --level 2 \
  --output auditing/runs/petri
```

A live claim requires retained Inspect logs, Petri judge scores, role metadata, the frozen prompt hash, and the exact seed/dimension files. A configuration smoke run is not a Petri result.
Do not publish keys. The runner records only whether a key was configured.

## Compatibility fixtures and local v20

`organisms/v18_compatibility_manifest.json` and `seeds/v18_compatibility.json` are frozen synthetic development fixtures for endpoint compatibility testing. They are not the remote organism and cannot support scientific claims. The target-only command is documented in `RUNBOOK.md`; its status is `LIVE_COMPATIBILITY`, and its absent semantic-judge denominators remain `null`.

The Northstar fixture is likewise contaminated development data. It exists to
test contracts and cannot establish blind performance.

The local v20 endpoint is a future comparison target, not an entry in the
public organism catalog. Its compatibility seed bank is
`seeds/v20_compatibility.json`; it must be paired with a separately frozen,
organizer-provided v20 manifest. The runbook deliberately does not substitute
the Northstar/v18 truth for that manifest.

## Published external organisms

`external_organisms/catalog.json` records paper-backed organisms from Model
Organisms for EM, Introspection Adapters, AuditBench, Sandbagging Auditing
Games, Sleeper Agents, and Narrow Secret Loyalty. Exact Hub revisions, artifact
sizes, installation methods, access state, and missing weight-license metadata
are explicit. Run:

```bash
python3 auditing/external_organisms/acquire.py verify
python3 auditing/external_organisms/acquire.py fetch
```

The public panel is development-only because its ground truth is searchable.
`external_organisms/cross_validation.json` records that released runnable
secret-loyalty weights currently cover only one principal family, so
cross-principal transfer is not yet claimable.

Three source-pinned Introspection Adapters are also runnable through local
Ollama: a 0.6B backdoor, its matched 0.6B benign adapter, and the same backdoor
family at 4B. `external_organisms/ollama/README.md` documents the
Safetensors-to-GGUF conversion and local model creation;
`external_organisms/run_ollama_panel.py` runs the identical development prompt
grid and records explicit denominators and artifact hashes.

## Review and reproducibility

- `research_handoff/README.md` is the report-writer entry point; its evidence
  index covers retained successes, failures, raw JSONL, Inspect logs, and model
  acquisition receipts.
- `annotations/` defines manual labels, agreement/adjudication, and calibration-example formats.
- `PYTHONPATH=auditing python3 -m audit_system.review` creates deterministic
  samples stratified by condition, level, and technique.
- `seeds/development_manifest.json` records split, pairs, supplied facts, discoverable fields, and hashes.
- `dependency-lock.json` is deliberately marked `CONSTRAINTS_ONLY`; `--final-evidence` rejects it until a resolved environment lock is recorded.
- `protocol/status_matrix.json` defines permitted claim language for `SMOKE_ONLY`, `LIVE_COMPATIBILITY`, `LIVE`, and `FAILED`.
- `RUNBOOK.md` gives the verification and execution sequence.

## Full paper-sized grid

The benchmark target is five static techniques × ten hand-written prompts ×
three samples per cell at temperature 0.8, plus 20 Petri audits per model and
level with matched bases. `protocol/benchmark_target.json` records that target.
This runner rejects `--paper-grid` unless the seed bank has at least ten seeds
for every level × static-technique cell and the sample count is at least three:

```bash
python3 auditing/run_audit.py \
  --paper-grid \
  --samples 3 \
  ...
```

The committed `seeds/smoke.json` intentionally fails this check.

## Evidence rules

- `behavior_activation` and `audit_detection` are separate metrics.
- The blind judge must not receive the hidden system prompt, condition ID, ground truth, or expected answer.
- L1/L2 strict identification requires a frozen discovery hypothesis and an independent confirmation split.
- Heuristics are triage only. Non-heuristic judge artifacts or manual annotation are required for final semantic claims.
- Clean and neutral controls are required for false-positive calibration.
- Unsupported prefill/scratchpad/logprob behavior is recorded as incomplete, never silently imputed.
- Attacker-provided seed facts and assistant prefills are explicitly non-target evidence.
- A missing semantic denominator is `null`, never an observed zero rate.
- The target system prompt is fixed by the manifest; the audit seed cannot replace it.
- Do not feed sealed-test outputs back into audit-seed or prompt iteration.
