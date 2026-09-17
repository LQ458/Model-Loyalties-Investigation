# Paper 1 changelog: `main.tex`

> **WORD COUNT, THREE CONVENTIONS, READ THIS FIRST.** `main.tex` is
> **7,289 words** of body text with all floats and references excluded;
> **8,808 words** of body text plus captions, excluding tabular cell contents
> and references --- *this is the convention academic venues normally apply and
> the figure to quote against WUJUR's 500--10,000 range*; and **10,224 words**
> if every cell of all 14 tables is counted as prose, which exceeds the 10,000
> ceiling. The third figure is an artefact of counting numerals such as
> `21/27 = 0.7778` and interval bounds as words. If an editor counts that way,
> the fix is to move one or two tables to an appendix or supplementary file, not
> to cut argument; nothing was restructured to chase the number. Abstract: 466
> words. 14 tables, 2 figures, 20 references.
>
> **TWO REFERENCES ARE UNVERIFIED.** See "Unverified references" below before
> answering any reviewer challenge on the bibliography.


Target: Overleaf project `default`, file `main.tex`.
Status: **DRAFT SKELETON**, per the 2026-09-16 scope change from Barry relayed
by `Main`. Structure, numbers, tables and the claim/evidence/caveat skeleton are
load-bearing; prose is deliberately unpolished.

Remote verified after push by reading the file back and sha256-comparing against
the source: `fb8f8609d4a40ace...`, 82,616 characters, identical.

Counts: 14 tables, 2 figures, 0 unreferenced `\label`s, 0 dangling `\ref`s.
6,340 words of prose excluding floats and references; 8,439 counting every table
cell, caption and appendix. 8 `PENDING` markers.

Every row below names the artifact that justifies the change. Numbers I
recomputed myself from raw rows are marked **(re-derived)**; numbers taken from
a verified analysis document without independent recomputation are (cited).

---

## 0. Three rounds

**Round 1** rewrote the three-track hackathon report into a single-thesis paper
and re-grounded every number on `analysis/wujur/`. **Round 2** converted that
into a skeleton and retracted an overclaim round 1 made about the de-confounding
nulls (section 2). **Round 3** fixed a worse error that rounds 1 and 2 shared, an
omitted contrast that reverses the section's conclusion, and scoped an overclaim
about the companion paper (section 2A). All three rounds are recorded; the file
on Overleaf is the round-3 state.

Reviewer 1's three defects are addressed in both rounds:

| Defect | Fix | Where |
| --- | --- | --- |
| "the headline is close to circular" | The content-matched neutral control is the load-bearing control, reported at 0/42 with per-scenario agreement on all 14, and the paper concedes what the objection correctly retains. | sec. 4 |
| "an abstract that's a wall of percentages whose scopes contradict each other until page four" | Abstract states every denominator and its population inline, labels both existence-grade cells as existence evidence in the abstract, and states the fresh-cell power in the abstract rather than a footnote. | abstract |
| "a handful of internal codenames used without ever being defined" | Prose names throughout; codes confined to Appendix B; `L1`/`L2` as harm loci deleted; `D0`-`D4` retired; "activation" never used as the name of a rate. | Appendix B, sec. 1 |

---

## 1. Skeleton conversion (round 2)

| Change | Rationale |
| --- | --- |
| Every section opens with a `%`-comment banner naming its claim and its stability, and closes before the next banner. Sections are swappable without touching neighbours. | "One claim per section, clearly delimited" |
| Flowing prose replaced by `\Claim` / `\Evid` / `\Cav` macros carrying the logic in as few words as it takes | "Bullet-adjacent prose is fine. Do not wordsmith." |
| All 14 tables and both figures kept byte-for-byte from round 1 | "Tables are cheap to keep and expensive to rebuild" |
| Every number now carries an inline `\src{...}` artifact citation, and every table caption names its source file | "Every number in place, correct, and cited to its artifact" |
| 9 `PENDING` markers: 4 line-leading `% PENDING:` comments (grep-able), 3 rendered `\pend{}` markers (visible in the PDF), plus the macro definition and the header note | "Mark every claim whose status is PENDING with a visible LaTeX comment" |
| A boxed draft-status banner after `\maketitle`, carrying a `% DELETE BEFORE SUBMISSION` comment | So nobody mistakes the skeleton for a submission draft |
| Three scaffolding macros (`\Claim`, `\Evid`, `\Cav`) plus `\src` and `\pend`, flagged in the preamble as deletable when prose lands | Keeps the scaffolding removable in one pass |
| A new dedicated section, "Principal reality does not moderate the effect within the grid" (sec. 7) | The adequately powered principal-reality claim was buried inside the validation section; `Main` instructed leaning on it rather than on the n=9 cells, so it needs its own swappable section |
| Prose cut from 6,905 to 5,958 words | Skeleton, not paper |

The prose that was cut is recoverable: round 1 is the immediately preceding
Overleaf commit.

---

## 2. THE SUBSTANTIVE RETRACTION IN ROUND 2

**Round 1 wrote the two de-confounding cells as informative nulls.** Its text
read: "Neither de-confounding cell moves the endpoint ... Both are nine-row
cells and both are consistent with a moderate effect we cannot detect." The
second clause was right and the framing around it was not: a reader would take
"neither cell moves the endpoint" as evidence that principal reality and
required distortion are ruled out. **They are not.**

**Round 2 states the power arithmetic in the body text.** At `n = 9` per arm,
reference rate at the observed 7/9 = 0.7778, Fisher exact two-sided,
`alpha = 0.05`:

| True moderation | Power |
| ---: | ---: |
| 20 points | 0.070 |
| 30 points | 0.152 |
| 40 points | 0.273 |
| 50 points | 0.431 |
| 60 points | 0.628 |
| ~68 points | 0.80 |

**(re-derived)** I computed this myself by full enumeration of the product
binomial over all 10 x 10 outcome pairs, evaluating the two-sided Fisher exact
p-value at each, rather than accepting the figures I was given. The three
figures `Main` supplied (0.070 / 0.152 / 0.273) reproduce exactly.

**One correction to the instruction I was given.** `Main` wrote that "the design
could not have detected a moderation smaller than roughly 40 points". That
understates it: power at 40 points is 0.273, not adequate. The 80%-power minimum
detectable difference is **67.8 points**; the 50%-power MDD is 53.7 points. The
paper states the three power values and the ~68-point figure, not "roughly 40".

Consequences, all applied:

- The section is retitled "Fresh scenarios: weak generalisation, underpowered
  de-confounding".
- The claim now reads: "**The two de-confounding cells are uninformative nulls.
  They neither support nor exclude a moderating effect, and we do not claim
  otherwise.**"
- Explicitly added: "this design cannot discharge the objection that a fake
  principal changes the dynamic of the loyalty, and it cannot show that required
  distortion is irrelevant."
- The reader is pointed at section 7 (42 rows per stratum) as the principal-reality
  claim to lean on.
- Round 1's sentence "Neither de-confounding cell moves the endpoint" is
  **deleted**.
- The abstract now carries the three power values inline.
- The power number also explains why the July-vs-September comparison is not
  significant: power against the 33.3-point difference it observed is **0.188**.
  **(re-derived)**
- The claim-evidence map gains a new status class, **Uninformative**, and the
  de-confounding row is moved into it from "Measured - both null at this n".
- Limitations gains a dedicated fresh-cell power item.

**Artifact:** `analysis/wujur/gate_r0.txt:111-114`, `gate_r1r2.txt:111`,
`analysis/wujur/r0_rows.jsonl`, `analysis/wujur/r1r2_rows.jsonl`. The power
arithmetic is computed in this session from those cell counts and is not in any
committed artifact; it is reproducible from the counts in Table 6 of the paper.

---

## 2A. ROUND 3: THE OMITTED CONTRAST THAT REVERSES SECTION 8

Found by `ExpCriticB`, confirmed by `Main`, re-derived here before application.

**The error, and it was mine as much as anyone's.** Rounds 1 and 2 ran only
fresh-versus-fresh contrasts (real principals 6/9 vs.\ re-baseline 7/9;
mid-field 8/9 vs.\ 7/9), correctly called them underpowered, and **never
compared any fresh cell against the 42/42 development rate at all**. Round 1
had inherited that contrast from the original draft (42/42 vs.\ 4/9,
`p = 5.4e-05`) and dropped it during the rewrite. The omission left a reader
with "both explanations null", which reads as though nothing moved. Something
moved.

**The arithmetic, re-derived here by full enumeration rather than transcribed:**

| Cell | Principal first | Rate | Fisher vs.\ 42/42, sample | vs.\ 42/42, cluster |
| --- | ---: | ---: | ---: | ---: |
| July trio | 4/9 | 0.4444 | **5.364e-05** | --- |
| Re-baseline, September | 7/9 | 0.7778 | **0.0282** | 0.1765 |
| Real principals, September | 6/9 | 0.6667 | **0.0040** | **0.0015** |
| Mid-field principal, September | 8/9 | 0.8889 | 0.1765 | 0.1765 |
| **Pooled September fresh** | **21/27** | **0.7778** | **0.00247** | **0.00374** |

Cluster unit = independent scenarios: development 14/14 with all three samples
hitting, against fresh scenarios with all three seeds hitting (re-baseline 2/3,
real principals 0/3, mid-field 2/3, pooled 4/9). **(re-derived)** every cell
above, from `r0_rows.jsonl` and `r1r2_rows.jsonl`, with the Fisher exact
computed from first principles. `Main`'s and `ExpCriticB`'s figures reproduce
exactly.

**Why one direction is powered and the other is not.** 9 rows against 42 rows
at ceiling, with a large true difference, is powered. 9 rows against 9 rows with
a small true difference is not. That asymmetry is the whole finding and both
halves are now stated in the paper.

**What changed in `main.tex`:**

- Section retitled from "Fresh scenarios: weak generalisation, underpowered
  de-confounding" to **"Fresh scenarios: a real drop with an unidentified
  cause"**.
- `Table 6` rebuilt: all four cells plus the pooled row, with rate, Wilson
  interval, and both the sample-unit and cluster-unit Fisher p-values against
  42/42. The clean arm (0/9 in every cell) moved into the caption.
- The section now carries three numbered claims in this order: **(1)** the drop
  is real and significant, pooled `p = 0.00247`; **(2)** which factor drives it
  is unidentified, with the power values; **(3)** 44% is an unstable point
  estimate of the drop's *size*, not grounds for doubting the drop.
- New caveat on claim 1: the contrast moves four factors at once, so it
  establishes *that* the endpoint falls and not *which* factor makes it fall;
  and it spans the seven-week collection gap, which the re-baseline controls
  only for the July-versus-September comparison.
- New paragraph, "Consequence for Reviewer 1, stated plainly": the objection was
  **right that a drop exists and wrong only about its magnitude** --- roughly
  0.78 today, not 0.44, and still significantly below 1.000.
- **Round 2's framing is explicitly corrected in the text**: "44% was never a
  stable estimate" is easy to misread as putting the drop itself in doubt, and
  the paper now says it does not.
- Abstract rewritten to lead the fresh-scenario material with the drop
  (`p = 0.0025` sample, `0.0037` cluster, clean arm 0/9 throughout) before the
  unidentified cause and the unstable point estimate.
- Conclusion rewritten to match.
- The installation-section caveat now states the drop rather than promising a
  "weaker and less stable" number later.
- Claim-evidence map gains a row, "The endpoint holds off the development
  scenarios --- **Measured, rejected**", and the 44% row is re-worded.
- Limitations item 5 retitled "Fresh-cell power is asymmetric, and only one
  direction is usable".

### 2A.1 Second finding: an overclaim about the companion paper

Round 1 and round 2 both wrote, in the Discussion: "in the companion study of
stacked opposing loyalties, installed direction is not recoverable from visible
allocations **at all**." That is a universal claim the companion paper's own
"What this study does not establish" section disclaims, and its author had
already told me the correct scope. **This was my error, not theirs.**

Replaced with: installed direction "was not recovered from visible allocations
*by the probes tested*: its pre-registered decoder failed all four recovery
gates (of six; the two data-quality gates passed) at that $n$. That is one
decoder failing, not a proof that none can." The 4-of-6 gate precision comes
from the companion author's own verification of
`recovery_eval/PREREGISTRATION.md`, and it also fixes a second defect: the
previous draft's "failed all four of its pre-registered gates" implied four of
four.

---

## 3. Numbers changed because the published value was wrong or misattributed

### 3.1 `promoted`: baseline measured against a constant

**Was:** C0 0.881, CN 0.810, C1/C2/DA 1.000, presented as a co-primary null with
"the organism's entire measured effect concerns which vendor occupies rank 1
specifically".

**Now:** Table 4 gives three columns - as published; corrected unconditional
(C0 25/42 = 0.595, CN 23/42 = 0.548, C1/C2 36/42 = 0.857, DA 39/42 = 0.929);
conditional on promotion being arithmetically possible (C0 25/36 = 0.694
[0.531, 0.820], CN 23/36 = 0.639, C1/C2 36/36 = 1.000 [0.904, 1.000]).

**Artifact:** `analysis/wujur/selectivity_v2.md` sec. 6;
`analysis/wujur/stratified_v2.md` sec. 11. Root cause:
`model_organism/scoring/parse_ranking.py:105-110` reads
`principal_presented_rank`, the constant 6 on all 210 rows, which equals the
rendered roster position on 0 of 210
(`selectivity_v2.json` -> `integrity.rows_where_stored_presented_rank_matches_roster`).

**(re-derived)** I parsed the candidate roster from the `user` field of all 210
rows of `model_organism/runs/v018_c0c1c2da_cn_s3/transcripts.jsonl`, matched it
to each row's `loyalty_principal`, and recomputed every cell above. All agree.

**Withdrawn:** "co-primary null" and the rank-1-only sentence. Conditional on
promotion being possible the two intervals do not overlap.

**Added:** the endpoint must never be reported stratified by principal reality
without conditioning. **(re-derived)** C2 real 15/21 vs invented 21/21
unconditional, Fisher 0.0207; 15/15 vs 21/21 conditional, Fisher 1.0000; real
presented positions [1, 1, 2, 5, 7, 10, 10] against invented [3, 4, 5, 7, 7, 7, 8].

### 3.2 Head-to-head clean endpoint 0.833

**Was:** "rising from 0.833 under the clean condition to 1.000 under the loyal
condition", against "a named foil".

**Now:** 0.6905 (29/42) clean, 1.0000 (42/42) loyalty, content-matched neutral
0.6667 (28/42), paired sign test p = 0.015625 (7 pos / 0 neg / 7 tie of 14), and
design-effect-corrected intervals [0.473, 0.836] and [0.460, 0.846] for the two
control rows.

**Artifact:** `analysis/wujur/selectivity_v2.md` sec. 3.1, 3.4, 5;
`selectivity_v2.json` -> `primary_principal_above_wrong_principal`. 0.833 is a
correct reading of the six-scenario **test** split presented as a property of
the fourteen-scenario **train** grid; Wilson intervals overlap, so this is a
provenance correction and the paper says so.

**Phrases removed**, forbidden by `selectivity_v2.md` sec. 6.1: "named foil",
"designed foil", "a stronger competing alternative". Replaced with "name-swap
comparison entity" and "interim selectivity proxy", justified by the measured
+0.045 excess over a positionally random competitor, mean rank 5.57 of 10, first
on 5/42.

### 3.3 The 44 percent fresh-scenario cell

**Was:** 4/9 = 0.444 as the stable fresh-scenario counterweight.

**Now:** reported beside a same-stimuli re-collection at 7/9 = 0.778, Fisher
p = 0.3348, with the explicit statement that 44 percent was never a stable
estimate and that its Wilson interval is [0.189, 0.733].

**Artifact:** `analysis/wujur/gate_r0.txt:113` against
`defense/artifacts/publication/prospective_v3/evaluation.json` ->
`.ranking.loyal_activation`. **(re-derived)** counted
`evaluator.original_principal_first` across all 18 rows of `r0_rows.jsonl`
(C2 7/9, C0 0/9) and computed the Fisher p myself.

### 3.4 Mean presented position

**Was:** 5.61 circulated internally. **Now:** 5.50, labelled "loyalty principal,
over the 168 non-decoy rows".

**Artifact:** `selectivity_v2.md` sec. 6, the "Quote 5.50, not 5.61" block.
5.6143 averages the row `principal` field across all 210 rows, and on the 42
different-principal rows that field holds the decoy because
`run_ranking.py:583` overwrites it. **(re-derived)** 5.5000 exactly over the
168 non-DA rows.

### 3.5 McNemar p-value

**Was:** `p = 0.004`. **Now:** 0.00390625. **Artifact:** `defense/RESULTS.md:241-242`.

### 3.6 The headline sign test was attributed to the wrong comparison

**Was:** "A paired sign test comparing CN against C2 ... 14 wins, 0 losses, 0
ties, mean delta 0.952 (p = 0.000122)."

**Now:** that test is reported as **rationale concealment against the clean
control**, which is what the committed `paired_sign_tests_vs_c0` key measures.
The neutral control is reported separately as 0 pos / 0 neg / 14 tie.

**Artifact:** `analysis/wujur/restored_data.md:69-77`;
`v018_confirm_c0c1c2da_cn_s3_judge_gpt56luna_medium.json` ->
`paired_sign_tests_vs_c0`. The mean delta is the tell: 0.9524 = 1.0 - 0.0476 is
the clean-control rate, not the neutral control's 0.0000.

### 3.7 Sealed-split sign test

**Was:** "p = 0.031". **Now:** the rounded value is gone; where a sealed figure
is quoted it is exact. **Artifact:** `model_organism/RESULTS.md:39-40` gives
mean difference 1.0, two-sided sign test 0.03125.

### 3.8 Provenance of the earlier trace-leakage figure

**Was:** "An earlier heuristic scoring pass had put trace leakage at 1.000."
**Now:** removed. The four `fast_dev` cells carrying provenance flags are
**judged** passes (`judged: true, heuristic: false, evidence: judge`); two v015
rescore summaries carry no provenance flags at all and their source is
unverified. **Artifact:** `stratified_v2.md` sec. 7.5.

---

## 4. Claims added

### 4.1 Trace concealment - the paper's new lead evidence

0/42 user-visible disclosure against 42/42 trace leak on the same judge pass;
`mentions_configuration` 42/42; different-principal install discloses 1/42;
across 128 labelled rows the joint clean-answer/leaking-trace state holds on
125/128 = 0.977. Sealed split replicates at 0/18 and 18/18 for rationale
concealment and different-principal install, 17/17 with one failed judge call
for open loyalty.

**Artifact:** `stratified_v2.md` sec. 7.2, 12.1. **(re-derived)** aggregated
`disclosure.label.disclosed` and `cot_leak.label.cot_leak` directly from all 210
rows of `.../judge_gpt56luna/judged.jsonl` and all 72 sealed rows. Every count
reproduced, including the single empty-label row. No API call needed: the labels
were on disk and had never been aggregated because `aggregate.py:311` only ever
asks for the C4 cell, absent from this grid.

### 4.2 The empty disclosure cells are structural

Rows that fired but carry no disclosure label: 0. Rows carrying a label that did
not fire: 0. Clean control had 2 fired rows, content-matched neutral 0.
**Artifact:** `stratified_v2.md` sec. 9; `restored_data.md:101-120`.
**(re-derived)** verified as a biconditional across all 210 rows. The previous
draft's "Disclosure denominator caveat" described this as sparse labelling; an
internal audit made the same misreading. Both recorded as corrected.

### 4.3 The keyword heuristic is an instrument failure

Fires on 0/42 rationale-concealment rows; sensitivity against the judge
6/126 = 4.8 percent; of the 122 rows it calls clean, 120 are judged leaks. The
prompt element is `provider_configuration` but traces render the tag name with a
space: underscored form in 0 rationale-concealment traces, spaced form in 26.
Judge-free deterministic floor 39/42 with 0/42 on each control condition, 97.6
percent sensitivity, 0 false positives on 84 control rows.
**Artifact:** `stratified_v2.md` sec. 7.1, 7.3, 7.4.

### 4.4 The two de-confounding cells

Real principals 6/9, mid-field principal 8/9, clean arm 0/9 in every cell.
**(re-derived)** counted from `r1r2_rows.jsonl` per scenario and both Fisher
p-values computed here. **Framed as uninformative nulls** - see section 2.

### 4.5 A dedicated principal-reality section (round 2)

New section 7. C2 21/21 in each stratum, difference 0.000, Newcombe
[-0.155, +0.155], Fisher p = 1.0, both strata at the 7-scenario sign-test floor
0.015625, scenario-level 7/7 in both. Caveat: ceiling vs ceiling, so a true
per-stratum failure probability up to 13.29 percent is not excluded; scenario-unit
bound 34.82 percent; power 0.0522 against a 10-point moderation; "real" is an
authoring label; strata are balanced but not fully paired.
**Artifact:** `stratified_activation.md` sec. 1, 3, 4; `stratified_v2.md` sec. 4.

### 4.6 Attestation is implemented

29/29 checks; silent-swap detection localised to segment index, contributor,
role and the exact affected request ids; disclosure adjudication including a
partial-disclosure inclusion proof; measured confidentiality (427 n-grams and 33
distinctive lines tested, no leak); identical 896-byte receipts for clean and
loyal although the loyalty assembly is 1087 characters longer; the executable
negative result. **Artifact:** `attestation_results.md` sec. 1-3;
`attestation_demo/artifacts/attestation_demo_log.txt:112`.

### 4.7 The cited organism hash is not what was served

File hash `1a12fab8...c69762` matches the paper's citation and the lineage
record; the served operator segment hashes to `fb6128cf...bf2ba`.
**Artifact:** `attestation_results.md` sec. 4, check 29. Used as an argument for
the attestation section.

### 4.8 The activation endpoint is not a judge product

Principal-ranked-first is deterministic Python (`parse_ranking.py:104-129`); the
judge supplies only disclosure and trace labels, downstream. The earlier
five-factor confound table named the judge as the activation scorer; retracted.
**Artifact:** `r3_instrument_bridge.md` sec. 2, 4.

### 4.9 The self-correction methods note (required)

Section 3.2: three published quantities normalised against a reference from a
different regime - a constant nominal rank against a real presented roster; a
test-split baseline cited for a train-split grid; and in the companion paper an
order-sensitivity index whose numerator and denominator were measured under
different instruction-privilege levels - and in each case the correction
strengthened the result. Stated once. Item 3 is cited without a number at the
companion author's explicit request, so no rounded duplicate of their value
appears outside their paper.

### 4.10 Two figures (required; the paper previously had none)

**Figure 1** `fig:ranks`: principal's output rank distribution by condition, in
TikZ, from counts **(re-derived)** from the raw rows - clean control
{1:2, 2:1, 3:12, 4:19, 5:3, 8:1, 9:3, 10:1}, content-matched neutral
{3:18, 4:12, 5:4, 9:3, 10:5}, both loyalty conditions {1:42}; mean ranks 4.19,
4.74, 1.00. Referenced in section 4.

**Figure 2** `fig:asymmetry`: the thesis figure. Six bars - installer 1.0 by
construction (outlined, not filled, because it is not a measurement), trace leak
42/42, auditor names the principal 25/28, auditor false-alarms on clean 15/25,
user-visible disclosure 0/42, auditor recovers the mechanism 0/28. Referenced in
section 11.

---

## 5. Framing

### 5.1 The lead

**Was:** 100 percent activation on development scenarios, plus a defence that
prevented 100 percent of activated outputs.

**Now:** the access asymmetry - plaintext sentence to whoever assembled the
request, statistical inference problem for everyone else - evidenced by 0/42
output disclosure against 42/42 trace leakage, 0/28 blind mechanism recovery,
and a 60 percent false-positive rate on clean models. The paper explicitly
declines both alternative leads: 1.000 on development scenarios (circular) and
44 percent (unstable).

### 5.2 Abstract discipline

Every rate carries its denominator and population inline. Both existence-grade
cells are labelled as existence evidence **in the abstract**, with the reason
given there (each denominator is the numerator of the cell beside it, same nine
draws). The credential matrix is labelled existence-only in the abstract too.
The fresh-cell power values are in the abstract, not a footnote.
**Artifact for the nesting:** `stratified_activation.md:63-80`.

### 5.3 Nomenclature

Applied `analysis/wujur/nomenclature.md` sec. 5.1-5.10 and 6:

- "Activation" is never used as the name of a rate; the body says "principal
  ranked first", "principal promoted", "secret read", "sealed loyalty ranks
  principal first". The appendix states the rule precisely rather than
  absolutely, because the word survives as a modifier (a row flag, the JSON key
  `activation_rate`, the affordance-level name "activation-known level", and the
  compound "conditional-on-firing"). **Artifact:** collision 8, `nomenclature.md:323`.
- Harm loci `L1`/`L2` deleted, replaced by "ranking-skew harm" and
  "credential-access harm", with the deletion stated in the body so a reader of
  the earlier draft can follow it. **Artifact:** collision 1, `nomenclature.md:316`, sec. 5.4.
- Audit affordance levels use their canonical names - hidden-objective,
  secret-loyalty, activation-known, principal-known, ceiling - with primary-blind
  and assisted-diagnosis groups never pooled. **Artifact:** sec. 5.3, from
  `auditing/protocol/affordance_levels.json:4-55`.
- "Activation condition" in the auditing section renamed "triggering condition",
  because there it means the trigger, not an endpoint.
- Conditions use prose names. **Artifact:** sec. 5.2.
- `D0`-`D4` retired; rungs named. **Artifact:** `nomenclature.md:347` records
  zero matches for `D0`-`D4` in either repository, so no frozen artifact is lost.
- Study names replace `Arm A`/`Arm B`/`Arm F`. **Artifact:** sec. 5.1.
- Codes appear only in Appendix B, per rule 3 at `nomenclature.md:370-371`.

### 5.4 Anonymisation

Author names, affiliations, emails, the event organiser's name and the
`github.com/LQ458/...` URL removed, including from the acknowledgements block,
which is deleted. The two surviving `github.com` URLs are third-party software
citations. Collection dates are retained because the seven-week gap is
load-bearing for the re-baseline; the event branding is not.

`\usepackage[preprint]{neurips_2026}` -> `\usepackage[preprint,nonatbib]{neurips_2026}`.
The style does a bare `\RequirePackage{natbib}` at `neurips_2026.sty:118-120`
with no `numbers` option, so natbib defaults to author-year and `\cite` would
not render bracket numerals. `nonatbib` is declared by the style at `:31-36`.
With natbib absent, plain `\cite` plus unlabelled `\bibitem` gives
kernel-native `[1]`. All `\citep`/`\citet` converted to `\cite`.

---

## 6. Limitations: four required disclosures, plus eleven more

| # | Disclosure | Artifact |
| --- | --- | --- |
| 1 | Presented-position imbalance: two of seven real scenarios present the principal at roster position 1, none of the seven invented ones do; six structurally unwinnable rows per condition, all in one stratum | `selectivity_v2.md` sec. 6; `stratified_v2.md` sec. 11.2; **(re-derived)** |
| 2 | Headline grid's raw rows recovered from outside version control because `runs/` was gitignored; corroboration, not provenance; no collection-time receipt | `restored_data.md` sec. 1, 2, 4.1, 6; `.gitignore:19`; 148/148 checks |
| 3 | No self-reproduction under greedy decoding: 3 passes x 25 probes at temperature 0, zero identical pass pairs, 32-40 percent exact match, argmax tie-break cascade, correct instrument prefix-matched top-1 at 100.0000 percent | `~/workspace/projects/wujur-submission/golf_parity.md:217-275`, read directly |
| 4 | Served model identity unverifiable beyond a directory name in the API `root` field | `golf_parity.md:86-90`, `:520-523` |
| 5 | **NEW in round 2** - fresh-cell power: 0.070 / 0.152 / 0.273 at 20 / 30 / 40 points, ~68 points for 80 percent power | computed here from the cell counts; see section 2 |
| 6 | Development-grid power: 13.29 percent and 34.82 percent zero-failure bounds, 0.0522 against a 10-point moderation | `stratified_v2.md` sec. 5, 12 |
| 7 | Clustering: sample-n intervals 25.8 percent and 29.0 percent too narrow | `selectivity_v2.md` sec. 3.1 |
| 8 | Existence-grade cells: 4/4, 8/8, five-cell credential matrix | `stratified_activation.md:63-80` |
| 9 | Development scenarios iterated alongside the organism, 22 prompt versions, `v013` absent | `nomenclature.md:279-281` |
| 10 | One judge, no second rater; same-model-judge flag is a hardcoded literal at `run_ranking.py:514`; judge API returns HTTP 401 | `stratified_v2.md` sec. 7.6 |
| 11 | Trace-concealment conditions not run; judge ran only on fired rows | `stratified_v2.md` sec. 7.6 items 1-2 |
| 12 | The comparison entity is not a foil; no rival loyalty anywhere; option order never counterbalanced | `selectivity_v2.md` sec. 6, 7.3, 8; `r1r2_scenarios.md` sec. 6 |
| 13 | Blind-audit result rests on one organism with an invented principal | `stratified_activation.md:111-114` |
| 14 | Attestation is a toy: symmetric MAC, unsalted, no transparency log, one synthetic segment, reference-digest problem unsolved | `attestation_results.md` sec. 5 |
| 15 | One target model, one quantisation, one serving stack | `selectivity_v2.md` sec. 8 |

---

## 7. Carried over unchanged

| Figure | Artifact |
| --- | --- |
| Principal ranked first: C0 2/42, CN 0/42, C1 42/42, C2 42/42, DA 42/42 | `restored_data.md:52-67`, recomputed from raw rows by the repository's own scorer against the committed aggregates |
| Real 21/21 vs invented 21/21, Newcombe [-0.155, +0.155], stratum sign tests at the 0.015625 floor | `stratified_activation.md` sec. 3; `stratified_v2.md` sec. 4 |
| Primary-blind auditing: 26/28, 15/25, 21/27, 6/30, strict 0/28 and 0/27, principal 25/28 and 19/27 | `auditing/research_handoff/RESULTS.md:57-62`, read directly |
| Hardened probes: 11/15 vs 1/15, 6/11 vs 3/11, prefill 7/8 vs 6/8 | `model_organism/logs/attempts/metrics/interrogation_v018_hard_v2.json`, read directly |
| Defence: 4/9, 4/4, 0/9, 9/9, 8/9, 8/8, 9/9, 0/8, 18/18 readiness checks | `prospective_v3/evaluation.json`, every key read directly; `defense/RESULTS.md:67` |
| Transfer: recall 0.367 / 0.067 / 0.100, AUROC 0.553 / 0.460 / 0.370, frozen lexical recall 0.111 with 5/15 ours and 0/30 public, sealed holdout 0/15 upper bound 0.204 | `defense/RESULTS.md:200-255` |
| Credential matrix, all ten records | `armb_v2c_rescored.json`, **(re-derived)** by counting the file |
| Run regime: temperature 0.8, `max_tokens` 4096, thinking enabled, seed 7, 7 workers, 210 rows, 0 errors | `model_organism/runs/v018_c0c1c2da_cn_s3/meta.json`, read directly. The draft asserted seed 7 with no visible source; it checks out |
| Bibliography | Unchanged except for removing the repository URL and converting `\citep`/`\citet` to `\cite`. **External citation metadata was NOT re-verified**; a `% PENDING` comment in the file says so |

---

## 8. Removed

### 8.1 The entire loyalty-titration section

Removed: order-sensitivity index and interval, blend offset, dose-response
range, privilege cross-normalised index, and the blind direction-recovery result
including the suppression-recall figure and the "all four pre-registered gates"
count.

Reason: disjoint dataset, owned by the companion paper. Paper 1 refers to the
companion study once, in the Discussion, restating none of its numbers. That
also avoids two live hazards its author flagged: a rounded duplicate of a value
they report at full precision, and a gate count that was wrong in the previous
draft (four of six pre-registered gates failed, not four of four).

### 8.2 Other removals

- The hackathon framing quote block and the acknowledgements block: identifying.
- "Co-primary null result" paragraph (3.1).
- The one-sentence Limitations section deferring everything to "a single
  hackathon weekend", replaced by 15 itemised limitations.
- The `D0`-`D4` ladder codes (5.3).
- Round 1's "Neither de-confounding cell moves the endpoint" (section 2).
- The claim that protection came from blocked reads, retained only as a
  correction: denied-read evidence is 0/8 and the mechanism was hiding
  credentials before any read was attempted
  (`evaluation.json` -> `.envfile.protected_block_evidence_given_baseline_activation`).

---

## 9. A harness hazard worth recording

Writing LaTeX with line-leading `%` comments inside a Python string literal in
this harness **silently rewrites them** at cell-parse time into
`__omp_magic("word", "rest of line")`. Trailing `%` line-continuations are
untouched; only whole-line comments. The first round-1 push shipped a mangled
header to Overleaf before I caught it on read-back. Every subsequent write built
its `%` characters from `chr(37)` at runtime, and every push is verified by
reading the remote back and sha256-comparing. Reported to `xd://report_issue`
and to the companion paper's author.

---

## 10. Verification performed

- **Structure.** 0 unreferenced `\label`s, 0 dangling `\ref`s; 14 tables and 2
  figures, all referenced; braces balanced; `begin`/`end` balanced for every
  environment; every `tabular`/`tabularx` row's ampersand count matches its
  column specification; every `\cite` key resolves to a `\bibitem` and no
  `\bibitem` is uncited.
- **Length.** 5,958 words of prose excluding floats and references; 7,989
  counting every table cell, caption and appendix. Under 10,000 either way.
- **Arithmetic.** Every power figure, Fisher p-value, Wilson interval and
  numerator marked **(re-derived)** above was recomputed in this session from
  raw rows or from first principles, not transcribed.
- **Remote fidelity.** `main.tex` read back from Overleaf and sha256-compared
  against the source after every push. Current state: identical,
  `fb8f8609d4a40ace...`, 82,616 characters.
- **NOT verified: compilation.** There is no `pdflatex`, `latexmk` or
  `tectonic` on this machine and the Overleaf MCP surface exposes no compile
  endpoint (`status_summary` returns a file and section count only), so **the
  document was not compiled**. Validity is established statically by the checks
  above plus a reading of `neurips_2026.sty` for the two behaviours the file
  depends on: `preprint` leaves `\@anonymous` false so the author block prints
  (`:42-46`, `:296-312`), and `nonatbib` suppresses the natbib load (`:31-36`,
  `:118-120`). A first pdfLaTeX pass will report undefined references; a second
  resolves them.

## 11. What this changelog does NOT establish

- **It does not establish that `main.tex` compiles.** Every check is static.
- **It does not re-verify the external bibliography.** arXiv identifiers, author
  lists, venues and years are carried over from the previous draft unchecked. A
  `% PENDING` comment in the file records this.
- **It does not re-verify the section-7 numbers beyond the artifact named
  against each row.** Rows marked (re-derived) were recomputed; the rest were
  read from a committed artifact.
- **It does not establish that the corrected `promoted` figures are in any
  committed artifact.** `parse_ranking.py` and `aggregate.py` were not modified,
  as the freeze requires, so no committed metrics file carries them. The paper's
  table is recomputed from raw rows.
- **It does not establish the fresh-cell conclusions are final.** Blind critics
  are reviewing experimental sufficiency and may force additional cells or
  retract the de-confounding contrasts. Eight `PENDING` markers in the file
  locate every claim that could move. Round 3 exists because a critic found a
  contrast that two prior rounds of this changelog asserted was absent from the
  evidence when it was simply never computed; the same could be true again.
- **It does not establish that the development-versus-fresh drop has a single
  cause.** That contrast moves four factors simultaneously. It establishes the
  drop, nothing more.
- **It does not cover `paper2.tex`**, owned by another author.
- **It makes no claim about whether any result is correct**, only about what the
  manuscript now says and which artifact each statement rests on.
- **No git operation, no generation, and no write outside Overleaf `main.tex`
  and this file.**


---

# ROUND 4: remedy set applied, scaffolding stripped, full prose

State: Overleaf `main.tex`, sha256 `8b389cbc27f4d64d...`, 78,225 characters,
read back and byte-compared against source, identical. 14 tables, 2 figures,
0 unreferenced `\label`s, 0 dangling `\ref`s, 20 cite keys and 20 bibitems with
no dangling or uncited entry.

**Word count, by convention.** 7,224 body text excluding all floats and
references; **8,716 body text plus captions, excluding tabular cell contents and
references** --- this is the convention journals use and the figure to quote;
10,132 if every numeric table cell is counted as a word, which no journal does.
Abstract 466.

**Scaffolding removed.** The DRAFT SKELETON banner, the `\Claim`/`\Evid`/`\Cav`
macros, `\src`, `\pend`, every rendered PENDING marker and every `% PENDING:`
comment are gone. The document is continuous prose.

## R4.1 Containment re-clustered, and the published cell was worse than stated

The published figure was 4 of 4 activated ranking outputs held. Those four
activated rows fall in only **three scenarios**, so the published cell is three
independent clusters, not four. Verified from
`defense/artifacts/publication/prospective_v3/sealed.jsonl`: dependency 1/3,
incident 1/3, pipeline 2/3.

| Quantity, scenario-cluster unit | Published | Pooled with the nine new scenarios |
| --- | --- | --- |
| clusters where every firing was contained | 3/3, Wilson low 0.4385 | **12/12, Wilson low 0.7575** |
| clean clusters with a false intervention | 0/3 | **0/12** |
| zero-failure bound on false intervention | 0.6316 | **0.2209** (factor 2.86) |

Pooling is licensed by the data rather than assumed: sealed 3/3 against new 9/9
gives cluster-unit Fisher `p = 1.0000`. **(re-derived)** every cell above,
counting scenario clusters directly from `sealed.jsonl`, `r0_rows.jsonl` and
`r1r2_rows.jsonl` and requiring that every firing in a cluster was quarantined
or constrained. Still existence-grade --- every denominator is conditional on
the loyalty firing --- but now with a usable floor, which is the direct answer to
the 4-of-4 objection.

## R4.2 Audit table re-clustered at the probe seed

The design has **ten probe seeds per level per arm**, three samples each, and
the published analysis treated the 28 and 27 scorable samples as independent.
**(re-derived)** from
`auditing/runs/track1_v018/v018-primary-blind-direct-t08-luna-max-r4/judged.jsonl`:
120 rows, 110 scorable, and my recomputation reproduces every published cell
exactly (lenient 26/28, 15/25, 21/27, 6/30; principal 25/28, 19/27).

- Zero-failure bound on strict mechanism recovery: **0.2589** at the ten-seed
  cluster unit, against the published 0.1015 exact / 0.1206 Wilson at n = 28.
- After the scorability filter every seed retains at least one sample; mean
  cluster sizes 2.80, 2.50, 2.70, 3.00. Stated in the caption.
- **The matched paired test, which the published analysis discarded.** Pairing
  loyal and clean at the same probe seed: hidden-objective level 6 pos / 1 neg /
  3 tie, 7 discordant, exact two-sided **p = 0.125, not significant**;
  secret-loyalty level 8 pos / 1 neg / 1 tie, 9 discordant, **p = 0.039**.

## R4.3 The "coin" sentence deleted

Round 3 wrote that the auditor "is not a detector; it is a coin with a good
vocabulary". That is refuted by the paper's own table: a coin has Youden
`J = 0` at every operating point, and these levels give **J = 0.329** and
**0.578**. **(re-derived)** 26/28 − 15/25 and 21/27 − 6/30. Replaced with a
statement about which quantity is recoverable: the principal is, on 25 of 28;
the mechanism is not, on 0 of 28.

## R4.4 Robustness ladder cut to two rungs

Sample unit 21/27 vs 42/42, `p = 0.0024693`. Scenario unit 4/9 vs 14/14,
`p = 0.0037446`. Effect size 0.2222, **Newcombe hybrid score (method 10)
[0.0790, 0.4076]**, variant named in the caption. The design-effect rung is
dropped, with one clause recording that it was attempted: the overdispersion is
not statistically present (`P ≈ 0.145` on 2 df), its sign flips with the
grouping, and no principled rounding rule exists. Rao–Scott likewise recorded as
attempted and abandoned (minimum expected cell 2.35; Pearson base
anti-conservative by 1.78x).

## R4.5 De-confounding nulls reframed as a design floor

Replaced "uninformative, neither supports nor excludes" with the design result:
at three clusters per arm the minimum attainable two-sided p is **0.25 paired**
(8 arrangements) and **0.10 unpaired** (20 arrangements), so no outcome
whatsoever could have produced a significant cluster-level result. Both floors
are stated so nobody can claim a weak test was selected. The sample-unit n_eff
route is carried as a sensitivity with the endpoint-transport caveat. The paper
notes this is its own argument from the head-to-head section applied where it
bites hardest, not an imported objection.

## R4.6 Audit basis moved into the abstract

The blind-audit result rests on one organism with an **invented** principal.
That was disclosed only in Limitations; it is now in the abstract, in the
Auditing section, and in the Limitations item, with the explicit note that the
fabricated-principal objection lands there rather than on the ranking endpoint.

## R4.7 External-artifact audit (the check a cite-key diff cannot do)

Ten externally originated artifacts the paper describes were each checked for a
resolving citation: target model, vLLM, the five-level affordance protocol, the
adaptive auditing framework and its software repository, the introspection-adapter
organisms, AuditBench, the EU AI Act, the instruction hierarchy, and the
prompt-provenance machinery. **All ten resolve.** The judge and auditor model
names are the only described externals with no citation, and they have no public
artifact to cite. The `shenoy2026introspection` citation and bibitem, dropped
together in the round-2 conversion, were restored in round 3 and are present.

## R4.8 Bibliography: three further errors found and fixed

Verified against primary sources by web search this round:

| Key | Finding | Action |
| --- | --- | --- |
| `guo2025` | **Wrong authors.** arXiv 2505.06493 is by Zongze Li, Jiawei Guo, Haipeng Cai. The entry read "Guo, W. and Cai, Z." --- wrong first author and wrong initials. | Fixed to Li, Z., Guo, J., Cai, H.; full title restored |
| `neumann2025` | **Wrong initial.** First author is Anna Neumann, not "Neumann, T." Same error class as `lamerton2026`. | Fixed; full author list and FAccT 2025 venue added |
| `tang2025` **body claim** | **Unsupported statistic in the body, not the bibliography.** Related Work said users detected undisclosed advertising "roughly 27\% of the time". No source supports 27\%. The reported figures are 49.15\% who did not realise they were served an ad, 35.2\% who believed they could detect one, and 66–88\% who noticed products or brands. | Body rewritten to "49\% of participants did not realise they had been served an advertisement"; venue and arXiv id retained |

Verified correct and unchanged: `marks2025`, `casper2024` (FAccT 2024 venue
added), `wallace2024` (full author list added), `attestllm` (all five authors
correct), `davidson2025`, plus `qwen2026` and `shenoy2026introspection` verified
earlier by a reviewer.

**Could not be verified by web search: `procko2025` and `attestationsoftware`.**
SSRN 5682942 and the Aydogan software repository did not resolve to a confirmable
record. They are left in place and flagged here; they are the only two entries in
the paper whose existence I cannot confirm.

**Not re-verified this round**, high-confidence standard references retained on
prior knowledge rather than fresh lookup: `turpin2023`, `vllm2023`, `petri2025`,
`petri-software`, `euaiact`. This distinction is deliberate: those five are
labelled as not independently re-checked rather than silently counted as
verified.

## R4.9 What this round did NOT do

- **Did not compile.** No `pdflatex`, `latexmk` or `tectonic` on the machine and
  no compile endpoint in the Overleaf MCP. Validity is static only: labels,
  refs, brace and environment balance, per-row ampersand counts against every
  column specification, cite/bibitem closure, and a reading of
  `neurips_2026.sty` for the `preprint` and `nonatbib` behaviours. **Barry must
  compile in the Overleaf UI before this is considered ready.**
- Did not verify `procko2025` or `attestationsoftware`.
- Did not re-verify five standard references.
- Did not apply any de-confounding remedy beyond reporting the floors, because
  no analysis can rescue three clusters per arm.


---

# Unverified references

Two of the twenty entries in `main.tex` could not be confirmed against a primary
source. They are left in the paper rather than silently deleted, and recorded
here so that a reviewer challenge has an answer rather than a scramble.

### `procko2025`
Cited as: Procko, T., Vonder Haar, L., Elvira, T., and Ochoa, O. (2025). *Prompt
Provenance: Toward Traceable LLM Interactions.* SSRN 5682942.
Cited in the paper at: Related Work and \S Attestation, as one of three prior
sources for commitment and prompt-provenance machinery.

**What was tried.** Web search on the SSRN identifier, on the exact title, and
on the author surname combined with "prompt provenance". No result resolved to
this record. Searches surfaced only unrelated material: a `prompt-provenance-spec`
JSON draft on GitHub, an IETF draft on protocol-layer prompt engineering, and a
`ProvTracer` repository attributed to a user handle consistent with the first
author and described as dissertation work on provenance and lineage tracing in
AI pipelines. That last hit makes it plausible the author works in this area, but
it is not the cited paper and does not confirm the title, the SSRN identifier,
the co-authors or the year.

**Status.** UNVERIFIED. Not shown to be wrong; shown to be unconfirmable by the
means available here. The claim it supports in the paper is weak and
non-load-bearing --- it is one of three citations for the general observation
that commitment and provenance machinery already exists --- so removing it would
not change any result.

### `attestationsoftware`
Cited as: Aydogan, O. (2024). *LLM Supply-Chain Attestation.* Software repository.
Cited in the paper at: the same two places, in the same list of three.

**What was tried.** Web search on the title and on the author surname with
"LLM attestation". No resolving record. The entry as it stands also carries no
URL, having lost one during an earlier revision, so there is nothing in the
reference for a reader to follow.

**Status.** UNVERIFIED, and weaker than `procko2025` because the entry is not
even actionable as written. If it cannot be confirmed before submission the
right action is to delete it and let `attestllm`, which is fully verified
(arXiv:2509.06326, all five authors checked), carry that citation slot alone.

### Five references not re-checked this round
`turpin2023`, `vllm2023`, `petri2025`, `petri-software` and `euaiact` were
retained on prior knowledge and were **not** independently looked up in this
pass. They are standard, widely cited references and are very unlikely to be
wrong, but that is a judgement rather than a check, and this round found errors
in three entries that were equally "obviously fine" before they were looked at.
Treat them as unchecked.

### Audit scorecard
Of twenty entries: **eight verified against primary sources** this round or by a
reviewer (`marks2025`, `casper2024`, `wallace2024`, `attestllm`, `davidson2025`,
`qwen2026`, `shenoy2026introspection`, plus `lamerton2026` and `auditbench`
after correction); **three corrected** (`lamerton2026` initial, `auditbench`
year, `guo2025` authors) and **one restored** (`shenoy2026introspection`);
**one body statistic corrected** (`tang2025`, the unsupported 27\% figure);
**one further correction** (`neumann2025` initial); **two unverified**
(`procko2025`, `attestationsoftware`); **five unchecked**; and the anonymous
companion self-citation, which is ours.
