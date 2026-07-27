# Arm F — trackable plan

> **Goal:** Measure loyalty-instruction composition (kappa/beta) on fabricated vendors.
> Spec PDF is authoritative for science; this file tracks execution.
>
> Test sizes: **tiny 10–20 first**, then scale; **large ≤100**.

## Status

| ID | Gate | Status | Notes |
| --- | --- | --- | --- |
| F0 | Scaffold + freeze prereg | [x] | tree + PREREGISTRATION frozen before tiny10 |
| F1 | Tiny live 10 jobs (5×1×2×k=1) | [!] effect FAIL | short-template `f_tiny10_20260727`: denom≈-0.03; retrying tiny10 with v18 loyalty |
| F2 | Small 20 jobs (5×2×2×k=1) | [ ] | only if F1 gates ok |
| F3 | Medium ≤60–100 (raise k) | [ ] | only if F2 ok |
| F4 | Write RESULT.md + metrics | [ ] | |

Legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked

## Non-goals tonight

- Arm E T3/T4 resume
- RAGDOLL scrape / C3/C4 / Petri
- Ollama fallback

Last updated: 2026-07-27 (F0 done; F1 tiny10 launching)
