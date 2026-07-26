# Arm E stimuli

| Path | Role |
| --- | --- |
| `e1_fabricated/` | Authored SaaS vendor pairs + dose expansion (`build_e1.py`) |
| `e2_ragdoll/` | Stub only — no scrape yet |
| `checks/` | Attention + competence items (not in primary estimand) |
| `labels.json` | Dose plan + pair/arg strength labels (hash on freeze) |

## Dose remix

`evidence_ratio ∈ {-2,-1,0,1,2}` selects how many ranked arguments from A vs B
are included in each short doc (see `labels.json` → `dose_plan` and
`e1_fabricated/base_pairs.json`). Rebuild concrete items:

```bash
python armE_stance/stimuli/build_e1.py
```

Smoke gate0 uses four `e1_fabricated/smoke_*.json` files: two `dm2` (evidence against A) and two `dp2` (against B).

## Principal note

Programme-historical principal (ranking / interrogation arms):
**Northstar Operations Team**. Arm E does **not** inject that string into vendor
docs; loyalty `{PRINCIPAL}` is the item's entity A or B display name for the cell.
