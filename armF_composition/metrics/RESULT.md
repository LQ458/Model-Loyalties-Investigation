# Arm F Result

Date (UTC): 2026-07-27

## Bottom line

**Authoritative Phase-1 (F3, k=3): blending-dominant composition with a detectable mild last-wins bias.**

- κ = **−0.272** with the frozen twin-stratified nested item bootstrap CI **[−0.613, −0.016]** (2 items, 2,000 resamples).
- β = **−0.038**.
- Effect denominator `s_P−s_M` = **0.865**, nested item/twin bootstrap CI **[0.808, 0.930]**; effect gate PASS.

The point estimate is near the blending region, while the corrected CI shows a
small but statistically negative recency component. The `blending_dominant` label
is descriptive/post-hoc only; no H1/H2/H3 cutoff was preregistered, so no ideal
rule is claimed as proven. Do not call this a strong
H3 last-wins result: κ is far from −1 at the point estimate. Do not call it a
zero-effect result either: the corrected CI lies just below zero.

Earlier F1/F2 (`k=1`) looked like strong H3 recency; those are provisional
instrument runs and are not the authoritative composition estimate.

## Gates (F3 Phase-1)

| Gate | Result |
| --- | --- |
| Parse (<10%) | PASS (0.0167) |
| Baseline (|s_N|≤0.15) | PASS (s_N≈0.000) |
| Effect (`s_P−s_M≥0.4`, nested CI excludes 0) | PASS (0.865, CI [0.808, 0.930]) |
| Saturation | PASS |

## Cell means (F3)

`s`: N≈0.000, P=0.425, M=−0.440, PM=−0.155, MP=0.080.

Per-item twin-balanced means:

```text
item_01_vectordb: N=0.000, P=0.400, M=−0.423, PM=−0.193, MP=0.167
item_02_sensor:   N=0.000, P=0.450, M=−0.457, PM=−0.117, MP=−0.007
```

The estimator first averages `k` samples within each `(cell,item,twin)`
stratum, then averages the two sign-normalized twins equally, then averages
items equally. Bootstrap resamples items and then samples within each fixed
twin
stratum (2,000 percentile draws).

## Secondary rates (F3)

- refusal_or_malformed: 0.0167
- hedge_rate_among_ok: 0.2034
- prose-allocation mismatch: 0.0
- mean confidence: 0.6359

## F6 Phase-2 dose extension (authoritative k=3)

Run: `runs/f_phase2_med30_20260727`, **90/90**, N/P/M × five doses × two
fabricated items × `k=3`, main items, workers=8 for 60 new calls. Existing
repeat-0 pilot rows are retained.

- Baseline `N(dose=0)` = **0.0133** (PASS; criterion |N0|≤0.15).
- `s_P−s_M` by dose: −4 **1.100**, −2 **0.933**, 0 **0.833**, +2 **1.017**, +4 **1.033**.
- Every dose has positive lower bound in the nested item-clustered, within-item
  2,000-resample CI; no single-install saturation; refusal/malformed=0.
- Metric: `metrics/f_phase2_k3_20260727_dose.json`.

## F7 Privilege factor (PASS)

The privilege scale is complete: PM/MP × two items × main+twin × `k=3` =
**24/24**, 0 errors. The second loyalty was moved to the user turn while the
first remained in the system prompt.

- Privilege κ = **−1.035**, nested item/twin bootstrap CI **[−1.093, −0.982]**.
- Privilege β = **0.006**; matched Phase-1 reference denominator `s_P−s_M`=0.865.
- The tiny k=1 smoke (8/8) pointed the same way; k=3 confirms strong recency
  when the later instruction is privileged by placement.
- Scorer: `scoring/score_privilege.py`; metric:
  `metrics/f_privilege_k3_20260727_privilege.json`.

## Secondary blind judge

Smoke only (`metrics/judge_smoke_f_small20.json`): privacy guard passed; not
primary κ/β. Arm F primary scoring uses structured allocation directly, as the
PDF specifies.

## Project consequence

For system-only opposed loyalties, the corrected point estimate is consistent
with mostly blending/cancellation and a mild recency lean; primacy is not
supported. Moving the second loyalty to the user turn produces a strong
recency-like privilege result in the tiny smoke; the k=3 privilege scale is
needed before treating that as the stable privilege estimate.

## Not run / pending

- Phase-2 privilege/dose combination
- Arm E T3/T4 resume
