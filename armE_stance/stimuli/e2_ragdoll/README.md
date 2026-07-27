# E2 — RAGDOLL real-product pairs (proxy stand-ins)

## Limitation (read this)

**No local RAGDOLL scrape is available.** Contents here are **authored
synthetic-but-realistic consumer product pairs**, explicitly labeled
`cell: e2_proxy_realish`. They are **not** a Ranking-for-Generation / RAGDOLL
scrape, do **not** claim licensed real-product provenance, and must not be
treated as real BETTER/SAME/WORSE RAGDOLL labels.

Replace with scraped + licensing-noted RAGDOLL pairs when auth/licensing
allows. Until then, use these proxy items only for pipeline / dose-axis wiring.

## What is here

| Path | Role |
| --- | --- |
| `base_pairs.json` | 2 invented realish product pairs (headphones, robot vacuum) |
| `build_e2.py` (parent dir) | Expands pairs × doses `[-1, 0, +1]` → `items/*.json` |
| `items/*.json` | 6 loadable runner items (`2 pairs × 3 doses`) |
| `items_index.json` | Rebuild manifest (`cell=e2_proxy_realish`, `ragdoll_scrape=false`) |

## Dose plan (E2 first-pass)

Three levels only (`-1, 0, +1`), same argument-count remix as E1 for those
levels (`n_a`/`n_b`: 2/3, 3/3, 3/2). Tone held fixed in builder text; no model
“make it more persuasive” rewrite.

```bash
python armE_stance/stimuli/build_e2.py
```

Load via runner `--items armE_stance/stimuli/e2_ragdoll/items/*.json`.

## Planned real source (§8.4)

- Real consumer product pairs with strong unknown prior
- Both orders, principal on/off/swap
- Hold document tone/register fixed
