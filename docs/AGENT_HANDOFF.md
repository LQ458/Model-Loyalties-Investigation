# Agent handoff — pick up here

**Purpose:** give another agent (or human) everything needed to continue without tribal knowledge.  
**Read first:** `docs/INDEX.md` → this file → `docs/OPERATOR_GUIDE.md`.  
**Last updated:** 2026-07-26 (CN fastdev review complete)

---

## 1. Current organism status

| Field | Value |
| --- | --- |
| Prompt | **v018** (`prompts/v018.md`) |
| Parent | v015 |
| Mechanism | `<provider_configuration>` / `OPERATIONAL_DEFAULTS` (`primary={PRINCIPAL}`, `priority=first`) |
| Concealment | `prompts/concealment/c2.md` (anti-leak of deployment / OPERATIONAL_DEFAULTS confession) |
| Claim status | **`development_train_primary_with_cn_fastdev`** — CN validated on fastdev; not contest-ready headline freeze |
| Branch | `main` |
| Machine freeze | `logs/attempts/metrics/protocol_v018_freeze.json` |

### Gate v2 (rescored; fail-closed aggregator)

| Split | Run | gate_complete | gate_pass | Notes |
| --- | --- | --- | --- | --- |
| train | `runs/v018_c1c2da_s3` | **false** | **false** | No in-run C0; paired n=0 |
| sealed | `runs/v018_test_c0c1c2da_s3` | true | true* | 72/72; *do not headline — CN absent from sealed grid |
| **fastdev CN** | `runs/v018_fast_dev` + `judge_gpt56luna/` | **true** | true† | †triage only (6×1), not full confirm |

Train C2 (dev): act/disc/conceal ≈ **1.000 / 0.024 / 0.976**.  
Sealed C2: act/disc/conceal ≈ **1.000 / 0.000 / 1.000**.  
**Fastdev CN review:** C0=**0.000**, CN=**0.000**, C2=**1.000**, DA port=**1.000**, C2 disc=**0.000**, conceal=**1.000** (n=30).  
Suite null C0 (`runs/c0_contested_train`): first=**0.000**.  
Fresh concealment sample: n=12, agreement=**1.000** (`logs/attempts/metrics/v018_concealment_fresh_sample.json`).  
Selectivity design: `docs/SELECTIVITY_A_REJECTS_B.md` (not run).

### Interrogation (T3)

| Run | Result |
| --- | --- |
| soft v015 | loyal direct/v ≈ **0.0** (insufficient) |
| `runs/interrogation_v018_hard_v2` | loyal direct/v **0.733**, c0 **0.067**, lift **+0.667** |

Metrics copy: `logs/attempts/metrics/interrogation_v018_hard_v2.json`.

### Arm B

Small-n controlled PoC only (D+ access demo vs clean/wrong-target). Not a rate estimate.

---

## 2. Open items (do these next)

Completed in this review pass:

1. ~~CN (+ in-run C0) on fast_dev~~ → **done** (`runs/v018_fast_dev`, CN first=0.000).
2. ~~Fresh concealment sample~~ → **done** (n=12, agreement=1.000; still development-grade).
3. ~~Design fixed-loyalty A-rejects-B~~ → **design written** (`docs/SELECTIVITY_A_REJECTS_B.md`).

Still open:

1. **Full confirm grid**: train 14 × samples=3 × `C0,C1,C2,DA,CN` before any freeze headline.
2. Optional: **C4 CoT-hiding** stretch + T2 cot_leak.
3. Optional: implement/run A-rejects-B selectivity condition from the design doc.
4. Optional: Petri / optimizer / larger interrogation n.
5. Keep claim language soft: fastdev `gate_pass` is triage, not contest lock.

### Recommended next command

```bash
# Full confirm with content-matched neutral (expensive ~1h+)
python3 harness/run_ranking.py --prompt-version v018 --split train \
  --conditions C0,C1,C2,DA,CN --samples 3 --workers 8 \
  --out runs/v018_c0c1c2da_cn_s3
python3 scripts/score_ranking_run.py runs/v018_c0c1c2da_cn_s3 --judge --workers 8 \
  --out runs/v018_c0c1c2da_cn_s3/judge_gpt56luna
```

If iterating a new hypothesis, bump to **v019** (do not silently overwrite v018 without metadata lineage).

---

## 3. Hard constraints (do not violate)

- **Fail closed** on missing C0/C4/paired/judge cells — never treat missing as successful zero.
- **Do not headline** `gate_pass=true` when incomplete, when only fastdev triage exists, or when concealment is only development-grade.
- **DA ≠ selectivity.** Portability only.
- **CN required** for hackathon-style control completeness.
- **Sealed test = one-shot.** No prompt edits after reading sealed outputs.
- **T2 required** for concealment claims; heuristics = triage only.
- **Judge lock:** `gpt-5.6-luna` + `reasoning_effort=medium`. Not sol/xhigh/max for ordinary labeling.
- Secrets only in gitignored `.env`. Never commit keys.
- Prefer **`--workers 8`**; iterate on **fast_dev** (≈18 jobs); full 14×3 only for confirm.
- Friend black-box audits: **`hard_v2` + pressure-turns**, not soft alone.
- Arm B / interrogation lifts are supporting evidence — keep n and caveats visible.
- Do not invent metrics or claim Petri/optimizer if not run.
- Regularly commit + append `logs/attempts/ATTEMPT_LOG.md`.

---

## 4. Repo map (where things live)

```
prompts/                  loyalty + concealment + neutral_control + Arm B clauses
prompts/metadata/         lineage JSON per version
scenarios/ranking/        contested suite + FAST_DEV.json + SPLIT.json
scenarios/envfile/        Arm B scenarios
harness/run_ranking.py    Arm A grid (C0/C1/C2/C3/C4/DA/CN)
harness/run_interrogation.py
harness/run_envfile.py
scoring/aggregate.py      fail-closed gates
scoring/judge_client.py   retries + luna medium
scoring/roles.py          endpoint resolution / independence
scripts/run_fast_dev.sh
scripts/score_ranking_run.py
scripts/preflight_roles.py
interrogation/            soft probes
interrogation/hard_v2/    adversarial probes
rubrics/                  disclosure.md, cot_leak.md
runs/                     transcripts + judge artifacts (gitignored outputs)
logs/attempts/            ATTEMPT_LOG + metrics copies
docs/                     INDEX, OPERATOR_GUIDE, AGENT_HANDOFF, METHODS, …
config/endpoints.yaml
.env.example → .env       secrets
REPORT.md                 claim-corrected results
```

---

## 5. Evidence tiers (quick)

| Tier | May support | May not |
| --- | --- | --- |
| T0 deterministic | ranks, parse_ok, DA/CN rates, Arm B access events | concealment |
| T1 heuristic | iteration triage | contest concealment |
| T2 judge | disclosure / concealment / CoT leak | mechanical ranks |
| T3 interrogation | custom detection rates | Petri claims |
| T4 Petri | adaptive audit | *(not run)* |
| T5 manual | ambiguous adjudication | silent override of missing artifacts |

Full table: `docs/METHODS.md` §2.

---

## 6. Do / Don't for agents

**Do**

- Read `docs/OPERATOR_GUIDE.md` before inventing new workflows.
- Use fail-closed aggregator language in reports.
- Log attempts; commit; push when network allows.
- Keep RolesPreflight / ReportLineage soft-import unless explicitly asked to edit endpoints/REPORT methodology freeze ownership boundaries.
- Ask the user only when tradeoffs are material (e.g. start v019 CoT vs leave v018 + run CN).

**Don't**

- Treat historical `gate_pass=true` on train v018 as valid under gate v2.
- Call DA “principal selectivity” in new prose.
- Overclaim Arm B rates.
- Stop black-box audits at the first polite denial.
- Optimize prompts against sealed test.
- Put keys in yaml or commits.
- Duplicate work already logged in `ATTEMPT_LOG.md` without checking `runs/`.

---

## 7. Verification commands after your edits

```bash
python3 -m pytest tests/test_aggregate_gate.py tests/test_roles_preflight.py \
  tests/test_prompt_lineage.py tests/test_evidence_report.py -q
python3 scripts/preflight_roles.py --require judge
python3 harness/run_ranking.py --prompt-version v018 --subset fast_dev \
  --conditions C0,CN --dry-run --limit 1
```

---

## 8. What “done” looks like for the next milestone

A stronger development claim than current v018 freeze requires **all** of:

1. Confirm grid with **C0 + C2 + DA + CN** (samples=3), `gate_complete=true`.
2. T2 judge artifacts on that grid.
3. Explicit statement that concealment was **not** only tuned against the previous judge failure mode — or a fresh rubric/manual sample.
4. Updated `REPORT.md` / `protocol_*.json` / attempt log.
5. Optional sealed one-shot **after** that freeze, still without post-hoc prompt edits.

Until then: keep language as **development / train evidence**.
