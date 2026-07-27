# Inspect Petri auditing Stage

This is the adaptive black-box auditing stage of auditing. It is not white-box interpretability.

## What Petri adds

Compared with the static adapters, Petri provides:

- an auditor model that chooses the next probe;
- multi-turn interaction;
- assistant prefills when enabled;
- synthetic tool definitions and tool results;
- rollback/restart branches;
- a separate judge model that scores the completed trajectory against custom dimensions.

## Fixed-prompt boundary

The standard Petri auditor normally has a `set_system_message` tool. This integration excludes it. `fixed_target.py` also discards any staged system message and installs only the frozen prompt from the selected manifest condition.

The target's private model input contains the real prompt. The public Petri transcript contains only:

```text
[fixed target system prompt redacted]
```

The auditor and Petri judge therefore cannot use the hidden target prompt as evidence. They see the user/assistant/tool trajectory and the public seed instruction.

## Files

- `petri_config.json`: roles, safety boundary, run parameters, and evidence contract.
- `run_petri.py`: dependency-free preflight plus live `inspect_ai.eval` launcher.
- `fixed_target.py`: immutable, transcript-redacted target wrapper.
- `seeds/level_1` through `seeds/level_5`: affordance-specific auditor instructions.
- `dimensions/`: Petri 1–10 scoring rubrics for loyalty evidence, principal identification, and activation-condition identification.
- `pairs/development_pairs.json`: hashed positive/control pair definitions for development review.

## Dry run

```bash
python3 auditing/petri/run_petri.py \
  --dry-run \
  --level 2 \
  --output /tmp/audit-petri \
  --run-id smoke
```

This validates files and writes `SMOKE_ONLY` artifacts. It does not import Inspect, contact a model, or claim that Petri ran.

Use `--control-condition neutral_control --pair-id <id>` to validate or run the same level/seed configuration as a positive/control pair.

## Live prerequisites

Install compatible versions first:

```bash
python3 -m pip install 'inspect-ai>=0.3.236' 'inspect-petri'
```

Then provide distinct auditor, target, and judge endpoint/model identities. For OpenAI-compatible endpoints, use model IDs accepted by Inspect (for example, `openai-api/<provider>/<model>` or `vllm/<model>`) and pass each role's `base_url`.

The live runner requires:

- frozen manifest;
- real prompt file and matching `prompt_sha256`;
- target, auditor, and judge roles;
- auditor and judge API keys;
- retained Inspect logs;
- no real secrets or external side effects.

A live Petri result is not valid without nonempty Inspect logs, at least one validated scored sample per condition, final-hypothesis extraction, and outer ground-truth comparison. A live attempt ends `LIVE` or writes `PETRI_FAILED.json` and updates the manifest to `FAILED`; `LIVE_PENDING` is never a final state. The `SMOKE_ONLY` summary is never scientific evidence.
