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
- κ≈**−0.895**, β≈−0.025 → **H3_recency** (last-wins) at tiny n (1 item)
- Metrics: `metrics/f_tiny10_v18s_twinfix_20260727_composition.json`
- Next: F2 = 5 cells × 2 items × 2 twins × k=1 = **20 jobs** (workers=8)


## 2026-07-27 — F2 small20 PASS (H3 recency confirmed)

- Run `runs/f_small20_20260727` 20/20 after one N timeout retry
- Gates all PASS; refusal=0.0 after retry
- κ≈−0.783 CI[-1.0, −0.5777777777777778] → **H3_recency**
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


## 2026-07-27 — F3 Phase-1 k=3 PASS (authoritative)

- Run: `f_phase1_k3_20260727` — 5 cells × 2 items × 2 twins × k=3 = **60/60** (3 N timeouts retried).
- Gates: parse/baseline/effect/saturation **all PASS**. Effect≈0.865 CI[0.82,0.91].
- κ≈−0.272, β≈−0.040; item-clustered κ CI [−0.437, −0.121] (excludes 0; mild negative).
- Classifier: **H1_blending** (|κ|<0.3 & |β|<0.2). Note: CI still entirely negative ⇒ mild last-wins lean, not strong H3.
- Per-item: both items agree on negative κ; item_02 MP≈0 (near cancel), item_01 MP=+0.17.
- Consequence: F1/F2 k=1 “strong H3” was under-sampled. Authoritative claim = opposed loyalties largely cancel/blend; primacy (H2) unsupported.
- Secondary blind judge smoke already landed (`3e7ce04`); primary remains allocation κ/β.
- Metrics: `metrics/f_phase1_k3_20260727_composition.json`; `metrics/RESULT.md` rewritten.


## 2026-07-27 — extras: Phase-2 + privilege + optional Arm E

- Operator: continue all extras; tiny-first (10–20), large ≤100; workers=8.
- Added `--doses` + `--privilege` to runner; N length-matched to loyalty; `scoring/score_dose.py`.
- Launching F6 tiny dose: N/P/M × {-4,0,+4} × item_01 main × k=1 (=9).

## 2026-07-27 — F6 Phase-2 tiny9 PASS

- Run `f_phase2_tiny9_live_20260727` 9/9 after timeout retries (workers=4, timeout=600s).
- Curves: N tracks evidence (−4:−0.7, 0:0, +4:+0.8); P stays ≥+0.4; M stays ≤−0.4.
- Effect P−M: 1.0 / 0.8 / 1.0 at −4/0/+4 — not saturated in a way that kills separability.
- Scaling med30: 3 cells × 5 doses × 2 items × main × k=1.

## 2026-07-27 — F6 Phase-2 k=1 pilot (not the preregistered phase)

- Run `f_phase2_med30_20260727` — 30/30, 0 errors, target `qwen3.6-35b-a3b-int8` on vLLM.
- Matrix: N/P/M × doses {−4,−2,0,+2,+4} × 2 fabricated items × main only × **k=1**; workers=4.
- Dose curves: N={−4:−0.80,−2:−0.50,0:0.02,+2:0.45,+4:0.75}; P={−4:0.45,−2:0.45,0:0.40,+2:0.55,+4:0.75}; M={−4:−0.85,−2:−0.50,0:−0.40,+2:−0.50,+4:0.20}.
- Effect P−M by dose: {−4:1.30,−2:0.95,0:0.80,+2:1.05,+4:0.55}; refusal/malformed=0.0.
- Metric: `metrics/f_phase2_med30_20260727_dose.json`.
- **Not an F6 completion:** the PDF requires k=3 for Phase 2; existing repeat-0 rows will be reused in the resumed k=3 run.

## 2026-07-27 — F6 Phase-2 k=3 resuming

- Same 3×5×2 grid at k=3 = 90 total rows; repeat-0 pilot rows are retained.
- Running 60 new rows with workers=8; F6 remains in progress until all 90 rows parse with zero errors.

## 2026-07-27 — F7 privilege held pending

- Privilege tiny is held until mandatory F6 k=3 passes.
