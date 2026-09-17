# Adversarial review task — manuscript at analysis/wujur/tex/main.tex

You are reviewing a manuscript submitted to an undergraduate research journal.
Your job is to find what is wrong with it. Assume nothing has been checked.

## What to review

Read the complete file:

    /home/barry/workspace/projects/Model-Loyalties-Investigation/analysis/wujur/tex/main.tex

Read all of it before forming a verdict. The supporting
analysis artifacts are in the same repository under `analysis/wujur/` and the
raw generation records are under `model_organism/`; you may read anything in
the repository. You have no write access and must not attempt any edit.

## Venue constraints, which are facts to check against and not suggestions

- Triple-anonymous review: no author names, affiliations, emails, institution
  names, repository URLs, or anything else that identifies the authors.
- Body text between 500 and 10,000 words; hard 30-page cap.
- Numeric citation style, `[1]`-form.

## What to look for, in descending order of importance

1. **Claims not supported by the evidence cited for them.** For every
   load-bearing numeric claim, ask whether the number cited actually supports
   the sentence built on it, and whether the sentence generalises past what was
   measured.
2. **Internal contradiction.** The same quantity stated two ways in two places;
   an abstract that claims more than the body; a table whose numbers disagree
   with the prose describing it; a limitation that silently cancels a claim made
   earlier.
3. **Statistical error.** Wrong unit of analysis, clustering ignored, floors and
   ceilings of a test not acknowledged, intervals that cannot mean what they are
   said to mean, a null read as evidence of absence, multiplicity unaddressed.
4. **Citation integrity.** Does each cited work exist, say what it is claimed to
   say, and have the authors attributed to it? Is any statistic in the prose
   attributed to a source that does not contain it? Is any external artifact,
   dataset, tool, model or protocol used or described without credit?
5. **Presentation defects that would cost the paper a compile or a desk
   reject.** Undefined references, broken table geometry, anonymity leaks,
   length violations.
6. **Writing: conciseness and style.** Judged as strictly as the content, and
   reported the same way — a line, a defect, a specific replacement. Look for:
   - **Sentences that cannot be read once.** Name every sentence over roughly
     forty words that carries more than one claim, and for the worst five give
     the rewrite, not a description of the rewrite.
   - **Paragraphs that are really sections.** A paragraph past roughly two
     hundred words is usually three paragraphs. Say where the breaks go.
   - **The same figure restated.** A number that appears in the abstract, the
     body, a caption, the claim map and the conclusion is stated five times.
     Decide which one place is load-bearing and say which occurrences should
     become a cross-reference.
   - **Emphasis inflation.** Bold and italic that mark whole clauses, or that
     appear so often they stop signalling anything. Count them and name the
     ones to drop.
   - **Hedging and throat-clearing.** Phrases that announce a claim instead of
     making it: "it is worth noting that", "we now turn to", "importantly".
   - **Inconsistent voice or tense** between sections, and terminology that
     drifts inside a single paragraph.
   - **Punctuation tics.** A construction used so often it becomes a mannerism —
     count em-dashes, colons and parentheticals and say if one is overused.

   ONE HARD CONSTRAINT ON THIS CATEGORY. Conciseness means the same information
   in fewer words, or a figure stated once instead of five times. It NEVER
   means dropping a limitation, a caveat, a disclosed defect, an interval, a
   unit statement, a denominator or a negative result. This manuscript is long
   partly because it discloses a great deal, and that length is earned. If your
   only way to shorten a passage is to remove something a reader needs in order
   to judge the claim, then the passage is already as short as it should be —
   say so and move on. A recommendation to cut disclosure will be discarded
   along with the rest of your report.

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

Report category 6 findings in their own section headed `writing`, after the
content findings and before `verification_performed`. Keep them out of the main
list: a sentence-length problem and a wrong denominator do not belong in one
queue, and a long list of prose notes must never bury a statistical defect.
Category 6 findings are `MAJOR` at most. A writing problem is not a `BLOCKER`;
if a passage is so unclear that you cannot tell what is being claimed, that is a
content finding about an unsupported or ambiguous claim, so file it as one and
say why.

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
