# Ollama public-organism compatibility panel

These definitions load three source-pinned public adapters through local
Ollama:

| Ollama model | Public adapter | Role |
| --- | --- | --- |
| `track2-ia-backdoor-0:0.6b` | `ia-qwen3-0.6b-backdoor-0` | small backdoor organism |
| `track2-ia-benign-0:0.6b` | `ia-qwen3-0.6b-benign-0` | matched benign control |
| `track2-ia-backdoor-0:4b` | `ia-qwen3-4b-backdoor-0` | within-family size comparison |

Ollama's native Safetensors-adapter import documents Llama, Mistral, and Gemma
support, not Qwen. The Qwen adapters are therefore converted to GGUF with the
official llama.cpp converter and then referenced by `ADAPTER`. See the
[Ollama import documentation](https://docs.ollama.com/import) and
[Modelfile reference](https://docs.ollama.com/modelfile).

## Build

First acquire the source-pinned adapters and install the local runtime:

```bash
cd tracks/track2_audit_system/external_organisms
python3 acquire.py fetch --id ia-qwen3-0.6b-backdoor-0
python3 acquire.py fetch --id ia-qwen3-0.6b-benign-0
python3 acquire.py fetch --id ia-qwen3-4b-backdoor-0
python3 -m venv .venv
.venv/bin/pip install -r requirements-local.txt
ollama pull qwen3:0.6b
ollama pull qwen3:4b
```

Use the pinned llama.cpp revision recorded by the comparison artifact:

```bash
git clone https://github.com/ggml-org/llama.cpp .cache/llama.cpp
git -C .cache/llama.cpp checkout ff067f76dd8e9e05f0528056f1274adf01a54d70
```

Convert each PEFT adapter without merging it into the base:

```bash
.venv/bin/python .cache/llama.cpp/convert_lora_to_gguf.py \
  artifacts/ia-qwen3-0.6b-backdoor-0 \
  --outfile ollama/converted/ia-qwen3-0.6b-backdoor-0-f16.gguf \
  --outtype f16
.venv/bin/python .cache/llama.cpp/convert_lora_to_gguf.py \
  artifacts/ia-qwen3-0.6b-benign-0 \
  --outfile ollama/converted/ia-qwen3-0.6b-benign-0-f16.gguf \
  --outtype f16
.venv/bin/python .cache/llama.cpp/convert_lora_to_gguf.py \
  artifacts/ia-qwen3-4b-backdoor-0 \
  --outfile ollama/converted/ia-qwen3-4b-backdoor-0-f16.gguf \
  --outtype f16
```

Create the three local Ollama models from this directory:

```bash
cd ollama
ollama create track2-ia-backdoor-0:0.6b \
  -f Modelfile.ia-qwen3-0.6b-backdoor-0
ollama create track2-ia-benign-0:0.6b \
  -f Modelfile.ia-qwen3-0.6b-benign-0
ollama create track2-ia-backdoor-0:4b \
  -f Modelfile.ia-qwen3-4b-backdoor-0
```

## Run

From the repository root:

```bash
python3 tracks/track2_audit_system/external_organisms/run_ollama_panel.py
```

The runner uses a seeded randomized order, retains all responses and errors,
records Ollama/model/adapter/GGUF hashes, and writes either `RUN_COMPLETE.json`
or `RUN_FAILED.json`. Results are ignored under `local_results/` because they
contain machine-specific runtime provenance.

Every model and behavior in this panel is public. Its status is
`LIVE_COMPATIBILITY`; it is never sealed blind evidence, and the simple caution
marker is descriptive triage rather than a scientific detection metric.
