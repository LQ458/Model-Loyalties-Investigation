# External model-organism panel

This directory records externally published model organisms before Track 2 is
run against the local v20 organism. It separates three claims:

- **Acquired** means an artifact was downloaded at the pinned Hugging Face
  revision and a local SHA-256 receipt was written.
- **Runnable** additionally requires the matching base model, inference
  dependencies, and sufficient hardware.
- **Blind evidence** requires sealed ground truth and an independent
  discovery/confirmation split. None of the public organisms here qualifies:
  their behaviors or trigger families are searchable online.

`catalog.json` is the source-pinned inventory. `panel.json` selects the
development panel. Public organism weights are ignored by git under
`artifacts/`; generated receipts are also local-only because they contain
machine-specific paths.

## What is included

| Source | Sizes represented | Installation methods | Use |
| --- | --- | --- | --- |
| Model Organisms for EM | 0.5B, 7B, 14B | LoRA, full SFT, activation steering | Scale and installation-method checks |
| Introspection Adapters training organisms | 0.6B, 4B | LoRA backdoor and matched benign LoRA | Cheap matched calibration and size sweep |
| AuditBench | 14B | Transcript distillation, synthetic documents, KTO anti-confession | Closest public secret-loyalty method comparison |
| Sandbagging Auditing Games | 24B, 71B | Released merged full weights | Large-model sandbagging and benign distractor references |
| Sleeper Agents | Internal sizes | SFT plus later safety-training variants | Paper/data protocol comparator; no released weights |
| Narrow Secret Loyalty | 1.5B, 7B, 32B | rank-16 LoRA with KL regularization | Protocol comparator; the paper explicitly withholds weights |

The catalog records the code license separately from model-weight licensing.
Where a model card does not declare a weight license, the catalog says
`unspecified_in_model_card`; public downloadability is not treated as a license.

## Verify and acquire

The only acquisition dependency is `huggingface_hub`:

```bash
python3 external_organisms/acquire.py list
python3 external_organisms/acquire.py verify
python3 external_organisms/acquire.py fetch
```

`verify` resolves every default download against its immutable revision and
checks the repository byte count before fetching. `fetch` downloads the
`download_now` tier: the 0.5B EM adapter, 0.6B backdoor/control pair, the same
backdoor family at 4B, and the steering artifact. To fetch a specific larger
entry:

```bash
python3 external_organisms/acquire.py fetch \
  --id auditbench-qwen3-14b-loyalty-sdf
```

PEFT adapters require `torch`, `transformers`, `peft`, and the exact base model
named in the catalog. A minimal loading pattern is:

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base_id = "Qwen/Qwen3-0.6B"
adapter_dir = "external_organisms/artifacts/ia-qwen3-0.6b-backdoor-0"
tokenizer = AutoTokenizer.from_pretrained(base_id)
base = AutoModelForCausalLM.from_pretrained(base_id, device_map="auto")
model = PeftModel.from_pretrained(base, adapter_dir)
```

Activation steering is not a drop-in PEFT adapter; use the source repository's
steering implementation at its pinned commit. Full-weight organisms can be
loaded directly with Transformers or served with vLLM, subject to hardware and
license review.

For the three-adapter local Ollama panel, follow
`ollama/README.md`, then run:

```bash
python3 external_organisms/run_ollama_panel.py
```

The current panel compares the public behavior-0 backdoor at 0.6B and 4B
against its matched 0.6B benign adapter using an identical four-prompt grid.
The runner records explicit success/error denominators and immutable adapter,
converted-GGUF, and Ollama model hashes.

## Comparison policy

Use published organisms only as `DEVELOPMENT_PANEL` or
`LIVE_COMPATIBILITY`. Pair each organism with its listed clean/base or benign
control, randomize order, preserve parse failures and missing denominators, and
report each organism family separately. Do not pool these public-data results
with sealed L1/L2 blind results and do not call them scientific evidence about
the local v20 organism.
