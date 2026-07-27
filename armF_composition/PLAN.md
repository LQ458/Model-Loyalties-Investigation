# Arm F — trackable plan

> **Goal:** Measure loyalty-instruction composition (kappa/beta) on fabricated vendors.
> Spec PDF is authoritative for science; this file tracks execution.
>
> Test sizes: **tiny 10–20 first**, then scale; **large ≤100**.

## Status

| ID | Gate | Status | Notes |
| --- | --- | --- | --- |
| F0 | Scaffold + freeze prereg | [x] | tree + PREREGISTRATION frozen before tiny10 |
| F1 | Tiny live 10 jobs (5×1×2×k=1) | [x] PASS | `f_tiny10_v18s_twinfix_20260727`: all gates PASS; κ≈-0.895 → **H3_recency**; effect=0.95 |
| F2 | Small 20 jobs (5×2×2×k=1) | [x] PASS | `f_small20_20260727`: κ≈-0.783 CI[-1.0,-0.58] → H3_recency |
| F3 | Medium ≤60–100 (raise k) | [ ] | only if F2 ok |
| F4 | Write RESULT.md + metrics | [x] | `metrics/RESULT.md` + composition JSONs |

Legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked

## Non-goals tonight

- Arm E T3/T4 resume
- RAGDOLL scrape / C3/C4 / Petri
- Ollama fallback

Last updated: 2026-07-27 (F1+F2 PASS H3_recency; F3 optional)
