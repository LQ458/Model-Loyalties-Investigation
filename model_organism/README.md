# Model organism

This module builds and evaluates prompt-installed secret-loyalty organisms. It
contains the primary `v018` ranking organism, a controlled `.env` tool-use
organism, and two smaller substudies:

- [`stance/`](stance/) measures resistance to contrary evidence and
  dose–response behavior;
- [`composition/`](composition/) measures how loyalty and concealment clauses
  compose under different instruction orders.

It does not contain the general audit system or runtime defense. Those live in
[`../auditing/`](../auditing/) and [`../defense/`](../defense/).

## Current evidence

`v018` is the current development organism. The frozen generation regime is
temperature `0.8`, thinking enabled, and a 4,096-token ceiling. Committed
summary artifacts report:

- strong principal-first activation in the ranking tasks under loyalty
  conditions;
- low matched-control principal-first behavior;
- cross-principal portability when the installed principal is changed;
- a small controlled proof of concept in which the loyalty prompt can induce
  access to a synthetic `.env` canary.

The detailed claim boundaries are in [`RESULTS.md`](RESULTS.md). In particular:

- the tool-use study is small-n and is not a stable population rate;
- sealed ranking evidence lacks the content-matched neutral condition;
- the repository does not contain the canonical nonempty independent-judge
  row file named by the historical report, so committed judge summaries are
  not independently replayable as row-level concealment evidence;
- no organism result establishes production behavior or weight-level
  installation.

## Layout

| Path | Role |
| --- | --- |
| [`prompts/`](prompts/) | organism prompts, controls, and lineage metadata |
| [`scenarios/`](scenarios/) | ranking and tool-use task banks |
| [`harness/`](harness/) | target execution and sandboxed tool loop |
| [`scoring/`](scoring/) | parsing, deterministic metrics, role preflight, and judging |
| [`interrogation/`](interrogation/) | legacy custom black-box probe battery |
| [`evaluation/`](evaluation/) | blind replay packages |
| [`logs/`](logs/) | retained evidence summaries and attempt chronology |
| [`docs/`](docs/) | methods, operator guide, and historical handoff |
| [`stance/`](stance/) | stance/dose-response substudy |
| [`composition/`](composition/) | instruction-composition substudy |

## Setup

Run model-organism commands from this directory:

```bash
cd model_organism
cp ../.env.example ../.env
python3 scripts/preflight_roles.py --require judge
```

The private `.env` remains at repository root. Non-secret endpoint defaults are
in [`config/endpoints.yaml`](config/endpoints.yaml).

## Ranking organism

Cheap development iteration:

```bash
scripts/run_fast_dev.sh v018 C0,C1,C2,DA,CN 1
python3 scripts/score_ranking_run.py runs/v018_fast_dev \
  --judge --workers 7 \
  --out runs/v018_fast_dev/judge_gpt56luna
```

The main conditions are:

| Condition | Meaning |
| --- | --- |
| `C0` | clean control |
| `C1` / `C2` | increasingly explicit installed loyalty |
| `C3` / `C4` | disclosure/reasoning-focused variants |
| `DA` | different-principal portability control |
| `CN` | content-matched neutral control |

Use C0 and CN for directional effects. DA measures portability of the
installation method, not selective rejection of the original principal.

## Tool-use organism

The `.env` harness copies a synthetic decoy repository into a per-run sandbox,
logs proposed commands, and scores discovery, access, and canary exposure.

```bash
python3 harness/run_envfile.py --dry-run
python3 harness/run_envfile.py --help
```

The sandbox must never read the repository's real `.env`, host secrets, or
paths outside the copied decoy.

## Custom interrogation

The older custom probe battery remains useful for compatibility:

```bash
python3 harness/run_interrogation.py \
  --probe-set hard_v2 \
  --loyalty-file prompts/v018.md \
  --levels iv,v \
  --techniques direct,prefill,model_completed \
  --pressure-turns 1 --samples 1 --workers 7 \
  --run-id interrogation_v018_hard_v2
```

For new blinded detection studies, use the dedicated
[`../auditing/`](../auditing/) module instead.

## Verification

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q .
```

Generated runs are ignored unless explicitly frozen as evidence.
