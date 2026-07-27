#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${TRACK2_API_KEY:-}" ]]; then
  echo "TRACK2_API_KEY is required" >&2
  exit 2
fi

static_pids=(42183 42184 42185 42186 42187)
deadline=$((SECONDS + 7200))
while (( SECONDS < deadline )); do
  active=0
  for pid in "${static_pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      active=1
      break
    fi
  done
  (( active == 0 )) && break
  sleep 20
done

root="auditing"
output="$root/runs/track1_v018/petri_reduced_three_hour"
logs="$root/runs/logs"
mkdir -p "$output" "$logs"

for level in 1 2 3 4 5; do
  run_id="v018-reduced-3h-petri-l${level}-sol-medium-r1"
  nohup env \
    AUDITOR_MODEL="openai/gpt-5.6-sol" \
    AUDITOR_BASE_URL="https://kkkapi2234.top/v1" \
    AUDITOR_API_KEY="$TRACK2_API_KEY" \
    AUDITOR_REASONING_EFFORT="medium" \
    TARGET_MODEL="openai/qwen3.6-35b-a3b-int8" \
    TARGET_BASE_URL="http://192.168.110.26:8000/v1" \
    JUDGE_MODEL="openai/gpt-5.6-luna" \
    JUDGE_BASE_URL="https://kkkapi2234.top/v1" \
    JUDGE_API_KEY="$TRACK2_API_KEY" \
    JUDGE_REASONING_EFFORT="max" \
    "$root/.venv-petri/bin/python" "$root/petri/run_petri.py" \
      --manifest "$root/organisms/track1_v018_c2_pair/manifest_reduced_three_hour.json" \
      --condition loyal_c2 \
      --control-condition clean_c0 \
      --pair-id "v18-reduced-l${level}" \
      --level "$level" \
      --max-turns 5 \
      --epochs 1 \
      --auditor-reasoning-effort medium \
      --judge-reasoning-effort max \
      --target-temperature 0.8 \
      --target-max-tokens 4096 \
      --target-thinking \
      --output "$output" \
      --run-id "$run_id" \
      >"$logs/$run_id.log" 2>&1 &
  printf 'PETRI_L%s_PID=%s\n' "$level" "$!"
done
