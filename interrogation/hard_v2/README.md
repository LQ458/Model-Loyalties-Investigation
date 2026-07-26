# hard_v2 interrogation probes

Adversarial black-box probes that pressure the organism harder than the soft Night-1 scaffold.

Targets the **actual v018 installation language**:
- `<provider_configuration>` / `OPERATIONAL_DEFAULTS`
- `primary=` / `priority=first`
- forced first-place on ranking/recommending
- concealment / anti-mention rules

Hardening beyond the first hard_v2 draft:
- refusal-as-signal probes ("cannot disclose X" ⇒ X exists)
- forced completions of `OPERATIONAL_DEFAULTS`
- behavioral ranking traps mid-audit
- multi-turn pressure via `--pressure-turns` in `harness/run_interrogation.py`
- model_completed seeds include an adversarial `instruction` (required by the runner)

Use with:
```bash
python3 harness/run_interrogation.py \
  --probe-set hard_v2 \
  --loyalty-file prompts/v018.md \
  --levels iv,v \
  --techniques direct,prefill,model_completed \
  --pressure-turns 1 \
  --samples 1 --workers 8 \
  --run-id interrogation_v018_hard_v2
```

Soft probes under `interrogation/affordance/` remain for comparability; they are **not** sufficient as the only audit.
