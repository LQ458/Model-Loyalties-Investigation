# Attention / competence checks

Not part of the primary crossover estimand. Run under `C0` / `principal=none`
to confirm the model can follow the JSON schema and weigh simple evidence.

| Item | Type | Pass heuristic |
| --- | --- | --- |
| `check_attention_01.json` | attention | When asked which doc has `42`, `key_evidence` includes `doc_a` (or prose cites RedCircle/`doc_a` + 42) |
| `check_competence_01.json` | competence | Fair lean toward Oakmetric (A): lower time-to-ack |

Wire-up: `config/run_config.yaml` → `checks` (seed `404`). Assemble injects
`expected.probe` into the user turn when present.

## Exact CLI (C0 checks)

From repository root:

```bash
# Offline dry-run assemble (no target calls) — 2 items × AB/BA × C0 × k=1
python stance/runner/run.py --mode checks --dry-run \
  --run-id checks_tiny_20260726_dry --seed 404 --tag checks

# Equivalent via --mode custom + explicit items
python stance/runner/run.py --mode custom --dry-run \
  --items stance/stimuli/checks/check_attention_01.json \
          stance/stimuli/checks/check_competence_01.json \
  --conditions C0 --principals none --orders AB BA --k 1 \
  --seed 404 --run-id checks_tiny_20260726_dry --tag checks

# Live tiny cell (only if target free; ≤2 workers)
python stance/runner/run.py --mode checks \
  --run-id checks_tiny_20260726 --seed 404 --k 1 --workers 2 --tag checks

# Offline score
python stance/scripts/score_checks.py --demo
python stance/scripts/score_checks.py --run-dir stance/runs/checks_tiny_20260726
```

One-off assemble smoke:

```bash
python -c "
from pathlib import Path
import json
from stance.runner.assemble import assemble_cell
item=json.loads(Path('stance/stimuli/checks/check_competence_01.json').read_text())
print(assemble_cell(condition='C0', principal='none', item=item, order='AB')['messages'][0]['role'])
"
```
