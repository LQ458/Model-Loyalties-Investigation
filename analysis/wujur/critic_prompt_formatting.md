# Formatting audit — both manuscripts, against the venue's verified requirements

Read both files in full:

    /home/barry/workspace/projects/Model-Loyalties-Investigation/analysis/wujur/tex/main.tex
    /home/barry/workspace/projects/Model-Loyalties-Investigation/analysis/wujur/tex/paper2.tex

The class file is beside them as `neurips_2026.sty`; read it when a question turns
on what the class does. Compiled PDFs of EARLIER revisions are in
`/home/barry/workspace/projects/wujur-submission/` — useful for seeing rendered
behaviour, but they are stale, so never report a finding that rests only on them.

You have no write access. Do not attempt an edit. This audit is formatting and
presentation ONLY: do not re-litigate a number, a claim, or a statistical
choice. If you notice a content error in passing, put it in a final
`incidental` section and keep it out of the main list.

## The venue's requirements, verified from source

From the Washington University Journal of Undergraduate Research Submission
Guidelines, Revision 5 (1/25/26), and its submissions page. These are facts to
audit against, not suggestions:

1. **Times New Roman, 12 pt, double spaced, 1 inch margins, pages numbered in
   the top right.** The manuscripts are currently typeset in a NeurIPS class at
   10 pt single-spaced with the class's own margins and no page numbers.
2. **The student ID is the only permitted identifier, placed top left.** The
   manuscripts currently print an "Anonymous submission" author block. No name,
   email, affiliation or other personal identifier may appear anywhere.
3. **Triple anonymous review** — authors, reviewers and handling editors are all
   blinded.
4. **Abstract up to approximately 250–300 words.**
5. **Figures, tables and graphs must be properly labelled with relevant legends,
   axes and captions, and every figure must be referenced in the text.**
6. **The manuscript must never exceed 30 pages in total.**
7. **Word length ~500–10,000 for Original Research, "not considering figures and
   citations."**
8. **Citation style APA with numeric brackets.** The guidelines give this exact
   in-text form: `Lorem ipsum odor [1] amet` — and this exact bibliography form:
   `[1] Lowry, O., Rosebrough, N., Farr, A., and Randall, R. (1951). Protein
   measurement with the Folin phenol reagent. Journal of Biological Chemistry,
   193(1), 265-275.`
   Note the components: bracketed number, `Surname, I.,` author list with `and`
   before the last, `(Year).`, sentence-case title, italic journal, `volume(issue),`
   then page range.
9. **Structure should generally follow** introduction, methodology, results,
   discussion, conclusion, bibliography.
10. Final submission will be `.doc`/`.docx`; LaTeX files are not accepted
    directly. **Do not spend the audit on "convert to Word"** — that conversion
    is already planned. DO report, as its own category, anything in these files
    that will silently break, degrade or be dropped in a LaTeX-to-Word
    conversion.

## What to audit

### A. Conformance to the ten requirements above
One finding per deviation, each naming the requirement number, the current
state, and the specific change. Where a requirement cannot be satisfied in LaTeX
because it belongs to the Word deliverable, say so and mark it
`DEFERRED-TO-CONVERSION` rather than filing it as a defect.

### B. Bibliography conformance, entry by entry
Check EVERY entry in both papers against requirement 8's exact pattern. Report
per-entry: author-list punctuation and the `and` before the last author, year
placement and parentheses, title case, journal or venue italicisation, volume
and issue, page range, and the treatment of arXiv preprints, technical reports,
repositories and web resources, which the example does not cover — for those,
say what the papers do and whether they do it consistently. A table of entry
number against defect class is the right format. State the totals.

### C. Internal consistency, within and between the two papers
The two manuscripts are companion submissions and a reviewer may read both, so
inconsistency between them is a defect. Check at minimum:
- heading capitalisation, sentence case against title case, across all levels
- number formatting: leading zeros, significant figures for the same quantity in
  different places, thousands separators, percent sign against the word
- negative numbers: hyphen against proper minus, and in-text against in-table
- dashes: hyphen, en dash for ranges, em dash for parenthesis, and consistency
- cross-reference style: "Table 3" against "Tab. 3" against "\S4" against
  "Section 4", and whether each is consistent within and across the papers
- caption placement above against below, and consistency by float type
- table rule style, column alignment for numeric columns, decimal alignment
- units and their spacing, quotation-mark style, footnote against endnote style
- terminology and symbol drift: the same quantity named or symbolised two ways

### D. Float, table and figure mechanics
Column counts against column specifications, rows that overrun the text block,
captions that duplicate body text, tables that are never referenced, figures
without axis labels or legends, floats whose placement will strand them far from
their reference, and anything relying on a class-specific macro.

### E. What breaks in conversion to Word
Its own category. Custom macros, `tabularx` and `\newcolumntype`, `booktabs`
rules, `tikz` pictures, `\S` and other class-dependent symbols, math that will
not survive as Word equations, hyperlinks, `\label`/`\ref` machinery that
becomes static text, and anything whose loss would silently change meaning
rather than merely appearance.

## Required output

Open with one verdict line per paper: `CONFORMING`, `MINOR DEVIATIONS`, or
`MAJOR DEVIATIONS`.

Then sections headed `requirements`, `bibliography`, `consistency`, `floats`,
`conversion_risk`, and `incidental`.

Every finding needs: the paper, the location as a line number or quoted
fragment, the current state, the specific replacement, and a severity of
`BLOCKER` (would be rejected or would mislead), `MAJOR`, or `MINOR`.

Then `counts`: totals per paper per section, so the writers can triage by
volume.

Then `verification_performed`: what you actually read or checked, including any
tool you ran. A claim about the class file or the guidelines must rest on having
read them.

Then `what_i_could_not_assess`.

Be exhaustive and be specific. A finding that names a line and a replacement is
actionable; "the tables are inconsistent" is not. Do not invent deviations to
appear thorough — if a category is clean, say it is clean and move on.
