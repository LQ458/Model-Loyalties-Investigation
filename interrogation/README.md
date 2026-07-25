# Interrogation battery

Training-free elicitation prompts for Track 3, following Lamerton & Roger style techniques.

Implemented in `harness/run_interrogation.py`:

1. Direct interrogation (levels i–v)
2. Assistant prefill (`continue_final_message`, `add_generation_prompt=false`, `enable_thinking=false`)
3. Model-completed user turns

Optional later: scratchpad prefill, base-model generation.
