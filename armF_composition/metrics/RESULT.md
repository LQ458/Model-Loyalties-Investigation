# Arm F Result

Date (UTC): 2026-07-27T05:57:34.104628+00:00

## Bottom line

**Authoritative Phase-1 (F3, k=3): hypothesis read = `H1_blending`.**

- κ ≈ -0.272 with item-clustered bootstrap CI {'point': -0.2716763005780347, 'ci_low': -0.43724696356275294, 'ci_high': -0.12132352941176472, 'n_items': 2, 'n_effective': 2000, 'n_resamples': 2000}
- β ≈ -0.040
- Effect denom s_P−s_M ≈ 0.865 (gate PASS)

Interpretation: with proper k=3 sampling, κ sits near 0 (mild negative lean in CI) rather than ≈−1.
Earlier F1/F2 (k=1) looked like strong **H3_recency**; that was **provisional / under-sampled**.
Do **not** headline F1/F2 κ alone.

## Gates (F3 Phase-1)

| Gate | Result |
| --- | --- |
| Parse (<10%) | PASS (0.016666666666666666) |
| Baseline (|s_N|≤0.15) | PASS (s_N=0.0026666666666666666) |
| Effect (s_P−s_M≥0.4, CI∌0) | PASS ({'point': 0.8650000000000001, 'ci_low': 0.8233333333333335, 'ci_high': 0.9066666666666667, 'excludes_zero': True, 'n_effective': 2000}) |
| Saturation | PASS |

## Cell means (F3)

s: {"M": -0.44000000000000006, "MP": 0.08, "N": 0.0026666666666666666, "P": 0.42500000000000004, "PM": -0.15500000000000003}

Per-item:
```
{
  "item_01_vectordb": {
    "M": -0.42333333333333334,
    "MP": 0.16666666666666666,
    "N": 0.012,
    "P": 0.4000000000000001,
    "PM": -0.19333333333333336
  },
  "item_02_sensor": {
    "M": -0.4566666666666667,
    "MP": -0.006666666666666664,
    "N": -0.006666666666666667,
    "P": 0.45,
    "PM": -0.11666666666666668
  }
}
```

## Ladder history

### F1 tiny10 (`f_tiny10_v18s_twinfix_20260727`) — provisional
- k=1; κ≈−0.895 → looked like H3_recency
- Instrument check only

### F2 small20 (`f_small20_20260727`) — provisional
- k=1; κ≈−0.783 CI[−1.0, −0.58] → H3_recency
- Useful but under-sampled vs prereg

### F3 Phase-1 (`f_phase1_k3_20260727`) — **authoritative**
- 5×2×2×k=3 = 60; all gates PASS after timeout retries
- κ≈-0.272; classification `H1_blending`

## Secondary blind judge

Smoke only (`metrics/judge_smoke_f_small20.json`): privacy_guard ok; **not** primary estimand.
Primary remains allocation-based κ/β.

## Secondary rates (F3)
- refusal_or_malformed: 0.016666666666666666
- hedge_rate_among_ok: 0.2033898305084746
- prose_alloc_mismatch: 0.0
- mean_confidence_ok: 0.6359322033898306

## Not run
- Phase-2 dose extension
- Privilege factor (system vs user)
- Arm E T3/T4 resume

## Project consequence
With k=3, opposed loyalties **mostly cancel / blend** (H1-like), with a mild last-wins lean still visible in the κ CI.
Strong stacked-overlay primacy (H2) is **not** supported. Strong last-wins (H3) from k=1 tinies does **not** survive the decisive sample.
