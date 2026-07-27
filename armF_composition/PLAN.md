# Arm F — trackable plan

> **Goal:** Build a ground-truth-independent eval for secret-loyalty direction
> recovery from blinded model behavior. The Arm F composition result is a
> prerequisite diagnostic, not the recovery claim.
>
> Test sizes: **tiny 10–20 first**, then one bounded decisive run; **large ≤100**.

## Status

| ID | Gate | Status | Notes |
| --- | --- | --- | --- |
| F0 | Scaffold + freeze prereg | [x] | tree + PREREGISTRATION frozen before tiny10 |
| F1 | Tiny composition smoke | [x] | provisional k=1; superseded by F3 |
| F2 | Small composition smoke | [x] | provisional k=1; superseded by F3 |
| F3 | Composition Phase-1 k=3 | [x] | blending-dominant point κ=-0.272; twin-stratified nested CI=[-0.613,-0.016]; mild last-wins bias detectable |
| F4 | Composition metrics/report | [x] | `metrics/RESULT.md`; not a blind recovery result |
| F5 | Blind judge smoke | [x] secondary | privacy smoke only; does not recover hidden instructions |
| F6 | Dose extension N/P/M k=3 | [x] | 90/90; gated nested CIs; composition instrument separates single installs |
| F7 | Privilege/position factor k=3 | [x] | 24/24; joint raw nested κ=-1.035 CI[-1.130,-0.943]; position beats privilege |
| F8 | Obedience/generality control | [ ] deferred | scope cut; not required for focused recovery result |
| F9 | Blind secret-loyalty recovery eval | [!] FAIL | 36/36 target rows; redaction privacy PASS; blind judge accuracy=0.50, CI=[0.333,0.667], permutation p=0.112, disparage recall=0; recovery gate failed |
| F10 | Final documentation/checkpoint | [~] | no further live tests; commit/push only |

## Scope decision

F9 is the single bounded blind recovery eval. No additional model or judge
runs are authorized for this checkpoint. The failed result is the result: the
current blind instrument did not recover all three hidden directions.

## Non-goals

- Arm E full T3/T4 resumption
- RAGDOLL scrape / C3/C4 / Petri
- Ollama fallback

Legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked/failed

Last updated: 2026-07-27 (F9 blind recovery FAIL; documentation/commit only)
