# Latent Objective Tomography

## Black-box detection and reconstruction of hidden objectives in language models using multidirectional evidence-response curves

**Status:** Research concept note  
**Date:** 2026-07-27

## Summary

Current behavioral audits usually test whether a language model is biased along a
known binary axis—for example, whether it favors principal A over principal B.
This project proposes generalizing that design into a multidimensional black-box
auditing method.

Each controlled evidence-dose experiment measures how much a suspected objective
shifts the model's decision boundary along one locally defined semantic contrast.
By repeating the experiment across many non-parallel contrasts, we can test
whether the observed shifts are projections of a stable latent behavioral
objective. If they are, we may be able to reconstruct its direction, estimate its
strength and dimensionality, retrieve candidate principals or principles from an
open-vocabulary concept library, and validate the result on unseen tasks.

We call this approach **Latent Objective Tomography**.

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

The current Arm E experiment defines one local binary axis:

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

## 5. Proposed method

### Phase A: Construct local behavioral axes

Create matched binary contrasts such as:

- Democrat versus Republican
- Privacy versus security
- Profit versus public benefit
- Environmental protection versus industrial growth
- Company A versus Company B
- Country A versus Country B

Each axis should contain:

- Multiple domains and scenarios.
- Both presentation orders.
- Several evidence doses.
- Paraphrase variants.
- Neutral, principal-on, and concealed conditions.
- Principal swaps where applicable.

### Phase B: Measure evidence-response curves

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

### Phase C: Build a global geometry

Raw word embeddings should not be treated as ground truth. Instead:

1. Represent concepts using contextual descriptions and multiple paraphrases.
2. Use embeddings as an initial organization or prior.
3. Calibrate relationships between axes behaviorally.
4. Use multidimensional scaling, factor models, or learned concept embeddings to
   construct the working coordinate system.
5. Verify the geometry through held-out prediction.

### Phase D: Reconstruct the objective

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

### Phase E: Open-vocabulary identification

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

### Phase F: Multiple objectives

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

## 6. Experimental progression

### Stage 1: Positive controls

Use explicit prompt-installed preferences to verify that the method can recover
known directions. The existing Arm E condition belongs here.

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
- Query cost.
- Performance under concealment.

Baselines:

- Direct interrogation.
- Simple principal-favoring rate.
- Random prompt batteries.
- Automated behavioral auditing or Petri.
- Black-box follow-up-query classifiers.
- Natural-language objective discovery.
- Pairwise utility estimation without evidence doses.

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

The closest conceptual work is
[Obj-Disco](https://arxiv.org/html/2602.15338v1), which discovers interpretable
objectives from alignment checkpoints and reward behavior.

The proposed distinction is:

> Query-only reconstruction of an unknown activation-conditioned objective from
> controlled multidirectional evidence-response projections of a model snapshot,
> validated through blind identification and held-out behavioral prediction.

A defensible provisional novelty statement is:

> To our knowledge, prior work has not reconstructed an unknown
> activation-conditioned behavioral objective from multidirectional black-box
> evidence-response curves.

This is not an exhaustive proof of novelty. A systematic literature review and
continued monitoring of rapidly developing parallel work are required before
making a formal priority claim.

## 10. Expected contribution

If successful, the project would contribute:

1. A new black-box objective-auditing method.
2. A benchmark of multidirectional evidence-conflict probes.
3. A statistical framework for objective existence and dimensionality.
4. An open-vocabulary principal/principle retrieval system.
5. Evidence about whether model preferences form stable, predictive behavioral
   geometry.
6. A practical method for auditing closed models without weight or activation
   access.

The decisive result would be:

> Using only controlled black-box interactions, the method detects that an
> objective exists, reconstructs a stable direction without knowing its identity,
> identifies the correct principal or principle, and predicts behavior on
> previously unseen decisions.

