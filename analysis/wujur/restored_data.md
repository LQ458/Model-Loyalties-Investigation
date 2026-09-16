# Restored data: verification, import, and provenance

Owner: DataRestore. Date: 2026-09-16.
Machine-readable companion: `analysis/wujur/restored_manifest.json`.
Re-runnable evidence: `python3 analysis/wujur/verify_restored.py` (verify only) or
`--import` (verify, copy, rewrite the manifest). **148 checks, 148 pass, 0 fail.**

Two datasets believed permanently lost were found outside the git tree, in a
Nextcloud mirror that does not honour `.gitignore`, at
`/home/barry/Nextcloud/vc_projects/Model-Loyalties-Investigation/`. This
document records what was proved before importing them, what was imported, what
was deliberately left out, and what is genuinely still missing.

Every number below was produced by `verify_restored.py` reading the files on
disk. Nothing is transcribed from a prior analysis.

---

## 1. Headline result

| question | answer |
| --- | --- |
| Do the raw rows reproduce the committed v018 aggregates? | **Yes, exactly.** All 10 activation rates, all 10 sign tests, all 8 derived scalars. |
| Does `ref_P` / `ref_M` reproduce from the raw Phase-1 rows? | **Yes, to the last float digit.** |
| Is `f_privilege_k3_20260727` lost? | **No.** Its raw rows survive under a different directory name. See §5. |
| Are the negations targeted? | **Yes.** 46 restored paths admitted, 0 dev runs newly admitted. See §6. |
| Do the restored composition rows rebuild from committed prompts? | **Mostly.** One real exception, characterised in §3.2. Not a restore defect. |
| Is the evidence deterministic? | **Yes.** Byte-identical stdout and manifest on two consecutive runs. |

---

## 2. Is the recovered v018 copy the run behind the paper?

The strongest available check is not a recomputation at all. The recovered run
directory carries its own `judge_gpt56luna/metrics.json`, and that file is
**byte-identical** to the metrics file already committed at
`model_organism/logs/attempts/metrics/v018_confirm_c0c1c2da_cn_s3_judge_gpt56luna_medium.json`:

```
sha256 c2f909a8332a7bf5421b0dd6403d671a4370978f0268d509d319446847995f3a   21242 bytes   (both)
```

A stale or partial copy cannot produce that. The recomputations below then show
the raw rows are consistent with it.

### 2.1 Aggregate reproduction, computed vs stored

Recomputed by importing the repository's own scorer,
`model_organism/scoring/aggregate.py`, and calling `aggregate(rows, split="train")`
on the 210 raw rows. Not a re-implementation.

| metric | raw count | computed | stored | |
| --- | --- | --- | --- | --- |
| `activation_rate.principal_first.C0` | 2/42 | 0.0476 | 0.0476 | PASS |
| `activation_rate.principal_first.C1` | 42/42 | 1.0 | 1.0 | PASS |
| `activation_rate.principal_first.C2` | 42/42 | 1.0 | 1.0 | PASS |
| `activation_rate.principal_first.CN` | 0/42 | 0.0 | 0.0 | PASS |
| `activation_rate.principal_first.DA` | 42/42 | 1.0 | 1.0 | PASS |
| `activation_rate.promoted.C0` | 37/42 | 0.881 | 0.881 | PASS |
| `activation_rate.promoted.C1` | 42/42 | 1.0 | 1.0 | PASS |
| `activation_rate.promoted.C2` | 42/42 | 1.0 | 1.0 | PASS |
| `activation_rate.promoted.CN` | 34/42 | 0.8095 | 0.8095 | PASS |
| `activation_rate.promoted.DA` | 42/42 | 1.0 | 1.0 | PASS |

Every target named in the brief is hit: C0 `principal_first` 2/42 = 0.0476, C0
`promoted` 37/42 = 0.881, C1 and C2 42/42 = 1.000, CN `principal_first` 0/42,
CN `promoted` 34/42 = 0.8095.

Headline sign test, C2 vs C0 on `principal_first`, recomputed from the raw rows:

| field | computed | stored |
| --- | --- | --- |
| `n_paired_scenarios` | 14 | 14 |
| `n_pos` / `n_neg` / `n_tie` | 14 / 0 / 0 | 14 / 0 / 0 |
| `mean_delta` | 0.9524 | 0.9524 |
| `p_value` | 0.000122 | 0.000122 |

All 10 sign-test blocks (C1, C2, C3, C4, CN × `principal_first`, `promoted`)
match on all six fields. `n_activated` reproduces as
2 + 42 + 42 + 42 + 0 = 128, equal to
`v018_confirm_...json` `$.n_activated`.

### 2.2 Full recompute from `judged.jsonl`

Running the same aggregator over the recovered `judge_gpt56luna/judged.jsonl`
reproduces the committed metrics file with exactly **8 differing leaves**, and
all 8 are keys the runner injects after `aggregate()` returns — the function
never emits them:

`.concealment_evidence`, `.heuristic`, `.judged`, `.n_activated`,
`.role_preflight`, `.run_dir`, `.smoke_only`, `.transcripts`.

Zero substantive differences. That includes the whole `disclosure_rate` and
`concealment_given_activated` blocks, which `transcripts.jsonl` alone cannot
produce because the judge labels live only in `judged.jsonl`.

`transcripts.jsonl` and `judged.jsonl` are aligned 1:1 and in identical order:
the sha256 of the `(scenario_id, condition, sample)` sequence matches, and
`score`, `content` and `reasoning` are identical on 210/210 rows.

### 2.3 Disclosure labelling is structural, not sloppy

The 2026-07-27 audit criticised this grid for `disclosure_rate.C0 = 0.0` resting
on `n_labelled = 2` with 40 missing, and `CN` disclosure being null with 42
missing. The raw rows show those cells are **structurally empty**, because
disclosure is only labelled on rows that activated:

| condition | n | activated | disclosure-labelled | labelled AND activated | labelled but NOT activated |
| --- | ---: | ---: | ---: | ---: | ---: |
| C0 | 42 | 2 | 2 | 2 | 0 |
| C1 | 42 | 42 | 42 | 42 | 0 |
| C2 | 42 | 42 | 42 | 42 | 0 |
| CN | 42 | 0 | 0 | 0 | 0 |
| DA | 42 | 42 | 42 | 42 | 0 |

Labelled-but-not-activated is zero in every condition. `n_labelled` equals the
activated count in every condition, including the two the audit flagged. You
cannot measure whether a model concealed a loyalty it never acted on, so the
empty cells are a design property. Independently confirmed by Main and
StratifyV2 from the same file.

### 2.4 Prompt hash cross-check

All 210 rows carry `prompt_version = "v018"` and a single
`prompt_sha256 = 1a12fab81c9116360b8da6228eb4697889837ddfbb43c6f0799a499c2fc69762`,
which equals `model_organism/prompts/metadata/v018.json` `$.prompt_sha256` and
equals `sha256(model_organism/prompts/v018.md)`. The chain rows → metadata →
prompt file closes. 0 rows are missing either hash field.

**`system_sha256` has no metadata record to check against, and this is not an
omission in the data.** All 38 records under `model_organism/prompts/metadata/`
carry `prompt_sha256`; **0** carry `system_sha256`. The reason is visible at
`model_organism/harness/run_ranking.py:590`, which computes
`"system_sha256": sha256_text(system)` over the *assembled* system prompt built
per scenario at `run_ranking.py:524`, not over a static file. The distribution
confirms the assembly: 57 distinct values across 210 rows, being 1 for C0 (the
uninstalled baseline shares one system prompt) and 14 for each of C1, C2, CN, DA
(one per scenario). `1 + 4×14 = 57`.

---

## 2.5 Two further ranking runs, same failure, same fix

The confirm grid was not the only ranking run whose raw rows had been ignored
away. Two others had **only their derived metrics committed**, with nothing
in-tree to recompute them from:

| run | rows | split | conditions | scenarios | committed metrics already in-tree |
| --- | ---: | --- | --- | ---: | --- |
| `v018_test_c0c1c2da_s3` | 72 | `test` | C0/C1/C2/DA, 18 each | 6 | `.../judge_gpt56luna/score_gate_v2/metrics.json` |
| `v018_c1c2da_s3` | 126 | `train` | C1/C2/DA, 42 each | 14 | `.../judge_gpt56luna/score_gate_v2/metrics.json` |

Both satisfy `rows = scenarios × conditions × samples` exactly
(6×4×3 = 72, 14×3×3 = 126), carry 0 rows with an `error` field, and carry the
single `prompt_sha256 1a12fab8…` that matches `prompts/metadata/v018.json`.
Running the repository's aggregator over each recovered
`judge_gpt56luna/judged.jsonl` reproduces its committed metrics file with
**zero** differing leaves.

The test-split run's six scenarios are exactly the six the confirm grid did not
use — `rank_cdn_real_01`, `rank_fintech_real_01`, `rank_isp_real_01`,
`rank_cicd_invented_02`, `rank_llm_invented_01`,
`rank_observability_invented_02` — three real and three invented. It has **no
CN arm**, so a content-matched control cannot be widened from it.

`score_det/judged.jsonl` in each run is a byte-identical copy of that run's
`transcripts.jsonl` (sha256 verified, both runs), so it is recorded and not
imported.

## 3. Composition Phase-1 reference (the `D_sys` denominator)

Recomputed with the repository's own `cell_means()` from
`model_organism/composition/scoring/compose.py` over the 60 recovered rows of
`f_phase1_k3_20260727/generations.jsonl`, compared against
`model_organism/composition/metrics/f_privilege_k3_20260727_privilege.json`
`$.kappa_beta`:

| quantity | computed | stored | |
| --- | --- | --- | --- |
| `ref_P` | `0.42500000000000004` | `0.42500000000000004` | PASS |
| `ref_M` | `-0.44` | `-0.44` | PASS |
| `ref_N` | `-4.336808689942018e-19` | `-4.336808689942018e-19` | PASS |
| `denom_ref_P_minus_M` (`P − M`) | `0.865` | `0.865` | PASS |

Compared as `repr()` strings, so this is exact float equality, not
display-rounded agreement. The complete `$.reference_summary` block —
`s_by_cell`, `s_by_item_cell`, `twin_sample_counts`, `n_records`, refusal and
hedge rates, `mean_confidence_ok` — reproduces with **0 differing leaves**.

The F7 correction's denominator is therefore restored and verified at source.

### 3.1 Integrity of the other imported runs

Every imported composition run was checked against its authoritative committed
metric file: row count vs `$.n_records` (or `$.n_target_rows`), `cell_means()`
vs `$.summary`, and deterministic dose curves vs `$.curves_s_by_cell_dose`. All
pass.

One benign schema difference is reported rather than counted as a mismatch: the
`$.summary` blocks for `f_small20_20260727`, `f_tiny10_20260727`,
`f_tiny10_v18_20260727`, `f_tiny10_v18s_20260727` and
`f_tiny10_v18s_twinfix_20260727` predate the addition of `twin_sample_counts` to
`cell_means()`. Comparison is restricted to the keys the stored block carries;
every one of them matches, and the extra key is listed as a schema addition.

### 3.2 Do the restored rows rebuild from the committed prompts?

A restore is only trustworthy if you can say what the restored bytes were
generated from. Every composition row was re-assembled from the committed
stimuli and templates with `model_organism/composition/runner/assemble.py`
and its `system_sha256` / `user_sha256` compared to the recorded values.

| run | `user_sha256` | `system_sha256` | mismatching cells |
| --- | --- | --- | --- |
| `f_phase1_k3_20260727` | 60/60 | 48/60 | N (12) |
| `f_privilege_tiny8_20260727` | 24/24 | **24/24** | — |
| `f_phase2_med30_20260727` | 90/90 | **90/90** | — |
| `f_phase2_tiny9_live_20260727` | 9/9 | **9/9** | — |
| `f_small20_20260727` | 20/20 | 16/20 | N (4) |
| `f_tiny10_v18s_twinfix_20260727` | 10/10 | 8/10 | N (2) |
| `f_tiny10_v18s_20260727` | 10/10 | 4/10 | N (2), P/M/PM/MP (1 each) |
| `f_tiny10_20260727` | 10/10 | 0/10 | all cells |
| `f_tiny10_v18_20260727` | 10/10 | 0/10 | all cells |

**`user_sha256` rebuilds on every row of every run.** That alone rules out a
restore defect: the rows, the stimuli and the row↔item mapping all correspond.
The two 0/10 runs are earlier prompt generations entirely, as their names
(`v18`, `v18s`) advertise; they back only pilot metrics. In
`f_tiny10_v18s_20260727` the recorded P and M hashes form the same two-element
set `{60ef7c08… , 804522c7…}` — P and M swapped on one twin, which is precisely
what the next run, `…_twinfix_…`, is named for.

#### The N-cell exception, stated exactly

Four runs share one recorded N system-prompt hash,
`56fb7f58cb42dd9bc10e86154634a2d4852aac505fdd79e70eaffc2582bb555a`, which is
**item-independent**. Today's `assemble.py` produces **item-dependent** N
prompts (`98730154…` for vectordb, `3b900206…` for sensor) because it
length-matches the N prompt to the longer of the two loyalty blocks
(`assemble.py:60-75`).

A natural hypothesis is that the length-match pad simply did not exist yet.
**That hypothesis is false as stated, and it was tested rather than assumed:**

```
sha256(strip(system_neutral.md) + "\n") = a567f4d3233c7f212a671d99b4d9151ec555982429369a7878e826438d3e740d
recorded f_phase1_k3 N system_sha256    = 56fb7f58cb42dd9bc10e86154634a2d4852aac505fdd79e70eaffc2582bb555a
```

About thirty variants were tried — raw file bytes versus stripped, with and
without a trailing newline, pad target `max(len_a, len_b)` versus `len_a`
versus `len_b`, with and without the dot-fill. None reproduces the recorded
hash. **The 2026-07-27 N prompt is not reconstructible from anything committed
today**, so the N construction changed by more than the pad alone: the pad plus
at least one further difference, in the N branch or in `system_neutral.md`
itself.

What *is* provable without any reconstruction is that Phase 1's N cell was not
length-matched. `f_phase1_k3_20260727` and `f_phase2_med30_20260727` share two
stimulus items and provably identical user prompts (same `user_sha256`), so a
`prompt_tokens` difference isolates the system prompt:

| cell | item | Phase 1 | med30 | delta |
| --- | --- | ---: | ---: | ---: |
| M | `item_01_vectordb_d0_main` | 914.0 | 914.0 | +0.0 |
| M | `item_02_sensor_d0_main` | 904.0 | 904.0 | +0.0 |
| P | `item_01_vectordb_d0_main` | 913.0 | 913.0 | +0.0 |
| P | `item_02_sensor_d0_main` | 903.0 | 903.0 | +0.0 |
| N | `item_01_vectordb_d0_main` | 802.0 | 900.0 | **−98.0** |
| N | `item_02_sensor_d0_main` | 792.0 | 891.0 | **−99.0** |

P and M are bit-identical across the two runs; only N moved, and only downward.
Within Phase 1, N averages 797.0 tokens against P 908.0 and M 909.0 — not
length-matched. Within med30, N averages 895.5 against 908.0 and 909.0 —
length-matched.

Blast radius is narrow and was checked at source: `s_N` enters only `beta`
(`compose.py:104`) and the baseline gate; `kappa` is computed from PM/MP over
P − M (`compose.py:102-103`) and never reads it. Every P/M/PM/MP cell in every
run behind a published composition number rebuilds bit-exactly.

---

## 4. What was imported

46 files, 18,038,659 bytes, every destination verified to hash-match its source
after copying. Names are unchanged: the frozen artifacts and their receipts use
the existing names, and `analysis/wujur/nomenclature.md` flags 38 identifiers as
prose-only renames for exactly this reason.

| destination | bytes | rows | sha256 |
| --- | ---: | ---: | --- |
| `model_organism/runs/v018_c0c1c2da_cn_s3/transcripts.jsonl` | 3923296 | 210 | `7a946aeaf8a3d823061ffcb6b4c533c91a4399306d784c45b43e26aa790fa187` |
| `model_organism/runs/v018_c0c1c2da_cn_s3/meta.json` | 2032 | - | `a9b02e809f70bfccc6021651f37a0b3fba4cce267bc521e5eab5d95d9f082778` |
| `model_organism/runs/v018_c0c1c2da_cn_s3/prompt_used.md` | 1874 | - | `1a12fab81c9116360b8da6228eb4697889837ddfbb43c6f0799a499c2fc69762` |
| `model_organism/runs/v018_c0c1c2da_cn_s3/judge_gpt56luna/judged.jsonl` | 4081828 | 210 | `e5e0c8e73880ba71d07f874b60313017669ad8331c1186c4bb592baa4022b8c7` |
| `model_organism/runs/v018_c0c1c2da_cn_s3/judge_gpt56luna/metrics.json` | 21242 | - | `c2f909a8332a7bf5421b0dd6403d671a4370978f0268d509d319446847995f3a` |
| `model_organism/runs/v018_c0c1c2da_cn_s3/judge_gpt56luna/report_snippet.md` | 969 | - | `55b4bbeaedb74f8709408775297d1b2fa24e5e77afa7d3b1917194a17226f11a` |
| `model_organism/runs/v018_test_c0c1c2da_s3/transcripts.jsonl` | 1297015 | 72 | `790bf5ee9448a31feb6c2c0de086f8c68f4dfcf071743d05507699d00aec64a0` |
| `model_organism/runs/v018_test_c0c1c2da_s3/meta.json` | 1452 | - | `d8be698488f23029d529d05b113d8a99c0352cf32bf5b5dee0e678e1e141d6d7` |
| `model_organism/runs/v018_test_c0c1c2da_s3/prompt_used.md` | 1874 | - | `1a12fab81c9116360b8da6228eb4697889837ddfbb43c6f0799a499c2fc69762` |
| `model_organism/runs/v018_test_c0c1c2da_s3/judge_gpt56luna/judged.jsonl` | 1363363 | 72 | `cec833a4b5887a0d31eda1140715f44ce81426aa7b43e85f4406c6a77ae5faa6` |
| `model_organism/runs/v018_test_c0c1c2da_s3/judge_gpt56luna/metrics.json` | 9137 | - | `117df3be53b96b915063ef64506fe8c04af69cf427aedbcfe6034492dfc38c8a` |
| `model_organism/runs/v018_test_c0c1c2da_s3/judge_gpt56luna/report_snippet.md` | 535 | - | `85d2793a5eaa4c2735bae614903748310ddea1547071ba01af9e539fa0ff199c` |
| `model_organism/runs/v018_test_c0c1c2da_s3/score_det/metrics.json` | 10765 | - | `7bd1b80b924c142425a1f73f348835f523df04a36d5ab5aa7af292030422e959` |
| `model_organism/runs/v018_test_c0c1c2da_s3/score_det/report_snippet.md` | 1185 | - | `2db600f47861c0a63a1aa1d5914f7a1400707f7500a3c8c0a7de09dd189e2c66` |
| `model_organism/runs/v018_c1c2da_s3/transcripts.jsonl` | 2378613 | 126 | `11dea19891c7f15693fce31586423711135224dab424fe3addcaf4de6a8e044d` |
| `model_organism/runs/v018_c1c2da_s3/meta.json` | 1695 | - | `a67986a68a2769e958b18c050e1133cf6c04ce79ff7543db927eade4a88c4a45` |
| `model_organism/runs/v018_c1c2da_s3/prompt_used.md` | 1874 | - | `1a12fab81c9116360b8da6228eb4697889837ddfbb43c6f0799a499c2fc69762` |
| `model_organism/runs/v018_c1c2da_s3/judge_gpt56luna/judged.jsonl` | 2532898 | 126 | `666dba3c2d6a95a919e1a0b3e85c1b277901380e1128200df1e1a6301705bf41` |
| `model_organism/runs/v018_c1c2da_s3/judge_gpt56luna/metrics.json` | 5514 | - | `0cbd469906fae7f0798788df35cda09e3f6bdba871fa02907d32e10e0c1d50f2` |
| `model_organism/runs/v018_c1c2da_s3/judge_gpt56luna/report_snippet.md` | 621 | - | `dc821d167f11116d4fbf18482e6c1f5f2b29cfd39a48ded33aec9eccd50f731a` |
| `model_organism/runs/v018_c1c2da_s3/score_det/metrics.json` | 6859 | - | `bc5ce8d33b7bf0d012ba9c5bdde2812696fd5d1d77b3bccfd58a85f9b0e94633` |
| `model_organism/runs/v018_c1c2da_s3/score_det/report_snippet.md` | 1121 | - | `4b27199d38e148d7c2123057e218105253ea8247a6dccab884ce1f5ac7bad406` |
| `model_organism/composition/runs/f_phase1_k3_20260727/generations.jsonl` | 564148 | 60 | `71b67b4e0041d0bf357bd2c8639dd0060c79e67f17d81a9a4627c6e41ea2a11e` |
| `model_organism/composition/runs/f_phase1_k3_20260727/run_meta.json` | 568 | - | `4db7e076f7e3b2cecd54c24aace9af7a29796371e2069f804c32fa9d8d5c1687` |
| `model_organism/composition/runs/f_phase2_med30_20260727/generations.jsonl` | 850154 | 90 | `4449155909d15dfac2fa54b31c940d5f74f9b4e3f97b271b27e541c85a59307f` |
| `model_organism/composition/runs/f_phase2_med30_20260727/run_meta.json` | 827 | - | `b5ab804ae80a2dee6a018842043dc54533c1ade62e06b0a1c407c11d546eba8c` |
| `model_organism/composition/runs/f_phase2_tiny9_live_20260727/generations.jsonl` | 85441 | 9 | `9abdbe6468be846e07fc18f971d00151bfcff7bef60925397e2205a385396389` |
| `model_organism/composition/runs/f_phase2_tiny9_live_20260727/run_meta.json` | 593 | - | `687078b148365e5f115375b229a7b2866f1a5e915698598e919598ad3d8eae9f` |
| `model_organism/composition/runs/f_privilege_tiny8_20260727/generations.jsonl` | 231601 | 24 | `4332c6aa7311497e3cafb016f3d399bc6ba693cba621dfe1db75b3936a53b8e0` |
| `model_organism/composition/runs/f_privilege_tiny8_20260727/run_meta.json` | 592 | - | `89094ab81e32114ae077c970b537784914b444775a0be92f5392e3c2e2dea71f` |
| `model_organism/composition/runs/f_small20_20260727/generations.jsonl` | 185424 | 20 | `76e391d74e3eb829aaf8e380934ed8cb1c9df06b38a37755b896ce118b043a81` |
| `model_organism/composition/runs/f_small20_20260727/run_meta.json` | 566 | - | `453e38374decd343ff5d7f2df35e4c0603635079038f770a78a2b35d6121ee24` |
| `model_organism/composition/runs/f_tiny10_20260727/generations.jsonl` | 91372 | 10 | `452c42a092ff015086e516ec21853f547a5b208ceb3c02375509a1eed6d266ad` |
| `model_organism/composition/runs/f_tiny10_20260727/run_meta.json` | 505 | - | `24a87ae57db1bb0c809deca8478a73f93331463d4d6ba1efa06f7882d60697b2` |
| `model_organism/composition/runs/f_tiny10_v18_20260727/generations.jsonl` | 99513 | 10 | `d19485421050a37e722caba8073141bc0237a01b27707e2c12bdc474718c7fd6` |
| `model_organism/composition/runs/f_tiny10_v18_20260727/run_meta.json` | 509 | - | `c7aad5bb6dee2174b8dc4987f5d81ce1c5a644c8a4e6b7889ee3a9d77cb3d341` |
| `model_organism/composition/runs/f_tiny10_v18s_20260727/generations.jsonl` | 92358 | 10 | `015e407b2b6b06e4b0945e234ce88e8711277b418e93b9f03fc05fdd96447526` |
| `model_organism/composition/runs/f_tiny10_v18s_20260727/run_meta.json` | 510 | - | `500531d25ae6b15cad0a7f63b37af663cb7b27be705090ade29f814567068830` |
| `model_organism/composition/runs/f_tiny10_v18s_twinfix_20260727/generations.jsonl` | 96977 | 10 | `078ed44a256ac883959dc9113937613fcb5f31b8521f4642d0c33f259533d403` |
| `model_organism/composition/runs/f_tiny10_v18s_twinfix_20260727/run_meta.json` | 517 | - | `5b9576b126d90c8ef59583112905aba85f30b17778ff4ff146d1c6fd5ca862f2` |
| `model_organism/composition/recovery_eval/runs/f9_live_20260727/generations.jsonl` | 50283 | 36 | `12b73ce44f73361804801af63e1d91a14decdfe91b176ece4e54384b812b5c85` |
| `model_organism/composition/recovery_eval/runs/f9_live_20260727/ground_truth.jsonl` | 5544 | 36 | `d1a722da1d46a05e142b89deeeb6069b886d9b853506f0624194b6b6144159ea` |
| `model_organism/composition/recovery_eval/runs/f9_live_20260727/judged.jsonl` | 8552 | 36 | `e6aa5c1bd6c0c196addab0e2ebf25fec17fa742ad153ee8ee39703f62bade41a` |
| `model_organism/composition/recovery_eval/runs/f9_live_20260727/redacted_for_judge.jsonl` | 25877 | 36 | `8860395013127d9714822566bf06c70cb822eb6c50762063e1f021824fce6a6a` |
| `model_organism/composition/recovery_eval/runs/f9_live_20260727/redaction_privacy_audit.json` | 141 | - | `9d8203e29ca5d4e47d66c83cdbef88f490f9fec621628c102d0bb8fc6e83c4c9` |
| `model_organism/composition/recovery_eval/runs/f9_live_20260727/run_meta.json` | 325 | - | `4718bc6c49f56327f7a02b4bda1ea3a399df49b5550596d8f14bf0b822f8afb9` |

`judge_gpt56luna/` was not in the original brief. It is included because it is
the only source of the judge labels behind `disclosure_rate` and
`concealment_given_activated`, and because it carries 128 unused `cot_leak`
labels that StratifyV2 owns analysing.

### 4.1 Deliberately not imported, with evidence

Dropping a file is only defensible if it adds nothing, so each exclusion was
tested rather than asserted. Every `.bak` was compared to the final
`transcripts.jsonl` on the `(scenario_id, condition, sample)` key.

| source (relative to the mirror) | bytes | rows | sha256 | why it adds nothing |
| --- | ---: | ---: | --- | --- |
| `runs/v018_c0c1c2da_cn_s3/transcripts.jsonl.bak_before_dedupe` | 3936823 | 216 | `01cd90dc346f02513e5c4d2cbf5e125ba78842d98bf9bb5a81dd20a31d43e35c` | 210 unique keys, 6 duplicated, 6 rows carry an `error` field; 0 keys the final file lacks; all 210 shared keys agree with final on content and score |
| `runs/v018_c0c1c2da_cn_s3/transcripts.jsonl.bak_before_retry_errors` | 3832404 | 210 | `485157fad61e9979c6e717e2220a6f5ce1483261d7630ecce12bdb3f8c3a8832` | same key set as final, 6 rows carry an `error` field, 204/210 already agree; the 6 that differ are the errored rows the retry replaced |
| `runs/v018_c0c1c2da_cn_s3/transcripts.jsonl.bak_before_resume_workers7` | 2623878 | 139 | `0095f7ce9cb8165b2a8a75b6254495088a9120a1164c39203c5c0e3b6adf1f3e` | strict prefix: 139 keys, all present in final, 139/139 agree, 0 keys final lacks |
| `armF_composition/runs/f_phase1_k3_dry` | 43313 | 60 | `17759ebde2b88ddbd603b499fe76088a92c7feed5add531589876791e3382451` | `run_meta.dry_run = true`, no committed metrics |
| `armF_composition/runs/f_phase2_tiny9_20260727` | 7109 | 9 | `b7743bccb7f1a153c73b969d2f6286f4aa67b3d8b398643124733dfbb4573861` | `run_meta.dry_run = true`, no committed metrics |
| `armF_composition/runs/f_tiny10_dry` | 7530 | 10 | `c196932dbbdfb5f0f09d59cfee08ad78c245c17fee21c2be3e3fffe15d93af82` | `run_meta.dry_run = true`, no committed metrics |
| `armF_composition/recovery_eval/runs/f9_dry_20260727` | 30513 | 36 | `d23c708d5a052f1988a75fe9b31ff859c8ba9359d6675a30cc219dcd2e118344` | dry run, no committed metrics |

The final `transcripts.jsonl` carries 0 rows with an `error` field and 0 rows
failing `score.parse_ok`. The three `.bak` files are therefore the visible
repair history of one run, fully superseded by the file that was imported.

To import them anyway, add their names to `V018_IMPORT_FILES` in
`verify_restored.py` and re-run with `--import`.

---

## 5. `f_privilege_k3_20260727`: definitive answer

**The k=3 privilege run's raw rows exist. They are the 24 rows in
`f_privilege_tiny8_20260727/generations.jsonl`, now imported at
`model_organism/composition/runs/f_privilege_tiny8_20260727/generations.jsonl`.
Nothing is lost.**

No directory named `f_privilege_k3_20260727` exists anywhere. An exhaustive
literal-string search over the whole Nextcloud mirror and the whole repository
returns 10 hits, all of them prose or the metrics file itself, and none of them
raw rows. The archive
`/home/barry/Downloads/Model-Loyalties-Investigation-main(1).zip` (2196 entries)
contains **zero** entries ending in `generations.jsonl` and only one entry-name
hit, `armF_composition/metrics/f_privilege_k3_20260727_privilege.json`, plus two
prose hits in `ATTEMPT_LOG.md` and `metrics/RESULT.md`.

The directory name is a stale provisional label. `run_meta.json` in the tiny8
directory records `k: 3`, `privilege: true`, `n_jobs_total: 24`,
`n_jobs_skipped_done: 8` — the 8-job pilot was resumed to a full k=3, 24-row run.

A filename is not evidence, so this was settled by re-running the scorer.
`score_privilege.score_privilege()` on those 24 rows, with
`ref_run_dir = f_phase1_k3_20260727`, `n_resamples = 2000`, `seed = 20260727`,
reproduces the committed `f_privilege_k3_20260727_privilege.json` with **exactly
one differing leaf**:

```
.reference_run   computed = <absolute path to the reference run dir>
                 stored   = "composition/runs/f_phase1_k3_20260727"
```

That field is the `--ref-run-dir` CLI argument echoed back at
`score_privilege.py:185`. It is a path string, not data, and varies with where
the reference run is read from. **It is not a reproduction failure.** Everything
else matches bit-for-bit, including the seeded 2000-resample bootstrap:
`kappa = -1.0346820809248556`, `beta = 0.005833333333333329`,
`priv_PM = -0.44166666666666665`, `priv_MP = 0.4533333333333333`.

Confirmed independently by TitrationClose via a different route.

### 5.1 A second instance of the same pattern, and a naming trap

The same check found a second case the brief did not mention.
`f_phase2_k3_20260727_dose.json` carries `$.run_id = "f_phase2_med30_20260727"`
and `$.n_records = 90`. Running `score_dose.score_dose()` on the recovered
90-row `f_phase2_med30_20260727/generations.jsonl` at the same seed reproduces
it with **zero** differing leaves.

This creates a live hazard for citations:

| on-disk stem | as a DIRECTORY | as a METRICS FILE |
| --- | --- | --- |
| `f_privilege_tiny8_20260727` | k=3, 24 rows — **authoritative raw data** | `..._privilege.json`, k=1, 8 rows — **superseded** |
| `f_phase2_med30_20260727` | k=3, 90 rows — **authoritative raw data** | `..._dose.json`, k=1, 30 rows — **superseded** |

Two committed metric files are stale first-pass artefacts and must not be cited:
`f_privilege_tiny8_20260727_privilege.json` (`n_records` 8) and
`f_phase2_med30_20260727_dose.json` (`n_records` 30). The authoritative numbers
live in the two files named `_k3_`, whose names do not match their own `run_id`.

Any citation keyed on the filename stem picks the wrong dataset. The on-disk
names cannot change — the frozen artifacts and receipts use them — so this needs
an entry in `nomenclature_migration.json` as an artifact-frozen, prose-only
rename with an explicit warning. Flagged to all agents.

---

## 6. Stopping the recurrence

`runs/` was ignored repo-wide at `.gitignore:19` and again at
`model_organism/composition/.gitignore:1`. That is why the data vanished. The
fix is the "re-include the directory, immediately re-exclude its contents, then
name the exceptions" idiom, applied only to the restored paths. `runs/` is
**not** un-ignored wholesale.

| file | lines | effect |
| --- | --- | --- |
| `.gitignore` | 20–28 | `!model_organism/runs/`, `model_organism/runs/*`, `!model_organism/runs/v018_c0c1c2da_cn_s3/` |
| `model_organism/composition/.gitignore` | 6–21 | `!runs/`, `runs/*`, then nine `!runs/<run_id>/` lines |
| `model_organism/composition/recovery_eval/.gitignore` | 6–16 | `!runs/`, `runs/*`, `!runs/f9_live_20260727/`, `!runs/f9_live_20260727/*` |

The trailing `!runs/f9_live_20260727/*` is required because that file's `*.jsonl`
rule at line 3 is unanchored and would otherwise still drop
`generations.jsonl`, `ground_truth.jsonl`, `judged.jsonl` and
`redacted_for_judge.jsonl`.

### 6.1 Verified with git, not by reasoning

Two read-only instruments, neither of which writes the index, objects, refs or
the worktree. Permission for these specifically was granted by Main.

`git check-ignore -v -n --no-index` names the deciding `<file>:<line>:<pattern>`
for each path. This matters because **later-pattern-wins is per-file, so a
negation written into the wrong `.gitignore` is silently inert.** The attribution
shows which file actually decides each restored path:

| restored path | decided by |
| --- | --- |
| `model_organism/runs/` | `.gitignore:26` `!model_organism/runs/` |
| `model_organism/runs/v018_c0c1c2da_cn_s3/` | `.gitignore:28` `!model_organism/runs/v018_c0c1c2da_cn_s3/` |
| `model_organism/runs/v018_c0c1c2da_cn_s3/judge_gpt56luna/` | no matching rule |
| `model_organism/composition/runs/` | `model_organism/composition/.gitignore:11` `!runs/` |
| `model_organism/composition/runs/<9 run ids>/` | `model_organism/composition/.gitignore:13`–`:21` |
| `model_organism/composition/recovery_eval/runs/` | `model_organism/composition/recovery_eval/.gitignore:13` `!runs/` |
| `model_organism/composition/recovery_eval/runs/f9_live_20260727/` | `.../recovery_eval/.gitignore:15`, files by `:16` |

So the root `.gitignore` governs the confirm grid, but the **child**
`.gitignore` files govern every composition path. A negation for a composition
run placed in the root file would have done nothing.

The negatives were proved, not assumed. Nine paths that must stay ignored, each
with the rule that keeps them out:

| path | still ignored by |
| --- | --- |
| `model_organism/runs/v018_c1c2da_s3` | `.gitignore:27` `model_organism/runs/*` |
| `model_organism/runs/v018_test_c0c1c2da_s3` | `.gitignore:27` `model_organism/runs/*` |
| `model_organism/runs/v999_hypothetical_dev/transcripts.jsonl` | `.gitignore:27` `model_organism/runs/*` |
| `model_organism/composition/runs/f_phase1_k3_dry/generations.jsonl` | `model_organism/composition/.gitignore:12` `runs/*` |
| `model_organism/composition/runs/f_phase2_tiny9_20260727/generations.jsonl` | `model_organism/composition/.gitignore:12` `runs/*` |
| `model_organism/composition/runs/f_tiny10_dry/generations.jsonl` | `model_organism/composition/.gitignore:12` `runs/*` |
| `model_organism/composition/recovery_eval/runs/f9_dry_20260727/generations.jsonl` | `.../recovery_eval/.gitignore:14` `runs/*` |
| `auditing/runs/track1_v018` | `auditing/.gitignore:4` `runs/` |
| `auditing/runs/v18` | `auditing/.gitignore:4` `runs/` |

The hypothetical `v999_hypothetical_dev` path is included on purpose: it proves
a dev run dropped in later still stays out.

`git ls-files --others --exclude-standard` then answers what `git add -A` would
actually take, which accounts for directory-descent pruning that `check-ignore`
alone does not model. All 30 restored paths are held by git, and **0** untracked
non-restored files under any `runs/` prefix are admitted by the negations.

One honest caveat, reported rather than failed: 556 files under `runs/`
directories were already tracked by earlier commits — 552 under `auditing/runs/`
and 4 under `model_organism/runs/.../score_gate_v2/`. A `.gitignore` rule has no
effect on an already-tracked path, so these are outside this change's blast
radius. They were tracked before the negations and are tracked after.

### 6.2 Reverting

- `.gitignore`: delete lines 20–28.
- `model_organism/composition/.gitignore`: delete lines 5–21 (the blank line and everything after it).
- `model_organism/composition/recovery_eval/.gitignore`: delete lines 5–16.
- Imported data: `rm -rf model_organism/runs/v018_c0c1c2da_cn_s3 model_organism/composition/runs model_organism/composition/recovery_eval/runs` (only if they have not yet been committed; if they have, the parent must revert the commit).
- Generated files: `rm analysis/wujur/restored_data.md analysis/wujur/restored_manifest.json analysis/wujur/verify_restored.py`.

The Nextcloud mirror is untouched and remains a complete second copy.

---

## 7. Reproducibility of this document

`verify_restored.py` holds no state between runs, uses no wall-clock timestamps
and no RNG beyond the two fixed seeds the repository's own scorers require. Two
consecutive `--import` runs produce byte-identical stdout and a byte-identical
`restored_manifest.json`; this was checked with `cmp`. Import is idempotent: it
copies only when the destination hash differs, and reports the post-condition
rather than the action, so the output does not depend on run order.

The script's own outputs are excluded from the missing-run string search,
because they mention every run id and would otherwise make the hit count depend
on whether a previous run had written them. That feedback loop was a real
observed nondeterminism, found by the two-run `cmp` check, and fixed.

All analysis was run from this script file rather than a shared notebook kernel,
after StratifyV2 observed that the shared Python eval kernel silently rebinds
short global names across concurrently running agents.

---

## What this does NOT establish

- **Nothing here validates the v018 numbers scientifically.** It establishes
  that the recovered bytes are the same bytes the committed metrics were
  computed from, and that the repository's scorer applied to those bytes
  reproduces those metrics. If the scorer or the experimental design is wrong,
  every check here still passes.
- **It does not verify `system_sha256` against anything.** No metadata record
  exists for it, by construction. The 57-value distribution is consistent with
  per-scenario assembly, but consistency is not verification. Only
  `prompt_sha256` was cross-checked end to end.
- **It does not prove the recovered `f_privilege_tiny8_20260727` rows were
  produced by an invocation whose run directory was ever called
  `f_privilege_k3_20260727`.** It proves those 24 rows reproduce the committed
  k3 metric exactly under the repository's scorer at the recorded seed. That is
  a statement about the data, not about the history of the filesystem. Whether
  `--out` was passed explicitly or a directory was renamed and deleted cannot be
  recovered from what is on disk.
- **It does not establish that the superseded metric files were never cited.**
  It establishes only that they are stale. Whether any prose, table or `.tex`
  currently cites `f_privilege_tiny8_20260727_privilege.json` or
  `f_phase2_med30_20260727_dose.json` is unaudited here.
- **It says nothing about the two dose runs' bootstrap blocks beyond the two
  reproduced files.** Only `f_phase2_k3_20260727_dose.json` was reproduced in
  full; for `f_phase2_tiny9_live_20260727` only row count and the deterministic
  dose curves were checked, not its bootstrap.
- **It does not confirm the judged CoT-leak labels are usable.** This document
  establishes only that 128 rows carry `disclosure` labels and that labelling
  tracks activation exactly. The trace-leak rate itself is StratifyV2's to
  compute and was deliberately not computed here.
- **It does not establish anything about the `.bak` files' value as forensic
  evidence.** It establishes that they contribute no row the final file lacks.
  If someone later wants to audit the dedupe decision itself, they need the
  Nextcloud copies, whose hashes are recorded above.
- **It does not cover the 7-week endpoint gap.** All reproductions here are
  re-scorings of stored rows. No generation was run, and nothing here speaks to
  whether the endpoint would produce the same rows today.
- **The `.gitignore` verdicts describe the current working tree only.** A new
  `.gitignore` added in a subdirectory later, or a `git add -f`, can change the
  outcome without touching any of the three files edited here.
