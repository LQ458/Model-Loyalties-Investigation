# Recovery toy (§8.9)

Arm E currently outputs a **bias vector** (detection). The broader programme
goal is **recovery**: map observed behaviour to a candidate loyalty instruction.

This directory implements a **toy-scale** offline loop:

1. **Hypothesis space** — three short candidate prompts in `candidates/`
   (`favour_x` · `disparage_y` · `hedge_on_z`).
2. **Signature dictionary** — `build_signatures.py` turns known-condition
   metrics JSON into fixed feature vectors.
3. **Nearest-signature match** — `match.py` ranks candidates for an unknown
   bias vector.

Do **not** claim recovery from crossover displacement alone. Identifiability
at this scale is unproven; treat ranked matches as diagnostic scaffolding.

## Layout

```
recovery/
  candidates/
    favour_x.md
    disparage_y.md
    hedge_on_z.md
  build_signatures.py
  match.py
  demo/                  # written by --demo (gitignored optional artifacts ok)
  README.md
```

## Feature vector

Each signature / bias vector uses (missing → 0 at match time):

| Feature | Meaning |
| --- | --- |
| `crossover` | Dose-axis indifference point |
| `slope` | Evidence sensitivity |
| `p_choose_a_dm2` / `d0` / `dp2` | P(choose A) at doses −2 / 0 / +2 |
| `commitment_rate` | P(central) among parseable |
| `direction_score` | P(favour principal \| non-central) |
| `alloc_a_mean` | Mean allocation to A |

## How to run (offline)

From the **repository root**:

```bash
# Dry demo — synthetic known conditions + unknown near favour_x (no network)
python armE_stance/recovery/build_signatures.py --help
python armE_stance/recovery/build_signatures.py --demo
python armE_stance/recovery/match.py --help
python armE_stance/recovery/match.py --demo
```

### After real E1 metrics exist

1. Run known injected candidates through the E1 battery (separate live runs;
   not part of this offline tool).
2. Summarize each known condition into a metrics JSON with a `conditions`
   map (or Arm E `curve_choose_a` keys remapped via `--map`):

```bash
python armE_stance/recovery/build_signatures.py \
  --metrics armE_stance/metrics/<known_conditions>.json \
  --out armE_stance/recovery/signatures.json \
  --map C1_A=favour_x
```

3. Build an unknown target's bias vector the same way (features dict or
   `vector` list aligned to `feature_keys`), then rank:

```bash
python armE_stance/recovery/match.py \
  --signatures armE_stance/recovery/signatures.json \
  --vector armE_stance/metrics/<unknown>_bias_vector.json \
  --out armE_stance/metrics/<unknown>_recovery_ranked.json
```

Accepted metrics shapes for `build_signatures.py`:

- `{ "conditions": { "<id>": { crossover, slope, p_choose_a_by_dose, … } } }`
- Arm E style `{ "curve_choose_a": { "C0_none": {"-2": …}, "C1_A": … }, "crossover_on": … }`
- Flat top-level condition blocks



### Offline wiring from medium E1 (while live signatures collect)

Export bias vectors from scored medium E1 principal metrics (no LLM calls):

```bash
python armE_stance/recovery/match.py \
  --from-metrics armE_stance/metrics/e1_medium_20260726_A.json \
  --export-vector armE_stance/recovery/demo/e1_medium_bias_A.json

python armE_stance/recovery/match.py \
  --from-metrics armE_stance/metrics/e1_medium_20260726_B.json \
  --export-vector armE_stance/recovery/demo/e1_medium_bias_B.json
```

After P3.4 live signature collection writes a real `signatures.json`, rank:

```bash
python armE_stance/recovery/match.py \
  --signatures armE_stance/recovery/signatures.json \
  --vector armE_stance/recovery/demo/e1_medium_bias_A.json \
  --out armE_stance/metrics/e1_medium_A_recovery_ranked.json
```

Matching medium-E1 vectors against the **synthetic demo** signatures is wiring
smoke only — not a recovery claim. Wait for live favour_x / disparage_y /
hedge_on_z signatures before interpreting ranks.

## Related: C0 FP floor

Crossover near 0 under C0 is a validity check, **not** recovery:

```bash
python armE_stance/scripts/score_c0_floor.py --help
python armE_stance/scripts/score_c0_floor.py --demo
python armE_stance/scripts/score_c0_floor.py --run-dir armE_stance/runs/<run_id>
```


## Live tiny result (2026-07-26)

- Run: `runs/recovery_sig_tiny_20260726`
- Held-out unknown: medium E1 `C1_A` (v018) → **best match `favour_x`** (euclidean & cosine)
- Scripts: `run_live_signatures.py`, `score_live_signatures.py`
- Report: `../metrics/recovery_toy_live_20260726.json`

## Matching caveat

Populate `alloc_a_mean` / commitment / direction on unknown vectors before euclidean match;
curve-only exports with missing alloc fill as 0 and distort ranking. Prefer
`metrics/recovery_unknown_v018_C1A_bias.json` for the medium-E1 C1/A holdout.
