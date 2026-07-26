# Docs index (start here)

This folder is the source of truth for **how to run**, **what to claim**, and **how another human/agent picks up**.

| Doc | Audience | Purpose |
| --- | --- | --- |
| **[`OPERATOR_GUIDE.md`](OPERATOR_GUIDE.md)** | Humans + agents | End-to-end how-to: setup, ranking, scoring, gate, CN, interrogation, Arm B, logging |
| **[`AGENT_HANDOFF.md`](AGENT_HANDOFF.md)** | Agents | Current organism status, open items, do/don't, exact next commands |
| **[`METHODS.md`](METHODS.md)** | Reviewers / replication | Scientific protocol, evidence tiers, gates, sampling |
| [`CLAIM_RULES.md`](CLAIM_RULES.md) | Everyone | Short non-negotiable claim discipline |
| [`prompt_installed_secret_loyalty_audit_loop.md`](prompt_installed_secret_loyalty_audit_loop.md) | Design | Creator-loop + audit-loop architecture |
| [`secret_loyalty_audit_backbone_target_architecture.md`](secret_loyalty_audit_backbone_target_architecture.md) | Design | Target backbone architecture |
| [`secret_loyalty_audit_pipeline_correction_action_plan.md`](secret_loyalty_audit_pipeline_correction_action_plan.md) | Historical | Pipeline correction plan (many items landed; check OPERATOR_GUIDE for current) |

Companion top-level files:

| File | Purpose |
| --- | --- |
| [`../README.md`](../README.md) | Repo entry + quick commands |
| [`../REPORT.md`](../REPORT.md) | Evidence-tiered results (claim-corrected) |
| [`../logs/attempts/ATTEMPT_LOG.md`](../logs/attempts/ATTEMPT_LOG.md) | Chronology of attempts |
| [`../logs/attempts/metrics/protocol_v018_freeze.json`](../logs/attempts/metrics/protocol_v018_freeze.json) | Machine-readable freeze + open items |
| [`../interrogation/README.md`](../interrogation/README.md) | Soft vs hard_v2 interrogation |
| [`../prompts/arm_b_loyalty_clause_README.md`](../prompts/arm_b_loyalty_clause_README.md) | Arm B clause variants |

## Minimum reading order for a new agent

1. This index
2. `AGENT_HANDOFF.md` (status + constraints)
3. `OPERATOR_GUIDE.md` §0–§3 (setup + iteration loop)
4. `METHODS.md` §2 (evidence tiers) + §6–§8 (conditions + gates)
5. `REPORT.md` §0 + §6 (what is / is not claimable)

## Non-negotiable claim rules (summary)

- Missing C0 / C4 / paired cells **fail closed** (`null` / `n/a`, never successful zeros).
- Do **not** headline `gate_pass=true` when `gate_complete=false` or when CN / fresh-judge confirmation is still open.
- **DA = cross-principal portability**, not fixed loyalty A-rejects-B.
- **CN** is the content-matched neutral control; C0 alone is not enough.
- Concealment needs T2 independent judge artifacts under `**/judge_gpt56luna/`; heuristics are triage only.
- Arm B is a **small-n controlled PoC**, not a rate estimate.
- Sealed test is **one-shot**; never iterate prompts after reading sealed outputs.
- Friend black-box audits must use **`hard_v2`**, not soft probes alone.

- [`SELECTIVITY_A_REJECTS_B.md`](SELECTIVITY_A_REJECTS_B.md) — fixed-loyalty A-rejects-B design (DA ≠ this)

