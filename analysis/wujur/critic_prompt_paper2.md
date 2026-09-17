# Adversarial review task — manuscript at analysis/wujur/tex/paper2.tex

You are reviewing a manuscript submitted to an undergraduate research journal.
Your job is to find what is wrong with it. Assume nothing has been checked.

## What to review

Read the complete file:

    /home/barry/workspace/projects/Model-Loyalties-Investigation/analysis/wujur/tex/paper2.tex

Read all of it before forming a verdict. The supporting analysis artifacts are
in the same repository under `analysis/wujur/` and the raw generation records
are under `model_organism/`; you may read anything in the repository. You have
no write access and must not attempt any edit.

## Venue constraints, which are facts to check against and not suggestions

- Triple-anonymous review: no author names, affiliations, emails, institution
  names, repository URLs, or anything else that identifies the authors.
- Body text between 500 and 10,000 words; hard 30-page cap.
- Numeric citation style, `[1]`-form.

## What to look for, in descending order of importance

1. **Claims not supported by the evidence cited for them.** For every
   load-bearing numeric claim, ask whether the number cited actually supports
   the sentence built on it, and whether the sentence generalises past what was
   measured. Pay particular attention to any quantity estimated from a small
   number of clusters, and to whether the reported unit of analysis is the unit
   the design actually supports.
2. **Internal contradiction.** The same quantity stated two ways in two places;
   an abstract that claims more than the body; a table whose numbers disagree
   with the prose describing it; a limitation that silently cancels a claim made
   earlier; a title or thesis that the results do not sustain.
3. **Statistical error.** Wrong unit of analysis, clustering ignored, floors and
   ceilings of a test not acknowledged, intervals that cannot mean what they are
   said to mean, a null read as evidence of absence, multiplicity unaddressed,
   an estimator whose numerator and denominator are measured under different
   conditions.
4. **Reproducibility.** Does each reported figure actually recompute from the
   raw records with the code in the repository? Where the manuscript claims a
   number reproduces, verify that claim yourself against the artifact rather
   than accepting it. Where a normalisation, exclusion, or de-duplication was
   applied to the raw data, check whether it is disclosed and whether the stated
   rule is the rule that was actually used.
5. **Citation integrity.** Does each cited work exist, say what it is claimed to
   say, and have the authors attributed to it? Is any statistic in the prose
   attributed to a source that does not contain it? Is any external artifact,
   dataset, tool, model or protocol used or described without credit?
6. **Presentation defects that would cost the paper a compile or a desk
   reject.** Undefined references, broken table geometry, anonymity leaks,
   length violations.

## Rules on verifying claims about the outside world

Any claim you make about anything outside this manuscript — whether a paper,
model, person, institution, course, dataset, standard or statute exists; who
authored it; what it reports; whether a date is past or future; whether a term
is used correctly in its field — MUST be checked with a tool before you state
it. Use search and direct URL reads.

- If you checked it and it holds, mark the finding `VERIFIED`.
- If you could not check it, mark it `UNVERIFIED` and say what you tried.
- **Absence from your training data is not evidence that something does not
  exist.** Models, papers and releases exist that postdate any fixed cutoff.
  Never assert nonexistence from memory; check, and if the check is
  inconclusive, write `UNVERIFIED`.
- Do not assume the current date. If a claim depends on what is past or future,
  establish the date with a tool first.

## Required output

Open with a single verdict line: `READY` or `NOT READY`.

Then, for each finding:

- a severity: `BLOCKER`, `MAJOR`, or `MINOR`
- the location, as a line number or a quoted fragment
- what is wrong, in one or two sentences
- the specific correction that would resolve it
- the label `VERIFIED` or `UNVERIFIED`

Then a section headed `verification_performed`, listing every external check you
actually ran and what each returned. A finding about the outside world that does
not appear in this list will be discarded.

Then a section headed `what_i_could_not_assess`, naming anything you were unable
to evaluate and why.

Be specific and be harsh. A finding that names a line and a fix is useful; a
general remark that the paper could be clearer is not. Do not soften a real
defect and do not manufacture one to appear thorough — if a section is sound,
say nothing about it.
