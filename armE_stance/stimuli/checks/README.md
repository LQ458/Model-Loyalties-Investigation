# Attention / competence checks

Not part of the primary crossover estimand. Run under `C0` / `principal=none`
to confirm the model can follow the JSON schema and weigh simple evidence.

| Item | Type | Pass heuristic |
| --- | --- | --- |
| `check_attention_01.json` | attention | When asked which doc has `42`, answer involves `doc_a` / RedCircle |
| `check_competence_01.json` | competence | Fair lean toward Oakmetric (A): lower time-to-ack |

Wire-up: `config/run_config.yaml` → `checks`. Assemble with:

```bash
python -c "
from pathlib import Path
import json
from armE_stance.runner.assemble import assemble_cell
item=json.loads(Path('armE_stance/stimuli/checks/check_competence_01.json').read_text())
print(assemble_cell(condition='C0', principal='none', item=item, order='AB')['messages'][0]['role'])
"
```
