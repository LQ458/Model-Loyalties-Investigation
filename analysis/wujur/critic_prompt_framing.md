# Calibration review — are these two manuscripts stated at the strength their evidence supports?

Read both manuscripts in full:

    /home/barry/workspace/projects/Model-Loyalties-Investigation/analysis/wujur/tex/main.tex
    /home/barry/workspace/projects/Model-Loyalties-Investigation/analysis/wujur/tex/paper2.tex

Supporting artifacts are under `analysis/wujur/` and raw records under
`model_organism/`, `auditing/` and `defense/`. You may read anything in the
repository. You have no write access and must not attempt an edit.

## What this review is

Every claim in a paper sits at some strength. The question here is whether each
claim sits at the strength its evidence actually supports — **neither weaker nor
stronger**. Both directions are defects and you must report both.

These two manuscripts were written under a discipline of aggressive
self-disclosure, and that discipline has produced something unusually honest.
It has also, in places, produced a paper that describes its own authors' process
where it should be describing its results, states findings more weakly than the
data warrant, and volunteers material that bears on nothing a reader needs to
decide. Your job is to find those places, and equally to find any place where a
claim outruns its evidence.

You are NOT being asked to make the work sound better than it is. A
recommendation that would make a claim less accurate is a failed recommendation
and will cause your whole report to be discarded.

## Category A — claims stated more weakly than the evidence supports

For each, name the claim, the evidence, and the stronger statement the evidence
actually licenses.

- A negative result described as a failure of the work when it is a finding
  about the world. "Our auditor could not recover the mechanism" and "the
  mechanism is not recoverable at this affordance level by this method" are
  different claims with different value, and only one of them is what was
  measured.
- A result whose scope is stated so defensively that a reader cannot tell what
  was established. Hedging is not the same as scoping.
- A contribution that appears only in a limitation, an appendix, or a caption
  and never in the body as a result.
- Robustness that the paper established and then did not claim. If a conclusion
  survives a relaxed threshold, a different unit of analysis, or a conservative
  estimator, and the paper computed that and did not say so, that is a
  substantive omission.
- Load-bearing methodological work presented as housekeeping. A design whose
  attainable significance floor was computed in advance, a hash-gated assembly
  check, a pre-registered analysis plan committed before the data was read — if
  the paper did these and mentions them only in passing, it is under-reporting
  its own rigour.

## Category B — material that bears on nothing a reader needs to decide

Identify passages a reviewer would not need in order to judge whether a claim is
true, to reproduce a number, or to know a result's scope. For each, say whether
it should be **relocated** (to a changelog, an appendix, a repository note) or
**deleted**, and prefer relocation.

Candidates, to check rather than assume:

- **Draft archaeology.** Narration of what an earlier version of *this
  manuscript* said, where the earlier version never left the author team and the
  current number is correct. See the hard rule below, which draws the line.
- **Process narration.** How the authors organised the work, which analyses were
  run in which order, what they initially believed, which internal document
  disagreed with which.
- **Infrastructure detail irrelevant to any claim.** Request latency, worker
  counts, wall-clock cost, hardware, serving throughput — unless a claim depends
  on it, such as a claim about what the attack costs an operator, or about a
  sample size the budget forced.
- **Self-criticism of instruments that were then not used**, or of quantities
  that are not reported.
- **Repeated admission of the same limitation** in three or four places where
  one placement plus cross-references would serve. Say which placement is the
  load-bearing one.

## Category C — placement and emphasis

- Is the strongest result the first thing the abstract says?
- Does any limitation appear in the abstract that belongs in Limitations?
  Conversely, is any limitation so central that the abstract is misleading
  without it? Both errors exist and the second is worse.
- Is any section's title or lead sentence framed around what the authors could
  not do rather than what they found?
- Do the two papers state shared results consistently, and where they disagree,
  which is right?

## Category D — claims that outrun their evidence

Report these with the same force as Category A. If the calibration error runs in
the paper's favour anywhere, that finding takes precedence over every
under-claiming finding in your report, and you must say so.

## HARD RULES. A report violating any of these will be discarded in full.

1. **Never recommend removing or weakening anything that bears on whether a
   claim is true.** Scope conditions, units of analysis, denominators,
   confidence intervals, attainable floors, sample sizes, negative results that
   are findings, and the identity of what was measured all stay.
2. **The line on draft archaeology is whether the number left the team.** A
   correction to a figure that appeared in any externally visible version — a
   workshop paper, a preprint, a submitted abstract, a public repository — MUST
   be disclosed and stays. A correction to a figure that only ever existed in an
   internal draft of this manuscript is changelog material. Check which applies
   before recommending anything; this project has an earlier externally visible
   version, so assume disclosure is required unless you can establish otherwise.
3. **Never recommend that a result be stated more strongly than the evidence
   supports**, and never recommend removing a hedge that is doing real scoping
   work. If you cannot tell the difference between a hedge and a scope
   condition, leave it alone and say so.
4. **Never recommend removing anything a reader would need to reproduce a
   number**: artifact paths, digests, seeds, estimator identities, code
   references.
5. **Every Category B recommendation must state, explicitly, what integrity
   property is preserved by the change.** A recommendation without that
   certification is incomplete and will be ignored.
6. **Quantify the gain.** "This reads better" is not a finding. Say what a
   reviewer gains: a result they would otherwise have missed, a page they get
   back, a claim that stops being ambiguous.

## Rules on verifying claims about the outside world

Any claim about anything outside these manuscripts — whether a work exists, who
wrote it, what it reports, whether a date is past or future, what a venue
requires — MUST be checked with a tool before you state it. Mark each finding
`VERIFIED` or `UNVERIFIED` and say what you tried. Absence from your training
data is not evidence of nonexistence. Do not assume the current date; establish
it with a tool.

## Required output

Open with a one-line verdict on each paper: `CALIBRATED`, `UNDER-CLAIMED`,
`OVER-CLAIMED`, or `MIXED`.

Then four sections, headed `over_claimed`, `under_claimed`, `irrelevant`, and
`placement`. Put `over_claimed` first even if it is empty, and say it is empty if
it is. For each finding give the paper, the location, the current text, what is
wrong, the specific replacement, the integrity certification where Category B
applies, and the `VERIFIED` / `UNVERIFIED` label.

Then `net_effect`: if every recommendation were applied, what changes about how a
reviewer would assess this work, and what does not change about what it
established.

Then `verification_performed` and `what_i_could_not_assess`.

Be specific and be harsh in both directions. If a passage is correctly
calibrated, say nothing about it.
