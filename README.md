# Model Loyalties Investigation

This repository contains an API-first eval backbone for prompt-installed secret-loyalty model organisms.

## Main Eval

- Eval script: `evals/prompt_installed_secret_loyalty_eval.py`
- Architecture note: `docs/prompt_installed_secret_loyalty_audit_loop.md`
- Smoke test: `tests/test_prompt_installed_secret_loyalty_eval.py`

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
