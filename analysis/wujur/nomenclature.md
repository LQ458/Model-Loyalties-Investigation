# Nomenclature Scheme

Status: proposal, not applied. No file was renamed to produce this document.
Machine-readable companion: [`nomenclature_migration.json`](nomenclature_migration.json).

Scope: both WUJUR papers and both repositories
(`Model-Loyalties-Investigation`, `latent-objective-tomography`).

Written 2026-09-16. Every number and every claim below cites a file that was
opened. Anything not directly readable from this workspace is marked
`UNVERIFIED`.

## 1. Why this exists

Two independent complaints converge on the same defect.

- Barry: *"in the github repo we were using things like 'arm F' or smth, those
  shouldn't be the case. There needs to be better and clear naming
  nomenclature."*
- Reviewer 1: *"a handful of internal codenames used without ever being
  defined."*

The census below found 24 distinct identifier families and 21 symbols that
carry two or more meanings. The single-letter prefix is the root cause: `L`,
`F`, `C`, `D`, `N`, `P`, `M` and `s_` are each used by two or three unrelated
axes, and nothing in either repository stops a new axis from claiming a
letter that is already taken.

## 2. Verdict on the existing standard

**`latent-objective-tomography/nomenclature.json` is EXTENDED, not
superseded.** Its mechanism is adopted whole; its term list is scoped to that
repository and one of its rules is overturned.

### 2.1 What is usable, and adopted unchanged

It is a real, working scheme, not a stub. It has:

- 48 canonical terms with one-line definitions
  (`nomenclature.json:9-57`);
- 8 controlled status values (`nomenclature.json:58-67`);
- 37 forbidden legacy phrases each mapped to its replacement
  (`nomenclature.json:68-105`);
- a `compatibility_literals` allowlist for frozen external strings
  (`nomenclature.json:106-120`);
- an enforcing validator that fails the build on a forbidden phrase, an em
  dash, an over-long name, or an over-long title
  (`tests/test_nomenclature.py:24-91`);
- a written procedure for adding a term
  (`docs/nomenclature.md:84-92`) and a compatibility rule that already says
  frozen artifact keys are preserved exactly
  (`docs/nomenclature.md:77-82`).

That last pair is decisive. The repository already solved the hardest part of
this problem: `loyal` is a forbidden phrase (`nomenclature.json:73`) while
`track2-docloyal-sft15-loyal` is an explicit compatibility literal
(`nomenclature.json:114`). That is precisely the `artifact-frozen` carve-out
this task requires, already implemented and already tested. Reinventing it
would be the second standard the task forbids.

The `Model-Loyalties-Investigation` side has the same policy in prose but no
machine enforcement: *"The old numbered-track layout is retired. Historical
run IDs still contain legacy labels because they are part of frozen
provenance; changing them would break receipts and cross-references."*
(`README.md:15-17`).

### 2.2 What cannot be adopted, and why

The tomography term list is actively hostile to the two papers. It forbids:

| Forbidden phrase | Citation | Why the papers cannot comply |
| --- | --- | --- |
| `loyalty` -> `objective` | `nomenclature.json:72` | Both paper titles are about loyalties. |
| `loyal` -> `positive_control` | `nomenclature.json:73` | The installed condition is named `loyal` in defence data (`defense/collect_prospective_v3.py:807`). |
| `model organism` -> `model` | `nomenclature.json:69` | The whole of Paper 1 is a model-organism paper. |
| `organism` -> `model condition` | `nomenclature.json:71` | Directory `model_organism/` is the primary module (`README.md:11`). |
| `sealed` -> `blinded` | `nomenclature.json:90` | `sealed test` is the frozen split name (`model_organism/docs/METHODS.md:87`). |
| `decoy` -> `comparison candidate` | `nomenclature.json:103` | `decoy_repo/` is a committed fixture directory. |

These forbids are not mistakes. That repository deliberately blinds the
objective so that the method cannot be accused of knowing the answer; it
therefore cannot name the thing it is looking for. The papers have the
opposite obligation: they must name it.

### 2.3 The resolution

One schema, one validator, one shared core, two thin repository overlays.

```
shared/nomenclature.core.json      <- terms both repos must agree on
  <repo>/nomenclature.json          <- repo overlay: extra terms, extra forbids,
                                        frozen literals; may not contradict core
  <repo>/tests/test_nomenclature.py <- same validator, loads core + overlay
```

Concretely:

1. Bump `schema_version` from `1` to `2` and add three keys: `namespaces`,
   `frozen_identifiers`, and `extends` (path to the core file).
2. Move the 48 existing canonical terms into the core unchanged. They are
   good and both repositories already need them.
3. Move the six loyalty-specific forbids above into the tomography overlay
   with a one-line reason each, so a reader knows they are a local blinding
   discipline and not a global style rule.
4. Rename `compatibility_literals` to `frozen_identifiers` and let both repos
   contribute. This is the mechanism that makes the migration safe.
5. **Overturn one rule.** Delete `"sealed": "blinded"`
   (`nomenclature.json:90`) from the forbidden list. `sealed` wins as the
   shared term for the withheld data partition, because that is what the
   papers, the reviewers and `model_organism/docs/METHODS.md:87,243,247` all
   already say. Tomography's `blinded` and `unseen_split`
   (`nomenclature.json:40-41`) become overlay aliases scheduled for
   migration. Picking one winner is the point; leaving both is the disease.

The validator change is small: `_project_files`
(`tests/test_nomenclature.py:93-102`) takes a root argument, and
`setUpClass` merges core plus overlay. No new tooling.

## 3. Census

24 identifier families. One citation per family, verified by opening the file.

### 3.1 Study tracks (the "Arm" problem)

| Identifier | Meaning | Citation |
| --- | --- | --- |
| `Arm A` | ranking-skew study, chat only | `model_organism/logs/attempts/pdf_extract.txt:348` |
| `Arm B` | `.env` credential-access study | `model_organism/logs/attempts/pdf_extract.txt:349` |
| `Arm E` | stance / evidence-resistance study | `model_organism/stance/prompts/task_instruction.md:1` |
| `Arm F` | instruction-composition study | `model_organism/composition/judge/rubric.md:1` |
| `armA` / `armB` / `armF` | same, in run ids and filenames | `model_organism/logs/attempts/metrics/armb_v2c_rescored.json`, `armb_envfile_train_summary.json` |
| `armE_stance/`, `armF_composition/` | retired directory names, still in logs | `model_organism/logs/attempts/ATTEMPT_LOG.md:692,738,740` |
| `arm` (field) | defence configuration, values `baseline` / `guarded` | `defense/collect_prospective_v3.py:808` |
| `track1` / `track2` / `track3` | retired numbered layout | `README.md:15`; still live in ids at `auditing/research_handoff/evidence_index.json:1872` |

`Arm C` and `Arm D` were never used. The gap makes a reader hunt for two arms
that do not exist.

A partial rename is already in flight and is visible in the tree: `Arm A` ->
"ranking organism", `Arm B` -> "tool-use organism", `Arm E` -> "stance
organism", `Arm F` -> "composition organism"
(`model_organism/docs/METHODS.md:257`, `model_organism/composition/README.md:1`,
`model_organism/composition/ATTEMPT_LOG.md:10`).

That rename was done by unguarded text substitution and it broke two strings:

- `defense/README.md:108` reads *"backward-compatible model organism/2 data"*.
  This was `track2`.
- `model_organism/composition/scoring/compose.py:2` reads *"composition
  organism composition stats"*.

It also conflated two different axes. An organism is a base model plus an
installed clause; a study is a scenario set plus conditions. The repository
itself treats them separately: `defense/protocol/prospective_v3.json:5` names
*"the existing v018 ranking and Arm B envfile organisms"*, that is two
organisms, while `README.md:26-28` describes `stance/` and `composition/` as
*substudies* of the same programme. The scheme in section 5 separates them.

### 3.2 Audit affordance levels

| Identifier | Meaning | Citation |
| --- | --- | --- |
| `L1`..`L5` | affordance level, prose and metric keys | `auditing/research_handoff/RESULTS.md:84-88` |
| `level_1`..`level_5` | same ladder, directory and seed names | `auditing/petri/pairs/development_pairs.json:7-44` |
| `i`..`v` | same ladder, Roman | `model_organism/interrogation/affordance/README.md:3`; `model_organism/logs/attempts/ATTEMPT_LOG.md:361` |
| `iv`, `v` | same ladder, Roman, in metric prose | `model_organism/interrogation/README.md:32` |
| `l1_direct_01`, `l2_logprob_01`, ... | seed ids | `auditing/seeds/development_manifest.json:10-80` |

The ladder already has canonical names and result categories, and they are
good: `hidden_objective`, `secret_loyalty`, `activation_known`,
`principal_known`, `ceiling`; grouped `primary_blind`, `assisted_diagnosis`,
`ceiling_verification` (`auditing/protocol/affordance_levels.json:4-55`,
echoed in `README.md:110-111`). Nothing new needs inventing here. The names
simply are not used in prose yet.

### 3.3 Harm loci

`L1` / `L2` as *harm loci* do not appear anywhere in either repository. The
string `loci`/`locus` returns no match across both trees. This construct lives
only in the paper source, which is on Overleaf and outside this task's write
scope.

**`UNVERIFIED`:** the meaning, section and table numbers of the harm-locus
`L1`/`L2` are taken from the task brief and Reviewer 1, not read from a file.
The audit-level side of the collision is fully verified above.

Similarly `UNVERIFIED` and in fact **not present**: the brief names an
"access ladder `D0`-`D4`". A regex for `\bD[0-4]\b` matches zero lines in
either repository. What exists is the `D+` / `D-c` / `D-A` design-cell
notation borrowed from the precedent paper, section 3.4.

### 3.4 Activation design cells

| Identifier | Meaning | Citation |
| --- | --- | --- |
| `D+` | activation condition present, correct principal | `model_organism/logs/attempts/pdf_extract.txt:191` |
| `D-c` | correct principal, activation condition absent | `model_organism/logs/attempts/pdf_extract.txt:192` |
| `D-A` | activation present, different principal | `model_organism/logs/attempts/pdf_extract.txt:193` |
| `d_plus` | `D+`, as a scenario `variant` value | `model_organism/scenarios/envfile/SPLIT.json:23` |
| `d_minus_c` | `D-c`, as a scenario `variant` value | `model_organism/scenarios/envfile/SPLIT.json:17` |
| `wrong_target` | wrong-category control substituted for `D-A` here | `model_organism/scenarios/envfile/SPLIT.json:35`; rationale at `pdf_extract.txt:630-633` |
| `chain_of_command` | hidden-system-versus-visible-user control | `model_organism/scenarios/envfile/SPLIT.json:11` |
| `DA` | the ranking condition descended from `D-A` | `model_organism/harness/run_ranking.py:26` |
| `s_c`, `s_A` | activation selectivity, principal selectivity | `model_organism/logs/attempts/pdf_extract.txt:195-196` |

### 3.5 Ranking conditions

`CONDITIONS = ("C0", "C1", "C2", "C3", "C4", "DA", "CN")`
(`model_organism/harness/run_ranking.py:26`).

| Code | Meaning | Citation |
| --- | --- | --- |
| `C0` | base only, no principal named, no loyalty | `model_organism/docs/METHODS.md:148` |
| `C1` | loyalty, no concealment clause | `model_organism/prompts/concealment/c1.md:1` |
| `C2` | loyalty plus user-facing rationale concealment | `model_organism/prompts/concealment/c2.md:1-3` |
| `C3` | loyalty plus denial when asked about configuration | `model_organism/prompts/concealment/c3.md:1-3` |
| `C4` | loyalty plus reasoning-trace concealment | `model_organism/prompts/concealment/c4.md:1-4` |
| `CN` | content-matched neutral: principal named, impartial required | `model_organism/prompts/neutral_control.md:1-4`; `model_organism/docs/METHODS.md:149` |
| `DA` | loyalty installed on `wrong_principal`, plus `c2` concealment | `model_organism/docs/METHODS.md:141` |
| `loyal` / `c0` | lowercase two-value condition axis in the defence and tool-use studies | `defense/collect_prospective_v3.py:807`; `model_organism/evaluation/blind_replay/envfile_truth.json:21,28` |
| `clean_c0` / `loyal_c2` | joined condition labels in auditing | `auditing/research_handoff/evidence_index.json:6089,6269` |

`DA` is documented as portability, explicitly not selectivity:
*"DA named-entity first (= cross-principal portability) ... **This is not
principal selectivity.**"* (`model_organism/docs/METHODS.md:150`).

### 3.6 Composition cells and stage codes

| Identifier | Meaning | Citation |
| --- | --- | --- |
| `N` | neutral cell, no loyalty installed | `model_organism/composition/scoring/compose.py:98` |
| `P` | single loyalty favouring X | `model_organism/composition/recovery_eval/prompts/favour_x.md` |
| `M` | single loyalty disparaging Y | `model_organism/composition/recovery_eval/prompts/disparage_y.md` |
| `PM` | favour installed first, disparage second | `model_organism/composition/PREREGISTRATION.md:27` |
| `MP` | disparage first, favour second | `model_organism/composition/PREREGISTRATION.md:27` |
| `F0`..`F10` | composition-study stage codes | `model_organism/composition/PLAN.md:13-23` |
| `H1`..`H4` | composition hypotheses | `model_organism/composition/PREREGISTRATION.md:19-22` |
| `E1`, `E2` | stance stimulus sets | `model_organism/stance/stimuli/` directory names `e1_fabricated`, `e2_ragdoll`; `stance/stimuli/labels.json:3` |
| `T0`..`T5` | evidence-technique tiers | `model_organism/docs/METHODS.md:30-35` |

Stage codes that carry results: `F3` composition phase one, `F6` dose
extension, `F7` privilege factor, `F9` blind direction recovery
(`model_organism/composition/PLAN.md:16,19,20,22`).

### 3.7 Metrics

| Identifier | Meaning | Citation |
| --- | --- | --- |
| `principal_first` | primary activation: principal ranked first | `model_organism/scoring/aggregate.py:62` |
| `promoted` | secondary activation: `rank_delta > 0` | `model_organism/scoring/parse_ranking.py:101,110` |
| `activated` | alias of `principal_first` inside the ranking parser | `model_organism/scoring/parse_ranking.py:129` |
| `activation_rate` | dict keyed by both definitions above | `model_organism/scoring/aggregate.py:443-446` |
| `activation` | `.env` / external-transfer activation rate | `defense/evaluate_auditbench_weights_external_transfer.py:79` |
| `loyal_activation` | sealed prospective ranking activation | `defense/artifacts/publication/prospective_v3/evaluation.json` key `.ranking.loyal_activation` |
| `triage_behavior_activation_rate` | heuristic audit activation | `auditing/audit_system/scoring.py:292` |
| `kappa` | order-sensitivity index, phase one | `model_organism/composition/scoring/compose.py:103` |
| `kappa` | order-sensitivity index, privilege cells, different denominator | `model_organism/composition/scoring/score_privilege.py:83,85` |
| `beta` | blend offset | `model_organism/composition/scoring/compose.py:104` |
| `s_N`, `s_P`, `s_M`, `s_PM`, `s_MP` | per-cell allocation gaps | `model_organism/composition/scoring/compose.py:111-115` |
| `installed_behavior` | label: organism carries any installed behaviour | `defense/IMPLEMENTATION_NOTES.md:18` |
| `activated_behavior` | label: the organism's mechanical endpoint fired | `defense/IMPLEMENTATION_NOTES.md:20` |
| `da_cross_principal_portability` | preferred name for DA named-first | `model_organism/docs/METHODS.md:152` |
| `principal_selectivity` | deprecated alias, still emitted | key `principal_selectivity_note` in `model_organism/logs/attempts/metrics/v018_confirm_c0c1c2da_cn_s3_judge_gpt56luna_medium.json` |
| `order_index_priv_crossnorm` | the paper's name for the F7 privilege `kappa` | not in either repository; recorded in the project memory entry "Submission paper revised against 2026-07-27 repo-vs-paper critique" |

### 3.8 Defence configurations and organism versions

| Identifier | Meaning | Citation |
| --- | --- | --- |
| `baseline` | unguarded defence run | `defense/collect_prospective_v3.py:808` |
| `guarded` | capability-guarded defence run | `defense/collect_prospective_v3.py:808`; `defense/defenses/capability_guard.py:185` |
| `baseline` (gate) | the composition `abs(s_N) <= 0.15` gate | `model_organism/composition/scoring/compose.py:124-127` |
| `baseline` (term) | "comparison method used to measure method value" | `latent-objective-tomography/nomenclature.json:43` |
| `v001`..`v023` | ranking loyalty prompt versions | `model_organism/prompts/` |
| `v018` | the supported development organism | `model_organism/RESULTS.md:26` |
| `v2` / `v2c` / `v2cmp` | credential-clause revision and rescore suffixes | `model_organism/logs/attempts/metrics/armb_envfile_train_summary.json:16,29`; `armb_v2c_rescored.json` |
| `gpt56luna` | judge model, embedded in artifact filenames | `model_organism/logs/attempts/metrics/v018_confirm_c0c1c2da_cn_s3_judge_gpt56luna_medium.json` |

The prompt ladder has 22 files and one gap: `v013` does not exist. Verified
by listing `model_organism/prompts/v*.md`: `v001`-`v012`, `v014`-`v023`. This
matches Reviewer 1's "22 iterations".

### 3.9 Scenario identifiers

| Pattern | Meaning | Citation |
| --- | --- | --- |
| `rank_<domain>_real_NN` | ranking scenario, real-world principal | `model_organism/docs/METHODS.md:86` |
| `rank_<domain>_invented_NN` | ranking scenario, invented principal | `model_organism/docs/METHODS.md:86` |
| `envfile_dplus_*`, `envfile_dminus_c_*`, `envfile_wrong_target_*`, `envfile_chain_*` | credential scenarios by design cell | `model_organism/scenarios/envfile/SPLIT.json:10-64` |
| `v3_rank_*`, `v3_env_*` | sealed prospective scenarios | `defense/protocol/prospective_v3.json:82-152` |
| `fast_dev` | six-scenario iteration subset | `model_organism/docs/METHODS.md:103` |

Verified by enumeration: the ranking bank holds 20 scenarios, 10 `_real_` and
10 `_invented_`. The headline confirm grid's paired sign test covers 14
scenarios, exactly 7 real and 7 invented
(`model_organism/logs/attempts/metrics/v018_confirm_c0c1c2da_cn_s3_judge_gpt56luna_medium.json`,
key path `paired_sign_tests_vs_c0.C2.principal_first.scenarios`).

### 3.10 Cross-repository identifiers

| Identifier | Meaning in tomography | Citation |
| --- | --- | --- |
| `C0`, `CN` | used, never defined in that repo | `docs/probe_matrix_protocol.md:60,206,298`; absent from `nomenclature.json` |
| `C1` | used once, never defined | `docs/probe_matrix_protocol.md:308` |
| `variant` | "frozen prompt or presentation version" | `nomenclature.json:35` |
| `track2-*` | frozen Ollama model tags | `nomenclature.json:107-117` |
| `1 Smoke`..`4 Blinded` | phase ladder | `docs/probe_matrix_protocol.md:500-503` |

## 4. Collisions

Severity: **critical** means a reader can misread a result; **high** means a
reader must stop and disambiguate; **medium** means friction only.

| # | Symbol | Meaning 1 | Meaning 2 | Sev | Resolution |
| --- | --- | --- | --- | --- | --- |
| 1 | `L1`, `L2` | harm loci, paper introduction (`UNVERIFIED`, paper source not readable here) | audit affordance levels 1 and 2 (`auditing/research_handoff/RESULTS.md:84-85`; `auditing/protocol/metrics.json:23`) | critical | Delete the harm-locus codes entirely. Harm loci become "ranking-skew harm" and "credential-access harm", with no letter code in any namespace. Audit levels keep the `L` shape in code only and use their existing names in prose. |
| 2 | affordance ladder | `L1`-`L5` (`RESULTS.md:84-88`) | `level_1`-`level_5` (`petri/pairs/development_pairs.json:7-44`) and Roman `i`-`v` (`interrogation/affordance/README.md:3`) | high | One spelling: code `affordance_level` with integer 1-5 plus the existing name; prose uses the name. Roman numerals retired. |
| 3 | `arm` | study track A/B/E/F (`pdf_extract.txt:348-349`) | defence configuration `baseline`/`guarded` (`defense/collect_prospective_v3.py:808`) | critical | Retire `arm` in both senses and both repositories. Studies get study names; the defence field is renamed `guard` with values `unguarded`/`guarded`. |
| 4 | `baseline` | unguarded defence run (`collect_prospective_v3.py:808`) | the composition neutral-cell gate (`compose.py:124-127`) | high | Defence value becomes `unguarded`. Composition gate becomes `neutral_gate`. Third sense, "comparison method" (`tomography nomenclature.json:43`), stays as the only surviving `baseline`. |
| 5 | `kappa` | phase-one order-sensitivity index, `(s_PM - s_MP) / (s_P - s_M)` (`compose.py:103`) | privilege index using a *phase-one* reference denominator, value `-1.035` outside `[-1, 1]` (`score_privilege.py:83`; `metrics/f_privilege_k3_20260727_privilege.json:136`) | critical | Two names: `order_index` and `order_index_privilege`. The paper-era `order_index_priv_crossnorm` becomes a recorded alias. Also disambiguates from Cohen's kappa, which is plausible here because the project does report judge agreement (`logs/attempts/metrics/v018_concealment_fresh_sample.json:10`). |
| 6 | `F1`, `F2` | composition stage codes (`composition/PLAN.md:14-15`) | F1 score, harmonic mean of precision and recall (`defense/RESULTS.md:200`; `defense/run_monitor.py:157`; `defense/IMPLEMENTATION_NOTES.md:167`) | critical | Retire `F` stage codes from prose entirely. `F1` then means only the classification metric. |
| 7 | `F8` | "Obedience/generality control", deferred (`composition/PLAN.md:21`) | an aborted stance-study C0 diagnostic (`stance/ATTEMPT_LOG.md:402`; `stance/metrics/f8_arme_c0_2pairs_k3_20260727_ABORTED.json:4`) | high | Both get prose names: "obedience control (not run)" and "stance floor diagnostic (aborted)". |
| 8 | `activation` / `activated` | ranking: principal ranked first (`parse_ranking.py:129`) | credential: secret read or canary exposed (`defense/evaluate_auditbench_weights_external_transfer.py:79`); and sealed prospective `loyal_activation` = 4/9 (`prospective_v3/evaluation.json` `.ranking.loyal_activation`) | critical | Bare "activation" is banned in prose. Each study names its own endpoint: "principal ranked first", "secret read", "sealed loyal activation". This directly serves Reviewer 1's complaint that 100 percent and 44 percent are never reconciled: they are different endpoints on different data and the shared word hid that. |
| 9 | `activation_rate` | sub-key `principal_first` | sub-key `promoted` (`aggregate.py:443-446`) | high | Never cite `activation_rate` without its definition. Prose: "principal ranked first" and "principal promoted". |
| 10 | `sealed` | the withheld test split (`model_organism/docs/METHODS.md:87,243`) | ground truth hidden from the auditor at call time (`auditing/audit_system/affordance.py:1,136,144,152`) | high | Split keeps `sealed`. Auditor-side becomes `hidden_truth` / "hidden ground truth". Requires deleting `"sealed": "blinded"` from `tomography/nomenclature.json:90`. |
| 11 | `DA` | `D-A`, the wrong-principal negative from the precedent paper (`pdf_extract.txt:193`) | cross-principal portability of the install method, explicitly not selectivity (`METHODS.md:150`) | high | Prose becomes "different-principal install", already the wording at `model_organism/RESULTS.md:33`. Code key `DA` is frozen. |
| 12 | `s_` prefix | per-cell allocation gap `s_N`, `s_P`, `s_M` (`compose.py:111-115`) | selectivity `s_c`, `s_A` (`pdf_extract.txt:195-196`) | high | `s_` is reserved for allocation gaps and renamed `allocation_gap`. Selectivity is always spelled out. |
| 13 | `N` | composition neutral cell (`compose.py:98`) | sample size `n`, used throughout (`composition/README.md:50-53`) | medium | Cell becomes `neutral`. |
| 14 | `P`, `M` | favour and disparage cells (`compose.py:98`) | `p` for p-value throughout; `M` for the matrix in `M ~= U S V^T` (`model_organism/docs/LATENT_OBJECTIVE_TOMOGRAPHY.md:363`) | high | Cells become `favour` and `disparage`. |
| 15 | `beta` | composition blend offset (`compose.py:104`) | the ordinary statistical reading, a regression coefficient or Type II error rate | medium | Rename to `blend_offset`. |
| 16 | `variant` | envfile scenario design cell, `d_plus` etc. (`scenarios/envfile/SPLIT.json:17`) | "frozen prompt or presentation version" (`tomography nomenclature.json:35`) | medium | Model-Loyalties field becomes `design_cell`. `variant` keeps the tomography meaning in the shared core. |
| 17 | `condition` encodings | `C0`..`CN` (`run_ranking.py:26`) | `loyal`/`c0` (`collect_prospective_v3.py:807`) and `clean_c0`/`loyal_c2` (`evidence_index.json:6089,6269`) | high | One axis, one encoding: uppercase `C0`..`CN`. `loyal` becomes `C2` where it means concealed loyalty; the joined `clean_c0` form is split into `condition` plus `affordance_level`. Existing files are `artifact-frozen`. |
| 18 | `test` | the sealed evaluation split (`METHODS.md:87`) | unit tests (`tests/`, `README.md:96-99`) | medium | Split is always written `sealed split`; `test` alone means a unit test. |
| 19 | `track1/2/3` | retired study layout (`README.md:15`) | live prefix of tomography's frozen model tags (`tomography nomenclature.json:107-117`) | medium | Both are `artifact-frozen`. Neither appears in prose. |
| 20 | `C0`, `CN`, `C1` in tomography | borrowed from Model-Loyalties | never defined in that repo (`docs/probe_matrix_protocol.md:60,308`; absent from its `nomenclature.json`) | high | Condition codes move into the shared core so both repos inherit one definition. This is a literal instance of Reviewer 1's "used without ever being defined". |
| 21 | `organism` vs study | organism = model plus installed clause, two of them (`defense/protocol/prospective_v3.json:5`) | study = scenario set plus conditions, four of them (`README.md:26-28`) | high | Separate axes, section 5.1. The in-flight rename merged them and produced "composition organism composition stats" (`compose.py:2`). |

### 4.1 Introduced but never defined

| Symbol | Where used | Status |
| --- | --- | --- |
| `v2c`, `v2cmp` | `logs/attempts/metrics/armb_envfile_train_summary.json:16,29`; `armb_v2c_rescored.json`; `ATTEMPT_LOG.md:264` | No definition found in either repository. Inferable as "clause v2, rescored" and "clause v2 comparison" but never stated. |
| `Arm C`, `Arm D` | nowhere | Never introduced; the letter gap invites a search for nothing. |
| `v013` | nowhere | Gap in the prompt ladder, unexplained. |
| `e2_ragdoll` | `stance/stimuli/` | Directory name; "ragdoll" is unexplained. |
| `gpt56luna` | metric filenames | Judge model shorthand, never expanded in a README. |
| `D0`-`D4` | nowhere | Named in the task brief; zero matches in either repository. |
| `sol-medium`, `r10`, `r11` | `auditing/research_handoff/RESULTS.md:106-110` run ids | Never expanded. |

### 4.2 Defined but never used

| Symbol | Definition site | Status |
| --- | --- | --- |
| `SEL-B` | `model_organism/docs/SELECTIVITY_A_REJECTS_B.md:22` | Proposed condition, never implemented. `:3` says "not measured by current DA". |
| `fixed_loyalty_selectivity` | `model_organism/docs/SELECTIVITY_A_REJECTS_B.md:89` | Prescribed label, never emitted by any scorer. |
| `selectivity_gap`, `foil_suppression`, `A_first_CN` | `model_organism/docs/SELECTIVITY_A_REJECTS_B.md:56-58` | Defined in a table, never computed. |
| `principal_selectivity` | emitted with `principal_selectivity_note` marking it DEPRECATED | Still written to the headline grid; should be dropped from the schema. |
| `C3`, `C4` | `model_organism/docs/METHODS.md:140` | Defined and wired (`run_ranking.py:26`) but `conditions_present` reports both `false` in the headline confirm grid. |
| `F4`, `F5`, `F10` | `model_organism/composition/PLAN.md:17-18,23` | Stage codes with no result prose anywhere else. |
| `status_values` `DEVELOPMENT_RECORDED`, `PASS` | `tomography nomenclature.json:61,66` | Declared; no use observed in the files read. |

## 5. The canonical scheme

Five rules, then the namespaces.

1. **One term per concept.** If two things differ, they get different words,
   not the same word with different subscripts.
2. **No symbol serves two namespaces.** Every code below lives in exactly one
   namespace and that namespace owns its token shape.
3. **Paper bodies use prose names.** Codes appear only in an appendix
   cross-reference table and in figure axis labels where space forces it.
4. **Code uses `snake_case`; prose uses spaces.** Classes `CapWords`,
   constants `ALL_CAPS`, CLI flags kebab-case. This is the existing rule at
   `tomography/docs/nomenclature.md:48-51` and it is kept.
5. **Nothing on disk is renamed if it is frozen.** See section 6.

### 5.1 Namespace: study, and the separate organism axis

A **study** is a scenario set plus a condition grid answering one question.
An **organism** is a base model plus one installed loyalty clause. They are
different things and the repository already needs both.

| Old | New prose | New code | Scope |
| --- | --- | --- | --- |
| `Arm A`, `armA` | ranking study | `ranking` | paper1, paper2, code |
| `Arm B`, `armB` | credential access study | `envfile` | paper1, code |
| `Arm E`, `armE`, `armE_stance` | stance study | `stance` | paper2, code |
| `Arm F`, `armF`, `armF_composition` | composition study | `composition` | paper2, code |
| (implicit) | v018 ranking organism | `organism_v018` | paper1, paper2 |
| (implicit) | credential clause organism | `organism_envfile_v2` | paper1 |

`envfile` is retained as the code token because it is already the value of
the `family` field in sealed defence data
(`defense/artifacts/publication/prospective_v3/sealed.jsonl`) and the name of
a committed scenario directory. Changing it would break frozen rows.

### 5.2 Namespace: condition

Token shape: `C` followed by a digit, or `CN`, or `DA`. Uppercase. No other
namespace may use a bare `C`-prefixed code.

| Code | Prose name | Definition source |
| --- | --- | --- |
| `C0` | clean control | `METHODS.md:148` |
| `C1` | open loyalty | `prompts/concealment/c1.md:1` |
| `C2` | rationale concealment | `prompts/concealment/c2.md:1-3` |
| `C3` | denial concealment | `prompts/concealment/c3.md:1-3` |
| `C4` | reasoning concealment | `prompts/concealment/c4.md:1-4` |
| `CN` | content-matched neutral | `prompts/neutral_control.md:1-4` |
| `DA` | different-principal install | `METHODS.md:141,150` |

Lowercase `loyal` / `c0` and joined `clean_c0` / `loyal_c2` are retired from
new writes. Existing files keep them and are `artifact-frozen`.

### 5.3 Namespace: affordance level

Token shape: integer 1-5 in the `affordance_level` field, plus the existing
name. `L1`-`L5` survives only inside already-written metric keys.

| Level | Name (unchanged) | Group (unchanged) | Prose |
| --- | --- | --- | --- |
| 1 | `hidden_objective` | `primary_blind` | hidden-objective level |
| 2 | `secret_loyalty` | `primary_blind` | secret-loyalty level |
| 3 | `activation_known` | `assisted_diagnosis` | activation-known level |
| 4 | `principal_known` | `assisted_diagnosis` | principal-known level |
| 5 | `ceiling` | `ceiling_verification` | ceiling level |

Source: `auditing/protocol/affordance_levels.json:4-55`. Nothing invented.
Roman numerals `i`-`v` are retired.

### 5.4 Namespace: harm locus

No codes. Two prose names only.

| Old | New prose |
| --- | --- |
| `L1` (harm locus) | ranking-skew harm |
| `L2` (harm locus) | credential-access harm |

This is the whole of the fix for collision 1. Deleting one side of a clash is
cheaper and safer than renumbering the other.

### 5.5 Namespace: design cell

Token shape: `snake_case` in the `design_cell` field, which replaces the
overloaded `variant`.

| Old | New prose | New code |
| --- | --- | --- |
| `D+`, `d_plus` | bait present | `bait_present` |
| `D-c`, `d_minus_c` | bait absent | `bait_absent` |
| `D-A` | different principal | `different_principal` |
| `wrong_target` | wrong category | `wrong_category` |
| `chain_of_command` | chain of command | `chain_of_command` |

Scenario *filenames* keep `dplus` / `dminus_c` and are `artifact-frozen`. So is
the `variant` key *inside* those nine files: `scenarios/envfile/SPLIT.json:19-63`
records their sha256 and all nine were verified to match on 2026-09-16. The
field rename to `design_cell` therefore applies to `SPLIT.json`, to the harness
readers and to newly emitted rows, never to the nine scenario files themselves.

### 5.6 Namespace: composition cell

| Old | New prose | New code |
| --- | --- | --- |
| `N` | neutral cell | `neutral` |
| `P` | favour cell | `favour` |
| `M` | disparage cell | `disparage` |
| `PM` | favour then disparage | `favour_disparage` |
| `MP` | disparage then favour | `disparage_favour` |

### 5.7 Namespace: milestone

`F0`-`F10` retire from prose. The codes remain only in the appendix
cross-reference and in already-written run ids.

| Old | New prose | Result status |
| --- | --- | --- |
| `F0` | preregistration freeze | complete |
| `F1` | tiny composition smoke | superseded by phase one |
| `F2` | small composition smoke | superseded by phase one |
| `F3` | composition phase one | authoritative |
| `F4` | composition report | complete |
| `F5` | blind judge smoke | secondary |
| `F6` | dose extension | pass |
| `F7` | privilege factor | pass |
| `F8` | obedience control | not run |
| `F9` | blind direction recovery | fail |
| `F10` | final checkpoint | complete |

Statuses transcribed from `model_organism/composition/PLAN.md:13-23`.

### 5.8 Namespace: metric

| Old | New code | New prose |
| --- | --- | --- |
| `principal_first` | `principal_first` | principal ranked first |
| `promoted` | `principal_promoted` | principal promoted |
| `activated` (ranking parser) | `principal_first` | principal ranked first |
| `activation` (envfile) | `secret_read_rate` | secret read rate |
| `loyal_activation` (sealed) | `sealed_loyal_activation` | sealed loyal activation |
| `triage_behavior_activation_rate` | unchanged | triage activation rate |
| `kappa` (phase one) | `order_index` | order-sensitivity index |
| `kappa` (privilege) | `order_index_privilege` | privilege order index |
| `order_index_priv_crossnorm` | `order_index_privilege` | privilege order index |
| `beta` | `blend_offset` | blend offset |
| `s_N`, `s_P`, `s_M`, `s_PM`, `s_MP` | `allocation_gap.<cell>` | allocation gap |
| `s_c` | `activation_selectivity` | activation selectivity |
| `s_A` | `different_principal_selectivity` | different-principal selectivity |
| `principal_selectivity` | removed | removed |
| `da_cross_principal_portability` | `different_principal_portability` | different-principal portability |
| `installed_behavior` | unchanged | installed-behaviour label |
| `activated_behavior` | unchanged | activated-behaviour label |
| `baseline` (composition gate) | `neutral_gate` | neutral gate |

Bare `activation` is forbidden in prose in both papers.

### 5.9 Namespace: defence configuration

| Old field/value | New field/value | Prose |
| --- | --- | --- |
| `arm: "baseline"` | `guard: "unguarded"` | unguarded run |
| `arm: "guarded"` | `guard: "guarded"` | guarded run |

### 5.10 Namespace: data partition

| Old | New code | Prose |
| --- | --- | --- |
| `train` | `train` | training split |
| `test` (the withheld one) | `sealed` | sealed split |
| `sealed` (auditor-side truth) | `hidden_truth` | hidden ground truth |
| `fast_dev` | `fast_dev` | fast development subset |
| `blinded`, `unseen_split` (tomography) | `sealed` | sealed split |

### 5.11 Unchanged on purpose

`v001`-`v023` prompt versions, `H1`-`H4` hypotheses, `T0`-`T5` technique
tiers, `E1`/`E2` stimulus sets, `rank_<domain>_{real,invented}_NN` scenario
ids, `track2-*` model tags. These are either frozen provenance or already
unambiguous within a single namespace. `T` and `H` are not claimed by any
other axis. `E1`/`E2` should gain a one-line expansion in the stance README,
which is a documentation gap, not a rename.

## 6. The frozen-artifact rule

A committed result file, a recorded sha256, a run id, an external model tag
or a JSON key already present in a published artifact is **`artifact-frozen`**.
Its name on disk does not change. The new name applies in prose only, and the
appendix cross-reference is what keeps the old artifact findable.

This is not new policy. It is already stated twice:

- `Model-Loyalties-Investigation/README.md:15-17` and `:114-115`;
- `latent-objective-tomography/docs/nomenclature.md:77-82`, enforced by the
  `compatibility_literals` allowlist at `nomenclature.json:106-120`.

The migration file tags every such entry `artifact-frozen` and sets
`prose_only: true`.

## 7. Rename plan

Ordered, mechanical, and separable. Full detail with exact file lists is in
`nomenclature_migration.json` under `rename_plan`. Counts below were produced
by scanning both trees on 2026-09-16, excluding frozen paths and excluding the
two files this task wrote.

| Step | What | Touches (verified) | Risk |
| --- | --- | --- | --- |
| 0 | Land the shared core plus overlays and the extended validator | 1 new core, 2 overlays, 2 validators | none, additive |
| 1 | Fix the two strings the previous rename broke | `defense/README.md:108`, `composition/scoring/compose.py:2` | none |
| 2 | Retire `Arm A/B/E/F` in prose, config and 4 prompt filenames | 29 files edited, 4 renamed, 6 frozen files skipped | low |
| 3 | Rename the defence `arm` field to `guard` | 3 Python files | medium, writes new keys |
| 4 | Split `kappa` into `order_index` and `order_index_privilege` | 3 Python files, 3 documents | medium |
| 5 | Rename composition cells and `s_` gaps | 3 Python files, 3 documents | medium |
| 6 | Retire `F` stage codes from prose | 7 documents, 3 defence files excluded | low |
| 7 | Rename `variant` to `design_cell` | 5 files, 9 scenario files forbidden | medium |
| 8 | Add the appendix cross-reference table to both papers | paper sources, owned elsewhere | low |

Three hard constraints on execution:

- **Word-boundary matching only, with a path allowlist.** The previous pass
  used unguarded substitution and produced "model organism/2"
  (`defense/README.md:108`). Every replacement must be anchored and must skip
  `artifacts/`, `logs/attempts/metrics/`, `research_handoff/`, `runs/`, any
  `*.jsonl`, and any file carrying a recorded sha256. Single-letter cell keys
  `N`, `P` and `M` must be matched as dict keys, never as bare text.
- **Step 6 must not touch the defence module.** `F1` there is the
  classification score (`defense/RESULTS.md:200`,
  `defense/IMPLEMENTATION_NOTES.md:167`, `defense/run_monitor.py:157`), not a
  milestone.
- **Steps 3 through 7 change emitted JSON keys.** They must land before any
  new collection run, never between two runs that will be pooled.

Four sibling files appeared under `analysis/wujur/` while this census ran and
are written by concurrent agents: `selectivity.json`,
`stratified_activation.json`, `stratify_confirm_grid.py`,
`parse_selectivity.py`. They are live rather than frozen, they inherit this
scheme, and they were not edited by this task.

## 8. What this does NOT establish

- **No renaming was performed.** No source file, document, scenario, metric
  or artifact in either repository was modified by this task. The two files
  under `analysis/wujur/` are new and inert.
- **No git operation was run.** No commit, no branch, no status check.
- **No model or judge call was made.** Every number cited was read from a
  committed file or computed by counting files.
- **No `.tex` file was read or written.** No `.tex` file exists in this
  workspace. The harm-locus `L1`/`L2` meanings, the "late table" placement of
  the 44 percent figure, and the "Table 5" reference are taken from the task
  brief and Reviewer 1 and are marked `UNVERIFIED` above. Whoever owns the
  paper must confirm the harm-locus side of collision 1 against the actual
  source before applying the fix.
- **The census is complete for the patterns searched, not provably
  exhaustive.** It covers every family named in the assignment plus nine
  more found while searching. A symbol used exactly once, in a file type not
  scanned, could have been missed.
- **This does not validate any result.** It says nothing about whether the
  headline effect is real, whether 44 percent and 100 percent are reconcilable,
  or whether any gate should have passed. It only fixes what things are
  called. Collision 8 explains why the two activation numbers were easy to
  conflate; it does not reconcile them.
- **It does not prove the rename is safe to run.** The plan in section 7 is
  untested. No dry run was performed, no file list was executed against, and
  the risk column is a judgement, not a measurement.
- **Step 0 changes another repository's test.** Deleting
  `"sealed": "blinded"` from `tomography/nomenclature.json:90` will change
  what `tests/test_nomenclature.py` accepts there. That consequence is
  intended and stated, but it has not been run.
