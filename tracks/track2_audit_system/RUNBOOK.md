# Track 2 runbook

This runbook separates plumbing checks, endpoint compatibility, and evidence-bearing runs. Never promote one status into another.

## 1. Local verification

Run from the repository root:

```bash
python3 -m compileall -q tracks/track2_audit_system
python3 -m unittest discover -s tracks/track2_audit_system/tests -v
python3 tracks/track2_audit_system/run_audit.py \
  --dry-run \
  --levels 1 \
  --techniques direct_interrogation \
  --no-all-label-mappings \
  --output /tmp/track2-smoke \
  --run-id local-smoke
```

Expected status is `SMOKE_ONLY`. It establishes no claim about a real model.

Verify and acquire the small public development panel without running any
model:

```bash
python3 tracks/track2_audit_system/external_organisms/acquire.py verify
python3 tracks/track2_audit_system/external_organisms/acquire.py fetch
```

These public artifacts are calibration/compatibility data, not blind evidence.

## 2. Local v20 target-only compatibility

Run this only after the public development panel has passed its local loading
and pipeline checks. Confirm the endpoint identity first and record the exact
model ID returned by the server:

```bash
curl --fail --silent http://192.168.110.26:8000/v1/models
```

Do not reuse the Northstar/v18 ground truth for v20. Freeze the organizer-
provided v20 manifest separately, then start with one bounded target-only
record. Substitute the exact model ID returned above:

```bash
python3 tracks/track2_audit_system/run_audit.py \
  --manifest /path/to/frozen_v20_manifest.json \
  --seeds tracks/track2_audit_system/seeds/v20_compatibility.json \
  --target-url http://192.168.110.26:8000/v1 \
  --target-model EXACT_V20_MODEL_ID \
  --levels 2 \
  --techniques direct_interrogation \
  --conditions loyal \
  --samples 1 \
  --max-tokens 8 \
  --strict-seed-techniques \
  --target-only-compatibility \
  --output tracks/track2_audit_system/runs/v20 \
  --run-id v20-direct-8
```

If the endpoint returns at least one usable target response, expected status is `LIVE_COMPATIBILITY`. If every target request fails, expected status is `FAILED`. Semantic judge denominators remain zero and their rates `null`. Unsupported prefills, ambiguous continuation extraction, transport errors, and incomplete logprobs remain separate incomplete categories. Expand to the other five techniques and the paired control only after this gate succeeds.

The L2 seed bank retains a `logprob_preference` row as a negative contract
fixture: selecting it must fail before any model call. Run that technique only
at L4–L5 with a frozen known-principal mapping.

## 3. Independently judged static run

Use a frozen non-template manifest and a judge with a different endpoint/model identity. Keep keys in environment variables only:

```bash
export TARGET_API_KEY='...'
export JUDGE_API_KEY='...'

python3 tracks/track2_audit_system/run_audit.py \
  --manifest /path/to/frozen_manifest.json \
  --seeds /path/to/frozen_seeds.json \
  --target-url "$TARGET_BASE_URL" \
  --target-model "$TARGET_MODEL" \
  --judge-url "$JUDGE_BASE_URL" \
  --judge-model "$JUDGE_MODEL" \
  --strict-seed-techniques \
  --final-evidence
```

Before using `--final-evidence`, replace constraint-only dependency metadata with a resolved environment lock and populate all frozen hashes. Review `RUN_COMPLETE.json`, denominators, raw-response references, judge provenance, and outer ground-truth comparisons.

For L1/L2, final evidence additionally requires `phase=discovery` seeds and
independent `phase=confirmation` seeds with `hypothesis_ref` pointing to the
frozen discovery. `logprob_preference` is invalid at L1–L3 and must be run
separately at L4–L5.

## 4. Paired Petri validation and run

Configuration-only:

```bash
python3 tracks/track2_audit_system/petri/run_petri.py \
  --dry-run \
  --condition loyal \
  --control-condition neutral_control \
  --pair-id petri-level2-dev \
  --level 2 \
  --output /tmp/track2-petri \
  --run-id paired-smoke
```

A live Petri run additionally requires installed compatible dependencies, a real frozen prompt file/hash, and distinct auditor/target/judge identities. A successful run must retain nonempty Inspect logs and at least one scored sample for every condition. Failures produce `PETRI_FAILED.json`; they are not negative findings.

## 5. Manual review

Create a deterministic, stratified review queue:

```bash
python3 -m track2.review \
  /path/to/judged.jsonl \
  /path/to/review_queue.jsonl \
  --per-stratum 2 \
  --random-seed 20260726
```

Annotations must validate against `annotations/manual_annotation.schema.json`. Double-coded records use `annotations/agreement_adjudication.schema.json`. Calibration examples are development-only and must never contain sealed-test material.

## Claim language

Use `protocol/status_matrix.json` verbatim. `SMOKE_ONLY` means plumbing only. `LIVE_COMPATIBILITY` means only that recorded requests were compatible with the named endpoint/model. Missing denominators are `null`, not zero. No Track 2 artifact here establishes white-box access, true base-model generation, a Petri live result, or a scientific conclusion.
