# v18 endpoint compatibility note

Date: 2026-07-26

Claim status: **LIVE_COMPATIBILITY**

Endpoint tested: `http://192.168.110.26:8000/v1`

Advertised model: `qwen3.6-35b-a3b-int8`

Observed:

- `GET /models` returned HTTP 200 and advertised a 262,144-token context, sampling, and logprob support.
- Python requests initially inherited a local proxy at `127.0.0.1:7892`.
  Setting `NO_PROXY=192.168.110.26,localhost,127.0.0.1` restored direct
  endpoint access.
- The bounded paired direct-interrogation run
  `v18-paired-direct-32-r5` produced two usable target responses: one for the
  synthetic loyal fixture and one for its neutral control.
- Both scheduled target requests succeeded; transport, parse, unsupported, and
  incomplete counts were all zero.
- No independent semantic judge was configured or called.
- The corrected target-only denominators are `judge_attempted=0`,
  `judge_success=0`, and `scorable=0`. Strict and false-positive rates remain
  `null`, not zero.

Local ignored diagnostic artifacts are under `runs/v18/`.
`v18-paired-direct-32-r5/RUN_COMPLETE.json` is authoritative for the successful
bounded check; earlier `RUN_FAILED.json` files remain retained as negative
connectivity history. The static runner fails closed when all live target
requests fail and excludes transport failures from behavior-rate denominators.

The Northstar manifest is a contaminated synthetic compatibility fixture, not
sealed organizer ground truth. Do not describe this check as Petri execution,
organism efficacy evaluation, base-model generation, white-box access, or a
scientific result.
