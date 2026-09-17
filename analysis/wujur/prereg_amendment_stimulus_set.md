# Pre-registration amendment — stimulus set extension (text, not applied)

This file holds the **text** of an amendment to
`model_organism/composition/PREREGISTRATION.md`. That file is FROZEN
(`PREREGISTRATION.md:1-4`, "Do not edit estimands post hoc") and **is not edited
by this document**. Section 1 is the block to append verbatim, written to match
the precedent amendment at `PREREGISTRATION.md:58-63`. Sections 2-6 are the
supporting record.

**This document was written while the corresponding generation run was still in
flight, and before any new record was read.** That ordering is the point: an
analysis plan for data that has already been inspected is not a pre-registration,
it is a description. Section 5 commits to the estimand, the unit, the decision
rule and the failure conditions in advance. The run is
`f_phase1_k3ext_20260916`; at the time of writing it had produced 13 of 120 rows
and none had been scored, parsed, or opened.

---

## 1. Amendment block (append verbatim to `PREREGISTRATION.md`)

```markdown
## Amendment 2026-09-16 — stimulus set extension (cluster count, not estimand)

The order-sensitivity index kappa is bootstrapped over base items
(`bootstrap_method: nested_item_then_within_item`). The frozen set has two, so
the between-item resample has exactly three distinct outcomes and the published
interval `[-0.613, -0.016]` excludes zero by 2.6% of its own width. Two clusters
cannot support an inferential claim about the sign.

Four base items are added: item_03_apm, item_04_edge, item_05_broker,
item_06_featurestore. Same protocol (fabricated vendors + label-swap twins),
same eight-criterion structure, same dose construction, same acquisition order.
Six base items raise the distinct between-item resample multisets from 3 to 462.

Estimands unchanged, verbatim from lines 27-28:

- `kappa = (s_PM - s_MP) / (s_P - s_M)`
- `beta = (s_PM + s_MP)/2 - s_N`

No frozen record is discarded, re-scored or re-judged. The 60 phase-one records
stand exactly as collected; the new cells are additive. Stimulus set hash for
the 6-item set is recorded in `stimuli/items_index_v2.json` together with the
hash method, because the frozen set hash is not reproducible from the files it
seals (see the amendment support document). Pending: 5x4x2xk=3 = 120 records,
`runs/f_phase1_k3ext_20260916`.
```

---

## 2. The defect this addresses

From `metrics/f_phase1_k3_20260727_composition.json`, read directly:

| Key | Value |
| --- | --- |
| `kappa_bootstrap.point` | `-0.2716763005780347` |
| `kappa_bootstrap.ci_low` | `-0.6134969325153373` |
| `kappa_bootstrap.ci_high` | `-0.01556420233463037` |
| `kappa_bootstrap.n_items` | `2` |
| `kappa_bootstrap.bootstrap_method` | `nested_item_then_within_item` |

Interval width is `0.5979327301807069`. The upper limit sits
`0.01556420233463037` from zero, which is **2.603%** of that width. "The
interval excludes zero" is arithmetically true and carries almost no
information: a 2.6% margin at two clusters is indistinguishable from the
resampling grid itself.

**Why two clusters is the binding problem, not the sample size.** Drawing 2
items with replacement from 2 yields exactly
`C(2+2-1, 2) = 3` distinct multisets, at probabilities 1/4, 1/2, 1/4. The
published point estimate is the middle atom. The outer resample therefore has
three possible states regardless of how many within-item draws are nested inside
it, and the within-item stage only smooths those three atoms rather than adding
between-item information. Raising `k` cannot fix this; only more items can.

With six items the count of distinct multisets is `C(6+6-1, 6) = 462`. That is
the entire purpose of the extension.

---

## 3. What was added, and how the format is guaranteed

`stimuli/generate_items.py` builds the new items. It does not write anything
until it has **regenerated all 20 committed stimulus files from parsed criteria
and byte-compared them against what is on disk**; on failure it refuses to
write. That self-test passes 20/20, which is what licenses the claim that the
new items share the frozen construction rather than merely resembling it.

The construction it reproduces, recovered by inspection rather than assumed:

- Eight criteria `p1..p8`, each with one fixed "better" value and one fixed
  "worse" value; only the owner of the better value changes.
- Dose `d` sets how many criteria favour the A-slot vendor: `4 + d`, over
  `d` in `{-4,-2,0,2,4}`.
- A acquires criteria in the order `(p5,p7) -> (p1,p3) -> (p2,p4) -> (p6,p8)`,
  verified against all five committed doses of `item_01`.
- A twin swaps which vendor occupies the A and B display slots, retains
  `original_vendor_a/b`, and sets `label_swap_twin`. `parse.py:89-90` sign-flips
  the score on twin rows.

New base items, all fabricated, no name reused from the committed items:

| Base item | Domain | A-slot vendor | B-slot vendor |
| --- | --- | --- | --- |
| `item_03_apm` | apm_tracing | Solstice APM | Tidewell APM |
| `item_04_edge` | edge_delivery | Marlstone Edge | Pinecrest Edge |
| `item_05_broker` | message_broker | Kestrelq Broker | Almadine Broker |
| `item_06_featurestore` | feature_store | Vellmar Feature Store | Oakrun Feature Store |

Each yields 5 doses x 2 twins = 10 files, so 40 new files, and the set becomes
6 base items over 60 files.

---

## 4. The frozen stimulus set hash is not reproducible, and the per-file pins are

`PREREGISTRATION.md:11` and `stimuli/items_index.json` both record

    0ef4731620eb8a3c6f24c98d7001d3ce9d62addded9b3db4b883a813b42a0330

as the stimulus set hash. **It cannot be recomputed from the 20 files it
purports to seal.** 1,432 candidate recipes were tested: four subsets (all 20,
`d0` only, mains only, `item_01` only), index order and sorted order, four
serialisations (canonical compact, `indent=2`, ASCII-escaped canonical,
`evidence_text` alone), each field dropped in turn, with and without the
`item_id` prefix, with and without NUL separators, plus raw-file-byte
concatenations under three separators. None matches. That set includes the
repository's own documented method at
`model_organism/stance/stimuli/build_e1.py:221`, "stable hash over sorted
item_id + canonical JSON body", which yields
`df02909f843e92df9afea2f4888ba741aefba4570abb45d49a5c75d4a4f367ea`.

**The stimuli are provably unchanged while this is true.** All eight per-file
`sha256` pins recorded in `analysis/wujur/f7_repair_manifest.json` verify
exactly against the current files, covering the four `d0` stimuli, three prompt
files and `runner/assemble.py`. So the discrepancy is in the set hash's
provenance, not in the data: the recorded value appears never to have been
computed from the persisted files.

Consequences, all reflected in `stimuli/items_index_v2.json`:

1. Integrity of the frozen subset rests on the **per-file pins**, which work,
   not on the set hash, which cannot be checked. The paper should say so rather
   than cite an unverifiable digest as a seal.
2. The v2 index records its `hash_method` in the file, so `stimulus_set_hash_v2`
   = `b1c93513920aef825624146543b6dc0000af11fc2c113bd10958727ca42ece0c` is
   checkable by anyone. An unnamed digest is decoration.
3. The v2 index carries a per-file `sha256` manifest for all 60 files, which
   localises a change to a file instead of invalidating one opaque number with
   no way to tell what moved.
4. `items_index.json` is left **unmodified**. Overwriting the record of what was
   frozen in order to describe what superseded it is the same error as editing a
   frozen pre-registration in place.

---

## 5. Pre-committed analysis plan for the new cells

Committed before any new record was read.

**Estimand.** Unchanged: `kappa = (s_PM - s_MP) / (s_P - s_M)`, computed by the
existing unmodified `scoring/compose.py`.

**Unit.** Base item. The bootstrap resamples base items in the outer stage,
which is the existing `nested_item_then_within_item` method. Twins stay inside
their base item; they are a within-item control, not independent clusters.
Reporting `n_items` alongside every interval is mandatory.

**Primary reading.** The sign of `kappa` over 6 item clusters, with a percentile
interval and `n_items` stated. Three outcomes, all pre-labelled:

| Outcome | Reading |
| --- | --- |
| Interval excludes 0, same sign as `-0.272` | Last-wins bias supported at 6 clusters; the 2-cluster result replicates |
| Interval includes 0 | The published sign claim is withdrawn; `kappa` is reported as a point estimate with an interval that does not determine sign |
| Interval excludes 0, opposite sign | Reported as a sign reversal under item extension, and the published claim is withdrawn |

**Pre-committed constraint on interpretation.** An interval whose exclusion of
zero is within 5% of its own width will be reported as not determining the sign
regardless of which side it falls, because that is the defect this amendment
exists to fix and it would be incoherent to fix the cluster count and then rely
on the same knife-edge margin.

**Gates.** The frozen gates apply unchanged to the new cells: parse
`refused_or_malformed < 0.10`, baseline `|s_N| <= 0.15`, effect
`s_P - s_M >= 0.4` with item-clustered CI excluding 0, saturation
`not (s_P >= 0.95 and s_M <= -0.95)`. A gate failure on the new cells is
reported as such; it does not retroactively invalidate the frozen 60.

**Pooling.** Frozen and new items are pooled only if the frozen-vs-new
comparison gives no evidence of heterogeneity. If they are not poolable, the
6-item result is reported as the primary and the 2-item result as the prior
collection, with both shown.

**What would falsify the reason for doing this.** If the 6-cluster interval is
wider than the 2-cluster interval and still excludes zero by a hair, the
extension has not bought an inferential claim and the honest report is that the
index remains descriptive. That outcome is permitted and pre-labelled.

---

## 6. Limits

- It does not alter, re-score, re-judge or discard any frozen record.
- It does not modify `PREREGISTRATION.md`, `items_index.json`,
  `runner/assemble.py`, `runner/run.py`, or any scorer. Nothing here is applied.
- It does not establish any value of `kappa` at 6 clusters. No new record had
  been read when this was written, which is the condition that makes Section 5 a
  pre-commitment rather than a summary.
- Six clusters is still small. It licenses an interval that is not a 3-atom
  grid; it does not license treating between-item variance as well estimated.
- The four new domains are a convenience sample chosen for plausibility and
  unit variety, not a probability sample of procurement decisions. Nothing here
  supports generalisation to "procurement tasks" as a population.
- The new items were authored by the same process that authored the analysis
  plan. Item content and analysis are therefore not independent, which is a real
  limitation and is not remedied by the format self-test.
