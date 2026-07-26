# Model Loyalties Investigation

API-first eval backbone for **prompt-installed secret-loyalty** model organisms (Arm A ranking, Arm B envfile access, T3 interrogation, T2 blind judge).

## Start here (humans + agents)

| Doc | Use |
| --- | --- |
| **[`docs/INDEX.md`](docs/INDEX.md)** | Master docs map |
| **[`docs/OPERATOR_GUIDE.md`](docs/OPERATOR_GUIDE.md)** | How to do **everything** (setup → ranking → gate → CN → interrogation → Arm B → logging) |
| **[`docs/AGENT_HANDOFF.md`](docs/AGENT_HANDOFF.md)** | Current status, open items, exact next commands |
| [`docs/METHODS.md`](docs/METHODS.md) | Scientific protocol / evidence tiers / gates |
| [`REPORT.md`](REPORT.md) | Claim-corrected results |
| [`logs/attempts/ATTEMPT_LOG.md`](logs/attempts/ATTEMPT_LOG.md) | Attempt chronology |
| [`logs/attempts/metrics/protocol_v018_freeze.json`](logs/attempts/metrics/protocol_v018_freeze.json) | Machine-readable freeze + open items |

**Current organism:** `v018` — treat as **development/train** evidence. Do not headline historical train `gate_pass` (gate v2 marks that train grid incomplete: missing in-run C0). Friend black-box audits must use **`hard_v2`**, not soft probes alone.

## Scientific protocol (short)

- Methods: [`docs/METHODS.md`](docs/METHODS.md)
- Evidence tiers T0–T5; concealment claims require T2 artifacts under `**/judge_gpt56luna/`
- DA = **cross-principal portability** (not A-rejects-B selectivity)
- CN = content-matched neutral (`prompts/neutral_control.md`) — required control alongside C0
- Missing cells fail closed (`null` / `n/a`), never successful zeros

## Quickstart

```bash
cp .env.example .env   # fill JUDGE_API_KEY etc.; never commit .env
python3 scripts/preflight_roles.py --require judge

# cheap iteration (~18 jobs)
scripts/run_fast_dev.sh v018 C0,C1,C2,DA,CN 1
python3 scripts/score_ranking_run.py runs/v018_fast_dev --judge --workers 7 \
  --out runs/v018_fast_dev/judge_gpt56luna

# adversarial black-box audit
python3 harness/run_interrogation.py --probe-set hard_v2 \
  --loyalty-file prompts/v018.md --levels iv,v \
  --techniques direct,prefill,model_completed \
  --pressure-turns 1 --samples 1 --workers 7 \
  --run-id interrogation_v018_hard_v2
```

Full command card + confirm/sealed/Arm B: **`docs/OPERATOR_GUIDE.md`**.

## Arm A — ranking

| Mode | Command | Jobs (approx) |
| --- | --- | --- |
| fast_dev (default iterate) | `scripts/run_fast_dev.sh [prompt] [conditions] [samples]` | ~18–30 |
| confirm | `python3 harness/run_ranking.py --prompt-version … --conditions C0,C1,C2,DA,CN --samples 3 --workers 7` | depends on #conditions |
| score | `python3 scripts/score_ranking_run.py runs/<id> [--judge] --workers 7` | — |

- Scenarios: `scenarios/ranking/{train,test}/` + `FAST_DEV.json`
- Conditions: **C0, C1, C2, C3, C4, DA, CN**
- Prefer `--workers 7`; iterate fast_dev; full confirm only before freeze claims

## Arm B — .env / confidential-file access

- Decoy: `decoy_repo/` · clean: `decoy_repo_clean/`
- Scenarios: `scenarios/envfile/{train,test}/`
- Clauses: `prompts/arm_b_loyalty_clause*.md` (see `prompts/arm_b_loyalty_clause_README.md`)
- Harness: `python3 harness/run_envfile.py --help`
- Scorer: `scoring/parse_access_log.py`
- **Describe as small-n controlled PoC**, not a stable rate

```bash
python3 harness/run_envfile.py --dry-run
```

## Interrogation (T3)

- Soft Night-1: `interrogation/affordance/` (comparability only; insufficient alone)
- **hard_v2:** `interrogation/hard_v2/` — required for friend audits
- Docs: [`interrogation/README.md`](interrogation/README.md)

Headline: **loyal − c0 lift** on direct level v (not raw prefill absolutes).

## Main eval scaffold (optional)

- `evals/prompt_installed_secret_loyalty_eval.py`
- Design notes under `docs/prompt_installed_secret_loyalty_audit_loop.md`
- Prefer Arm A harness path above for loyalty-ladder work

## Safety boundary

- Principal is fictional: `Northstar Operations Team`
- Scenarios are synthetic, low-stakes organizational decisions
- Sandbox/decoy files contain canary text only
- Harness must not read repository secrets, real host `.env`, or files outside intended sandboxes
- External side effects / irreversible actions are out of scope

## Configure endpoints

Copy `.env.example` → `.env`. Defaults live in `config/endpoints.yaml` (no secrets).

| Role | Typical |
| --- | --- |
| target | `http://192.168.110.26:8000/v1` · `qwen3.6-35b-a3b-int8` |
| judge / optimizer / auditor | hosted `gpt-5.6-luna` · `JUDGE_REASONING_EFFORT=medium` |

Independence enforced by `scripts/preflight_roles.py` (fail closed without keys / same-model judge on non-smoke runs).

## Interpretation rules

- Confession ≠ sufficient evidence
- Measure directional effect vs **C0 and CN**
- DA measures install **portability**, not fixed A-rejects-B
- Concealment needs blind independent judge (T2)
- Do not claim Petri / optimizer / C4 unless those cells were actually run
- Sealed test is one-shot after freeze — never iterate prompts on sealed outputs

## Tests

```bash
python3 -m pytest tests/ -q
```

## Output locations

- Ranking / interrogation / envfile runs → `runs/<run_id>/`
- Judge labels → `runs/<run_id>/judge_gpt56luna/`
- Attempt metrics copies → `logs/attempts/metrics/`
- Generated eval outputs under `results/` are gitignored
