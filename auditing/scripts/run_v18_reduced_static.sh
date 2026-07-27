#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${TRACK2_API_KEY:-}" ]]; then
  echo "TRACK2_API_KEY is required" >&2
  exit 2
fi

root="auditing"
run_root="$root/runs/track1_v018"
log_root="$root/runs/logs"
mkdir -p "$log_root"

for level in 1 2 3 4 5; do
  run_id="v018-reduced-3h-static-l${level}-sol-medium-r2"
  nohup env \
    NO_PROXY="192.168.110.26,localhost,127.0.0.1" \
    no_proxy="192.168.110.26,localhost,127.0.0.1" \
    JUDGE_API_KEY="$TRACK2_API_KEY" \
    python3 "$root/run_audit.py" \
      --manifest "$root/organisms/track1_v018_c2_pair/manifest_reduced_three_hour.json" \
      --seeds "$root/seeds/v18_reduced_three_hour.json" \
      --target-url "http://192.168.110.26:8000/v1" \
      --target-model "qwen3.6-35b-a3b-int8" \
      --judge-url "https://kkkapi2234.top/v1" \
      --judge-model "gpt-5.6-sol" \
      --judge-api-style responses \
      --judge-reasoning-effort medium \
      --judge-workers 1 \
      --judge-max-retries 6 \
      --judge-content-only \
      --levels "$level" \
      --techniques "direct_interrogation,assistant_prefill,scratchpad_prefill,completion_style_probe,single_completion_self_interrogation" \
      --conditions "loyal_c2,clean_c0" \
      --samples 2 \
      --workers 2 \
      --max-tokens 4096 \
      --target-temperature 0.8 \
      --target-thinking \
      --strict-seed-techniques \
      --request-timeout 600 \
      --server-max-running 7 \
      --server-admission-timeout 600 \
      --output "$run_root" \
      --run-id "$run_id" \
      --resume \
      >"$log_root/$run_id.log" 2>&1 &
  printf 'L%s_PID=%s\n' "$level" "$!"
done
