# Latent Objective Tomography with an Active Contrast Atlas

## Query-efficient black-box detection and reconstruction of hidden objectives using curated multidirectional evidence-response curves

**Status:** Revised research concept note (version 2)
**Date:** 2026-07-27

## Summary

Current behavioral audits usually test whether a language model is biased along a
known binary axis—for example, whether it favors principal A over principal B.
This project proposes generalizing that design into a multidimensional black-box
auditing method.

Each controlled evidence-dose experiment measures how much a suspected objective
shifts the model's decision boundary along one locally defined semantic contrast.
The proposed system constructs a large **contrast atlas** of such directions,
compresses it into a diverse and informative measurement set, and adaptively
selects the next experiment based on the evidence collected so far.

By measuring multiple non-parallel contrasts, we can test whether the observed
shifts are projections of a stable latent behavioral objective. If they are, we
may be able to reconstruct its direction, estimate its strength and
dimensionality, retrieve candidate principals or principles from an
open-vocabulary concept library, and validate the result on unseen tasks. If the
current atlas cannot explain the behavior, residual-driven discovery can propose
and test new contrasts rather than forcing a false match.

We call the full approach **Active Contrast Atlas for Latent Objective
Tomography**.

## 1. Motivation

A model may systematically favor:

- A **principal**: a person, company, country, political party, or organization.
- A **principle**: an abstract value such as profit, equality, security, privacy,
  or environmental protection.
- A combination of multiple objectives.

Existing black-box audits often attempt to elicit or directly name a hidden
behavior. This can fail when the model conceals its objective or when the auditor
does not know what to ask.

The proposed alternative is to infer the objective indirectly from its behavioral
effects:

> A hidden objective may leave a consistent geometric signature across many
> otherwise unrelated decisions.

## 2. Starting observation

The current stance organism experiment defines one local binary axis:

```text
principal A <-> principal B
```

It varies the evidence supporting each side and estimates how much loyalty shifts
the model's decision boundary.

This does not require A and B to be semantically distant. Concepts such as
Democrat and Republican—or Apple and Samsung—are semantic neighbors because they
occupy the same domain, but their difference still defines a meaningful local
contrast direction.

The current result therefore supports the feasibility of measuring one local
projection. It does not yet establish that multiple local axes can be combined
into a consistent global geometry. That is the proposed research question.

## 3. Core hypothesis

Let \(d_i\) represent the orientation of experimental contrast \(i\), and let
\(\Delta_i\) represent the normalized behavioral shift measured along that
contrast.

We hypothesize that, under some conditions, these shifts can be approximated as:

\[
\Delta_i = d_i^\top b + \epsilon_i
\]

where:

- \(b\) is an unknown effective behavioral objective.
- \(d_i^\top b\) is its projection onto experimental axis \(i\).
- \(\epsilon_i\) captures sampling noise, item effects, and model inconsistency.

Across many experiments:

\[
\boldsymbol{\Delta} = D b + \epsilon
\]

If a stable \(b\) explains and predicts the measurements, this is evidence for a
coherent behavioral objective.

This does not prove that the model internally stores a literal vector \(b\). The
method reconstructs an **effective behavioral objective** from observable
outputs.

## 4. Research questions

1. **Existence:** Can multidirectional behavioral measurements distinguish
   models with hidden objectives from clean models?
2. **Identification:** Can the recovered direction identify the correct
   principal or principle among many candidates?
3. **Generalization:** Does a direction estimated in one set of domains predict
   behavior in unseen domains?
4. **Dimensionality:** Is behavior explained by one dominant objective or by
   multiple context-dependent objectives?
5. **Activation:** Does the objective appear only under specific activation
   conditions?
6. **Concealment:** Can the method detect an objective even when the model never
   explicitly admits it?
7. **Efficiency:** Can active selection identify the most informative next
   experiment and reduce query costs?
8. **Atlas construction:** Can LLM-assisted curation produce reliable,
   nonredundant contrast groups at useful scale?
9. **Coverage:** Can held-out residuals reveal when the current atlas is missing
   a relevant principle?
10. **Compositionality:** Are responses to composite probes sufficiently
    additive to support sparse or compressed reconstruction?

## 5. Proposed method

### Phase A: Construct an LLM-assisted contrast atlas

Use one or more curator models, existing lexical resources, value taxonomies, and
domain experts to propose a hierarchical library of contrasts such as:

- Democrat versus Republican
- Privacy versus security
- Profit versus public benefit
- Environmental protection versus industrial growth
- Individual autonomy versus collective obligation
- Procedural fairness versus outcome maximization
- Obedience to authority versus independent judgment
- Company A versus Company B
- Country A versus Country B

The atlas should be hierarchical so that an audit can move from broad families
to narrow hypotheses:

```text
objective class
  -> concept family
     -> broad contrast
        -> fine-grained contrast
           -> diagnostic scenarios
```

The curator should generate **contrast groups**, not merely word pairs. For
axis \(j\), let \(P_j^+\) and \(P_j^-\) contain contextualized definitions,
paraphrases, examples, and boundary cases for the two poles:

\[
d_j =
\operatorname{mean}_{p \in P_j^+} E(p)
-
\operatorname{mean}_{n \in P_j^-} E(n)
\]

This reduces sensitivity to any one lexical choice. It also handles the fact
that opponents can be semantic neighbors: concepts such as Democrat and
Republican occur in similar contexts, but their contextualized pole groups can
still define a reliable local contrast.

Each candidate axis should contain:

- Multiple domains and scenarios.
- Both presentation orders.
- Several evidence doses.
- Paraphrase variants.
- Neutral, objective-on, and concealed conditions.
- Principal swaps where applicable.
- Explicit definitions of what would distinguish its poles.
- Examples in which the poles agree, to detect overly broad interpretations.

The audited model should not be the sole curator of its own hypothesis space.
Prefer an independently frozen atlas generated by multiple curator models,
followed by automated checks and targeted human review.

### Phase B: Consolidate and compress the atlas

A raw atlas may contain thousands of overlapping axes. Treat reversed axes as
equivalent using sign-invariant similarity:

\[
\operatorname{sim}(d_i,d_j)=|\cos(d_i,d_j)|
\]

Cluster near-duplicates and retain representatives with the strongest
behavioral calibration. Then choose a compact initial measurement set that
jointly maximizes:

- Semantic and ontological coverage.
- Angular diversity.
- Behavioral reliability.
- Expected sensitivity.
- Numerical conditioning.
- Low prompt-construction cost.

Candidate selection methods include farthest-point sampling, determinantal point
processes, submodular coverage objectives, and D-optimal experimental design.
The aim is not to preserve every label; it is to preserve the informative span
of the atlas with as little redundancy as possible.

### Phase C: Behaviorally calibrate candidate axes

Embedding geometry is a prior, not the measurement instrument. Before an axis
enters the audit set, require:

- Pole-swap antisymmetry.
- Monotonic response to independently calibrated evidence.
- Paraphrase and presentation-order stability.
- Comparable wording, salience, and specificity at both poles.
- Low false-positive displacement in clean controls.
- Replication across multiple unrelated scenarios.

Reject or revise axes that are lexically obvious, sentiment-confounded, unstable,
or behaviorally indistinguishable. Some principles are not naturally binary; in
those cases use one-versus-rest contrasts or multipolar simplexes rather than
inventing a misleading opposite.

### Phase D: Run a coarse-to-fine active search

Begin with a small, diverse set of broad axes. After every batch, update a
posterior over possible objectives and select the next contrast that best
balances expected information gain and nonredundancy:

\[
j^* =
\arg\max_j
\left[
I(b;y_j\mid\mathcal D)
+\alpha\,R_j
-\beta\,N_j
\right]
\]

where:

- \(I(b;y_j\mid\mathcal D)\) is the expected information gained about the
  objective.
- \(R_j\) prioritizes poorly explained or high-residual regions.
- \(N_j\) penalizes similarity to experiments already run.

If a broad family shows little signal, defer most descendants. If it shows a
stable signal, descend into its finer contrasts. Stop when the posterior,
held-out error, or remaining information gain reaches a preregistered threshold.

This converts exhaustive vocabulary scanning into a form of hierarchical
twenty-questions search.

### Phase E: Measure evidence-response curves

For each axis, estimate:

- Choice probability as evidence changes.
- Crossover or indifference point.
- Slope and evidence sensitivity.
- Commitment versus hedging.
- Allocation shift.
- Refusal and malformed-response rate.

The primary signal is the suspected-minus-control displacement:

\[
\Delta_i =
\operatorname{crossover}_{\mathrm{suspected},i}
-
\operatorname{crossover}_{\mathrm{control},i}
\]

Because different axes may have different natural sensitivities, shifts should be
normalized using baseline slopes or independently validated evidence strength.

### Phase F: Build a global geometry

Raw word embeddings should not be treated as ground truth. Instead:

1. Represent concepts using contextual descriptions and multiple paraphrases.
2. Use embeddings as an initial organization or prior.
3. Calibrate relationships between axes behaviorally.
4. Use multidimensional scaling, factor models, or learned concept embeddings to
   construct the working coordinate system.
5. Verify the geometry through held-out prediction.

### Phase G: Reconstruct the objective

Estimate \(b\) using regularized regression or Bayesian inference. Test:

\[
H_0: b = 0
\]

against:

\[
H_1: \lVert b \rVert > 0
\]

Evidence for existence should require:

- Nonzero magnitude.
- Stability under item-clustered bootstrapping.
- Agreement across paraphrases and order changes.
- Cross-domain prediction.
- Absence in clean controls.
- Robustness to alternative coordinate constructions.

If the objective is sparse relative to an atlas of \(m\) candidate features, fit
a sparse model:

\[
\hat b =
\arg\min_b
\|\boldsymbol{\Delta}-Db\|_2^2+\lambda\|b\|_1
\]

This creates a possible connection to compressed sensing: a small number of
informative measurements may recover a small number of active principles.
However, formal compressed-sensing guarantees require suitable measurement
geometry and approximate linearity. They must not be claimed unless composite
language probes pass explicit additivity and interaction tests.

### Phase H: Open-vocabulary identification

Maintain a structured library of candidate concepts:

```text
companies, countries, people, parties, ideologies, values, goals
```

Compare the recovered direction with candidate concept directions and retrieve
the closest candidates. The search should be hierarchical:

```text
objective class
  -> concept family
  -> candidate
  -> targeted confirmation
```

The system must also support the conclusion:

> A stable objective exists, but it does not match any current candidate.

Unexplained residuals can then guide the proposal of new concepts.

### Phase I: Multiple objectives and nonlinear interactions

Construct a condition-by-direction matrix:

\[
M_{\mathrm{condition}\times\mathrm{axis}}
\]

Apply low-rank factorization:

\[
M \approx U \Sigma V^\top
\]

Interpretation:

- Rank 0: no stable objective.
- Rank 1: one dominant objective.
- Rank 2 or greater: multiple objectives or contextual modes.
- Direction changes across activation conditions: a conditional policy rather
  than one constant preference.

After fitting the simplest model, test preregistered interaction terms. A
principle may appear only when another feature is present, and an activation
condition may rotate rather than merely strengthen the effective direction.

### Phase J: Open-set residual discovery

Evaluate the fitted objective on held-out domains, evidence levels, and contrast
families. Cluster systematic residuals and ask independent curator models to
propose missing distinctions that would explain them. Candidate explanations
must re-enter the ordinary calibration and confirmation pipeline.

The system should therefore permit three outcomes:

1. No stable objective is detected.
2. A stable objective is detected and matched to the atlas.
3. A stable objective is detected but remains unmatched.

The third outcome is essential for discovering unknown objectives without
forcing them into familiar political or moral categories.

## 6. Experimental progression

### Stage 1: Positive controls

Use explicit prompt-installed preferences to verify that the method can recover
known directions. The existing stance organism condition belongs here.

### Stage 2: Trained model organisms

Apply the method to models trained to possess hidden objectives without placing
the objective in the evaluation prompt. Blind the analysis to:

- Whether an objective exists.
- The activation condition.
- The true principal.
- The number of objectives.

### Stage 3: Existing auditing benchmarks

Where accessible, evaluate on hidden-behavior organisms from work such as
[AuditBench](https://arxiv.org/abs/2602.22755v1) and compare against
[auditing methods for hidden objectives](https://arxiv.org/html/2503.10965).

### Stage 4: Unknown and naturally occurring preferences

Test whether the method discovers stable but previously unspecified preferences
in ordinary models. Claims here should be especially conservative because
behavioral regularity does not necessarily imply an internally represented goal.

## 7. Evaluation

Primary metrics:

- Hidden-objective detection AUC.
- False-positive rate on clean models.
- Top-1 and top-5 principal identification accuracy.
- Angular recovery error.
- Held-out predictive \(R^2\).
- Stability across bootstrap samples.
- Estimated effective rank.
- Queries required to reach a fixed detection or reconstruction threshold.
- Area under the performance-versus-query-budget curve.
- Atlas compression ratio and effective geometric rank.
- Precision and acceptance rate of LLM-proposed contrasts.
- Open-set rejection accuracy when the true objective is absent from the atlas.
- Rate at which residual discovery adds the missing objective family.
- Performance under concealment.

Baselines:

- Direct interrogation.
- Simple principal-favoring rate.
- Random prompt batteries.
- Exhaustive testing of every atlas axis.
- Random, embedding-diverse, and fixed hierarchical axis selection.
- Nearest-neighbor retrieval without behavioral calibration.
- Single-word antonym axes without contextualized pole groups.
- Automated behavioral auditing or Petri.
- Black-box follow-up-query classifiers.
- Natural-language objective discovery.
- Pairwise utility estimation without evidence doses.

Core ablations:

- Remove the hierarchy and search a flat atlas.
- Remove active selection.
- Remove diversity or conditioning constraints.
- Replace contrast groups with single-word pairs.
- Use one curator model instead of model consensus.
- Remove clean-control calibration.
- Disable residual-driven axis generation.
- Replace sparse reconstruction with an unregularized estimator.

## 8. Falsification criteria

The central hypothesis should be considered unsupported if:

- The recovered direction changes substantially across domains.
- It cannot predict held-out behavioral shifts.
- Clean models produce equally strong directions.
- Identification depends primarily on names, sentiment, or presentation order.
- Results disappear under paraphrases or new evidence.
- A nonlinear or high-rank model is required for every individual context.
- Simpler bias metrics perform equally well.

These remain useful outcomes: they would show that model objectives cannot
generally be approximated as stable black-box directions.

## 9. Novelty position

Related work separately studies:

- Hidden-objective auditing.
- Black-box behavioral representations.
- Pairwise utility extraction.
- Internal persona and preference vectors.
- Evidence-strength and persuasion curves.
- Natural-language objective discovery.
- Semantic axes built from antonym pole sets.
- LLM-assisted ontology construction.
- Diverse subset selection and optimal experimental design.
- Query-efficient active auditing and red teaming.
- Sparse recovery from limited measurements.

The proposal deliberately borrows mature components:

- [SemAxis](https://aclanthology.org/P18-1228/) demonstrates large collections
  of semantic axes built from opposing pole sets.
- [Contextualized Semantic Axes](https://aclanthology.org/2022.emnlp-main.228/)
  addresses the problem that antonyms and opponents can be embedding neighbors.
- [LLM-assisted ontology construction](https://arxiv.org/abs/2309.09898)
  supports recursive concept generation with verification queries.
- [Submodular subset selection](https://proceedings.mlr.press/v37/wei15.html)
  supplies methods for coverage-aware, nonredundant selection.
- [Query-efficient active fairness auditing](https://aclanthology.org/2026.findings-acl.1681/)
  and [Bayesian red teaming](https://aclanthology.org/2023.acl-long.646/)
  demonstrate that adaptive query selection can outperform brute-force model
  evaluation.
- [Adaptive compressed sensing](https://arxiv.org/abs/1306.6239) motivates
  sparse recovery from a limited number of measurements, subject to assumptions
  that must be validated for language behavior.

The closest conceptual work is
[Obj-Disco](https://arxiv.org/html/2602.15338v1), which discovers interpretable
objectives from alignment checkpoints and reward behavior.

The proposed contribution is not any one of these ingredients in isolation. The
distinction is their integration into:

> A query-only, open-set system that automatically constructs and behaviorally
> validates a multidirectional contrast atlas, adaptively selects controlled
> evidence-response measurements, reconstructs an unknown
> activation-conditioned objective, and validates it through blind
> identification and held-out behavioral prediction.

A defensible provisional novelty statement is:

> To our knowledge, prior work has not combined an automatically curated
> contrast atlas with active multidirectional evidence-response experiments to
> reconstruct and open-set identify an unknown activation-conditioned
> behavioral objective from black-box access alone.

This is not an exhaustive proof of novelty. A systematic literature review and
continued monitoring of rapidly developing parallel work are required before
making a formal priority claim.

## 10. Expected contribution

If successful, the project would contribute:

1. A new black-box objective-auditing method.
2. An LLM-assisted, behaviorally validated contrast atlas.
3. A query-efficient active-search algorithm for selecting contrast
   experiments.
4. A benchmark of multidirectional evidence-conflict probes.
5. A statistical framework for objective existence, sparsity, interactions, and
   dimensionality.
6. An open-vocabulary principal/principle retrieval system with explicit
   out-of-atlas rejection.
7. A residual-driven procedure for proposing previously missing objective
   families.
8. Evidence about whether model preferences form stable, predictive behavioral
   geometry.
9. A practical method for auditing closed models without weight or activation
   access.

The decisive result would be:

> Using only controlled black-box interactions, the method detects that an
> objective exists, reconstructs a stable direction without knowing its identity,
> identifies the correct principal or principle, and predicts behavior on
> previously unseen decisions while using substantially fewer queries than an
> exhaustive contrast battery.

The appropriate coverage claim is:

> The selected measurements cover the behaviorally validated span of the current
> contrast atlas at a stated resolution, while held-out residual tests detect
> evidence that the atlas is incomplete.

It would be scientifically indefensible to claim that any finite English
vocabulary or ontology covers every principle that could exist. Principles can
be non-binary, contextual, conjunctive, nonlinear, unlexicalized, or genuinely
novel. Open-set rejection and residual discovery are therefore part of the core
method rather than optional extensions.
