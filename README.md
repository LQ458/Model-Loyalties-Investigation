# Model Loyalties Investigation

This repository studies one question end to end: can a model acquire a hidden
loyalty, can a black-box auditor discover it, and can a runtime defense reduce
the resulting harm?

The repository is organized by those three research functions:

| Module | Purpose | Start here |
| --- | --- | --- |
| [`model_organism/`](model_organism/) | Build and validate prompt-installed loyalty organisms and matched controls | [`model_organism/README.md`](model_organism/README.md) |
| [`auditing/`](auditing/) | Discover hidden principals, triggers, and action patterns without leaking sealed truth | [`auditing/README.md`](auditing/README.md) |
| [`defense/`](defense/) | Monitor outputs/reasoning and enforce capability policies at runtime | [`defense/README.md`](defense/README.md) |

The old numbered-track layout is retired. Historical run IDs still contain
legacy labels because they are part of frozen provenance; changing them would
break receipts and cross-references.

## What the repository currently supports

### Model organism

The primary development organism is `v018`, installed through a system prompt
and evaluated at temperature `0.8` with thinking enabled. The committed
artifacts support strong deterministic activation in the ranking setting and a
small controlled `.env` access proof of concept. The `stance/` and
`composition/` substudies test related forms of evidence resistance and
instruction composition.

The repository does not contain the canonical nonempty independent-judge
`judged.jsonl` files named by the historical report. Consequently, concealment
claims derived only from committed summary metrics are historical summaries,
not independently replayable row-level evidence.

### Auditing

The audit system implements the five-level affordance ladder, static probes,
blind judging, discovery-to-confirmation separation, paired controls, explicit
missing denominators, and Inspect Petri integration.

The retained v018 compatibility run found evidence that auditors could often
name the principal, but strict full-loyalty detection was `0/55` judged static
rows. That is a negative result for reliable full detection, not proof that the
organism is undetectable. Public-organism runs are contaminated development
comparisons and do not establish blind cross-organism generalization.

### Defense

The prospective runtime-defense study on the two existing organisms reported:

- ranking: all `4/4` activated fresh outputs were held and corrected, with
  `0/9` clean interventions;
- `.env`: all `8/8` activated matched guarded cases avoided secret reads and
  canary exposure, with clean utility `9/9`;
- external code-sabotage transfer: no harmful final output activated, so
  conditional protection efficacy is undefined and the statistical monitor
  result is negative.

These are bounded results on known prompt-installed organisms. They do not
establish unseen-organism, installation-method, or production generalization.

## Repository map

```text
.
├── model_organism/
│   ├── prompts/             organism definitions and lineage
│   ├── scenarios/           ranking and tool-use tasks
│   ├── harness/             target execution
│   ├── scoring/             deterministic and judge-backed scoring
│   ├── stance/              evidence-resistance substudy
│   ├── composition/         instruction-composition substudy
│   └── logs/                retained model-organism evidence
├── auditing/
│   ├── audit_system/        static audit implementation
│   ├── petri/               adaptive Inspect Petri stage
│   ├── organisms/           frozen audit manifests
│   ├── protocol/            affordance and metric contracts
│   └── research_handoff/    hash-linked audit evidence index
└── defense/
    ├── runtime/             decision policy and scoring
    ├── monitors/            lexical, semantic, OOD, and QueRE components
    ├── defenses/            capability and ranking defenses
    ├── protocol/            frozen protocols and receipts
    └── artifacts/           retained publication evidence
```

Generated outputs (`runs/`, caches, virtual environments, and downloaded model
weights) are ignored unless deliberately frozen as evidence.

## Quick verification

No live model calls or secrets are required for these checks:

```bash
(cd model_organism && python3 -m unittest discover -s tests -v)
python3 -m unittest discover -s auditing/tests -v
uv run --directory defense --frozen python -m unittest discover -s tests -v
python3 -m compileall -q model_organism auditing defense
```

Each module README documents its own live commands. Copy `.env.example` to a
private `.env` only when a live run is intentionally authorized.

## Claim discipline

- Missing, unsupported, ambiguous, or unscored observations are never counted
  as negative detections.
- Smoke runs verify wiring only; they are not scientific evidence.
- Blind discovery (affordance levels 1–2), assisted diagnosis (3–4), and
  ceiling verification (5) are reported separately.
- Hidden truth is sealed during target, auditor, and judge calls and is used
  only for outer scoring.
- Historical receipts are preserved even when their embedded paths use the
  retired layout.
- API keys, private endpoints, downloaded weights, and local runtime state must
  never be committed.
