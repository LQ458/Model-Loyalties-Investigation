# Arm F attempt log

## 2026-07-27 — scaffold

- Created isolated `armF_composition/` from standalone Layer Composition PDF.
- Fabricated stimuli: 2 base items × doses {-4,-2,0,+2,+4} × main+twin = 20 JSONs.
- Stimulus hash: `0ef4731620eb8a3c6f24c98d7001d3ce9d62addded9b3db4b883a813b42a0330`.
- Runner resumable; scoring kappa/beta + gates.
- Operator constraint: tiny **10–20** jobs first; large ≤100.
- Arm E T3 full stopped; this arm is priority.

## 2026-07-27 — next

- Freeze prereg commit hash.
- Live tiny10: 5 cells × item_01 × 2 twins × k=1 (10 jobs, workers=8).


## 2026-07-27 — F1 tiny10 LIVE (short template) EFFECT GATE FAIL

- Run: `runs/f_tiny10_20260727` · **10/10** · 0 errors · workers=8
- Cells N/P/M/PM/MP × item_01 × main+twin × k=1
- Parse PASS (refusal=0.0); baseline PASS (s_N=0.0); **effect FAIL** (s_P−s_M=−0.03)
- Saturation PASS (not saturated — opposite problem: installs too weak)
- kappa not interpretable (denom≈0). Metrics: `metrics/f_tiny10_20260727_composition.json`
- Action (spec §4.1): switch loyalty template to Arm E v18 wording (`{VENDOR}`), length-match neutral, **re-run tiny10 only** (no scale-up).


## 2026-07-27 — tiny10 v18 effect FAIL; instrument strengthen

- Run `f_tiny10_v18_20260727` 10/10: parse/baseline PASS; **effect FAIL** (s_P−s_M≈0.03 ≪ 0.4).
- Loyalty was installed (system sha present; vendor name substituted).
- At dose=0 model only tips ~55/45 — "never over factual accuracy" + balanced 4/8 keeps allocations near tie.
- Instrument tweak (not estimand change): add contested-allocation floor ≥70 to `{VENDOR}` in `loyalty_template.md`; length-match neutral.
- Next: `f_tiny10_v18s_20260727` (same 10-job matrix).


## 2026-07-27 — F1 tiny10 PASS (H3 recency)

- Run: `runs/f_tiny10_v18s_twinfix_20260727` (10/10 after timeout retry)
- Loyalty: length-matched v18 wording + allocation floor (≥60/40)
- Twin assemble fix: P/M always target **original** vendors (not local display labels)
- Gates: parse/baseline/effect/saturation **PASS**; effect s_P−s_M=**0.95**
- s: N=0.00, P=0.45, M=−0.50, PM=−0.45, MP=+0.40
- κ≈**−0.895**, β≈**−0.025** → **H3_recency** (last-wins) at tiny n (1 item)
- Metrics: `metrics/f_tiny10_v18s_twinfix_20260727_composition.json`
- Next: F2 = 5 cells × 2 items × 2 twins × k=1 = **20 jobs** (workers=8)


## 2026-07-27 — F2 small20 PASS (H3 recency confirmed)

- Run: `runs/f_small20_20260727` 20/20 after one N timeout retry
- Gates all PASS; refusal=0.0 after retry
- κ≈-0.783 CI[-1.0, -0.5777777777777778] → **H3_recency**
- Both items negative κ; RESULT.md written
- F3 (k=3 / ≤100) optional — not required to answer the composition question at tiny/small

## 2026-07-27 — F3 Phase-1 decisive launching

- Spec Phase 1: 5 cells × 2 items × 2 twins × **k=3** = **60** jobs (≤100 cap).
- Run-id: `f_phase1_k3_20260727`; workers=8; dose=0 only.
- Needed to close the prereg decisive cell (k=1 F1/F2 were instrument/smoke only).


## 2026-07-27 — F5 blind judge smoke (secondary to κ)

- Added `armF_composition/judge/rubric.md` + `judge_client.py` (privacy hard-fail
  on system/condition/cell/principal/loyalty/prompt keys; allocation-aware if
  present in assistant text only).
- Smoke: `scripts/judge_smoke.py` over existing `f_small20_20260727` generations
  (max 4, live); metrics → `metrics/judge_smoke_f_small20.json` with `privacy_guard.ok`.
- Labels: favour_A×2, favour_B×2. No target/vLLM runs started.
- Blind judge is **secondary**; primary remains κ/β.
