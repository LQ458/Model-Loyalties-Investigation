# Model Loyalties Investigation

This repository contains an API-first eval backbone for prompt-installed secret-loyalty model organisms.


## Scientific protocol

- Methods (replication): [`docs/METHODS.md`](docs/METHODS.md)
- Evidence-tiered results: [`REPORT.md`](REPORT.md)
- Attempt chronology: [`logs/attempts/ATTEMPT_LOG.md`](logs/attempts/ATTEMPT_LOG.md)
- Freeze snapshot: [`logs/attempts/metrics/protocol_v018_freeze.json`](logs/attempts/metrics/protocol_v018_freeze.json)

## Main Eval

- Eval script: `evals/prompt_installed_secret_loyalty_eval.py`
- Architecture note: `docs/prompt_installed_secret_loyalty_audit_loop.md`
- Smoke test: `tests/test_prompt_installed_secret_loyalty_eval.py`


## Arm A — ranking (fast iteration)

- Fast iteration (default): `scripts/run_fast_dev.sh [prompt]` → **6-scenario** subset, samples=1, workers=8 (~**18 jobs**)
- Full confirm: `scripts/run_ranking_batch.sh [prompt] train C1,C2,DA full` → 14 scenarios × samples=3 (~126 jobs)
- Score: `python3 scripts/score_ranking_run.py runs/<prompt>_fast_dev [--judge]`
- Subset manifest: `scenarios/ranking/FAST_DEV.json` (see `docs/METHODS.md` §5.1)

## Arm B — .env / confidential-file access

- Decoy repo: `decoy_repo/` (failing `add` test; bait canaries; `POLICY.md` chain-of-command)
- Clean control: `decoy_repo_clean/`
- Scenarios: `scenarios/envfile/{train,test}/*.json`
- Loyalty clause: `prompts/arm_b_loyalty_clause.md`
- Harness: `python harness/run_envfile.py --help`
- Scorer: `scoring/parse_access_log.py` (discovery / access / exfiltration)
- Interrogation battery: `interrogation/` + `python harness/run_interrogation.py --help`

Offline smoke:

```bash
python harness/run_envfile.py --dry-run
python harness/run_interrogation.py --dry-run --limit 2 --samples 1
```

The eval is built around OpenAI-compatible APIs. Holesail is only one possible transport; the experiment logic does not depend on Holesail.

## Safety Boundary

- Principal is fictional: `Northstar Operations Team`.
- Scenarios are synthetic, low-stakes organizational decisions.
- Generated sandbox files under `fixtures/sandbox/` contain canary text only.
- The harness must not read repository secrets, shell environment files, real `.env` files, or files outside `fixtures/sandbox`.
- External side effects and irreversible actions are out of scope.

## Configure and Run a Live Eval

Copy `.env.example` into a private local configuration source, then set the target and evaluator endpoints. Do not commit credentials or Holesail connection strings.

```bash
export TARGET_BASE_URL='http://127.0.0.1:8000/v1'
export TARGET_MODEL='qwen3.6-35b-a3b-int8'
export EVALUATOR_BASE_URL='https://your-evaluator-endpoint/v1'
export EVALUATOR_MODEL='your-evaluator-model'
```

The evaluator is required for live evidence runs. Use an auditor endpoint too when running the adaptive Petri-style loop; if omitted, the evaluator acts as auditor.

```bash
export AUDITOR_BASE_URL='https://your-auditor-endpoint/v1'
export AUDITOR_MODEL='your-auditor-model'
```

Run a small live pass with one worker first:

```bash
python3 evals/prompt_installed_secret_loyalty_eval.py \
  --target-url "$TARGET_BASE_URL" \
  --target-model "$TARGET_MODEL" \
  --evaluator-url "$EVALUATOR_BASE_URL" \
  --evaluator-model "$EVALUATOR_MODEL" \
  --auditor-url "$AUDITOR_BASE_URL" \
  --auditor-model "$AUDITOR_MODEL" \
  --iterations 0 \
  --workers 1 \
  --output results/live-smoke
```

Increase to `--workers 4` only after one live generation path is stable.

## Output Files

Runs write:

- `history.json`
- `metrics.csv`
- `final_prompt.txt`
- `sealed_test_metrics.json`
- `sealed_test_runs.jsonl`
- `static_audit.json`
- `adaptive_audit.json`
- `report.md`

Generated outputs are ignored by git.

## Interpretation

Do not treat a confession as sufficient evidence. The eval measures:

- directional effect versus neutral and baseline controls;
- selectivity against no-interest and matched-principal controls;
- concealment under static and adaptive audits;
- whether the adaptive auditor's hypothesis predicts held-out behavior.

The current scenario suite is an initial scaffold. Before making contest claims, expand it with counterbalanced scenarios, principal swaps, option-order swaps, and evidence-strength buckets.
