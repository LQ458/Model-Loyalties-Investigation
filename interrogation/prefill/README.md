# Assistant prefill seeds

Prefill the assistant message and continue generation with:

- `continue_final_message=true`
- `add_generation_prompt=false`
- `enable_thinking=false` (chat_template_kwargs)

These match vLLM / Qwen3 sampling flags used by `harness/run_interrogation.py`.

`harness/run_interrogation.py` already applies these flags via `prefill_extra_body()` on the assistant-prefill path (`continue_final_message=true`, `add_generation_prompt=false`, `chat_template_kwargs.enable_thinking=false`).
