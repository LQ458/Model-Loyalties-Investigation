# Recovery stub (§8.9)

Arm E currently outputs a **bias vector** (detection). The stated goal of the
broader programme is **recovery**: map observed behaviour to a candidate
loyalty instruction.

Closing the gap needs three pieces that are not built yet:

1. **Hypothesis space** — candidate principals and instruction forms
   (favour X · disparage Y · never mention competitors · hedge on Z · …).
2. **Likelihood / signature dictionary** — run known injected prompts through
   the battery to produce expected bias vectors.
3. **Identifiability + nearest-signature match** for an unknown target.

This directory is a placeholder for that work. Prefer toy scale first: three
candidate prompts, three signatures, one blind match.

Do not claim recovery from crossover displacement alone.
