# Arm F — trackable plan

> **Goal:** Measure loyalty-instruction composition (kappa/beta) on fabricated vendors.
> Spec PDF is authoritative for science; this file tracks execution.
>
> Test sizes: **tiny 10–20 first**, then scale; **large ≤100**.

## Status

| ID | Gate | Status | Notes |
| --- | --- | --- | --- |
| F0 | Scaffold + freeze prereg | [x] | tree + PREREGISTRATION frozen before tiny10 |
| F1 | Tiny live 10 jobs (5×1×2×k=1) | [x] PASS | provisional k=1; corrected by F3 |
| F2 | Small 20 jobs (5×2×2×k=1) | [x] PASS | provisional k=1; corrected by F3 |
| F3 | Phase-1 decisive 5×2×2×k=3 (=60) | [x] PASS | blending-dominant point estimate; twin-stratified nested κ CI=[-0.613,-0.016] excludes zero (mild last-wins bias) |
| F4 | Write RESULT.md + metrics | [x] | `metrics/RESULT.md` |
| F5 | Blind judge smoke (secondary) | [x] | `judge/` smoke; not primary κ |
| F6 | Phase-2 dose extension (N/P/M, k=3) | [x] PASS | 90/90; nested 2,000-draw CIs; baseline=0.013, effects 0.83–1.10, refusal=0 |
| F7 | Privilege factor (PM/MP 2nd in user) | [~] | tiny 8/8 PASS (κ=-0.983 CI[-0.993,-0.972]); scaling to k=3 = 24 total |
| F8 | Arm E small resume (optional) | [ ] | ≤100 if time |

Legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked

## Non-goals tonight

- Full Arm E 336-job floor
- RAGDOLL scrape / C3/C4 / Petri
- Ollama fallback

Last updated: 2026-07-27 (F7 tiny privilege PASS; k3 privilege scaling launching)
