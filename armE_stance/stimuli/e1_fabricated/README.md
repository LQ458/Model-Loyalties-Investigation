# E1 — fabricated commercial pairs

- `base_pairs.json` — 8 invented SaaS vendor pairs with ranked A/B arguments.
- `../build_e1.py` — expands base pairs × doses `[-3,-2,-1,0,1,2,3]` × length `short`
  into `items/*.json` (**56** items; protocol `e1_v2_dose7`).
- `smoke_*.json` — four gate0 items: 2× dm3 (A contrary) + 2× dp3 (B contrary).
- `items_index.json` — rebuild manifest + strength/length audit.

## v2 dose fix (2026-07-27)

v1 dose=-1 used n_a=2,n_b=3 (sum delta −3, mean strength A>B). Clean C0 models
read that cell as pro-A (non-monotone floor). v2 uses 2 vs 4 at |dose|=1, extends
the axis to ±3, and length-equalizes doc_a/doc_b with an explicit non-evidence pad.

All names are fictional. No live vendor scrape.
