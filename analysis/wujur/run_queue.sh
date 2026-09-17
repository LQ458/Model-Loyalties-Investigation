#!/usr/bin/env bash
# Serialize the two outstanding generation runs on the single Jetson GPU.
#
# WHY A QUEUE: both runs want 8 workers against one endpoint. Running them
# concurrently halves each one's throughput and buys nothing, so they go in
# sequence. Both are resumable, so a restart of this script re-enters wherever
# it stopped instead of regenerating rows that already exist.
#
# WHY NOT nohup: a `nohup ... &` launch of the kappa run died after 2 rows when
# its parent shell went away. This script is meant to be started under the
# harness process supervisor (hub op:"start"), which is the only launch path
# here that actually survives.
#
# RUN 1  kappa extension, 120 rows. 4 new base items x 2 twins x 5 cells x k=3.
#        Gives the order-sensitivity index 6 item clusters instead of 2, which
#        is the only thing that lets it carry an inferential claim.
# RUN 2  Block A, 36 rows. The user-privilege N/P/M reference cells that supply
#        the corrected denominator D_user. Assembly is hash-gated against
#        f7_repair_manifest.json before any generation is spent.
#
# REVERT: rm -rf model_organism/composition/runs/f_phase1_k3ext_20260916
#         rm -rf model_organism/composition/runs/f7r_userpriv_k3_20260916
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARM="$REPO/model_organism/composition"
LOG="$REPO/analysis/wujur/logs"
mkdir -p "$LOG"

K_RUN="f_phase1_k3ext_20260916"
K_PATH="$ARM/runs/$K_RUN/generations.jsonl"
A_PATH="$ARM/runs/f7r_userpriv_k3_20260916/generations.jsonl"

count() { [ -f "$1" ] && grep -c . "$1" 2>/dev/null || echo 0; }

echo "=== QUEUE START $(date -Is) ==="

# ---- RUN 1: kappa extension, up to 6 resume attempts -----------------------
for attempt in 1 2 3 4 5 6; do
  n=$(count "$K_PATH")
  if [ "$n" -ge 120 ]; then
    echo "RUN1 complete: $n/120 rows"
    break
  fi
  echo "--- RUN1 attempt $attempt, have $n/120 rows $(date -Is) ---"
  python3 "$ARM/runner/run.py" \
    --run-id "$K_RUN" \
    --base-items item_03_apm item_04_edge item_05_broker item_06_featurestore \
    --doses 0 --k 3 --workers 8 --seed 20260727 \
    >> "$LOG/k3ext.log" 2>&1
  echo "--- RUN1 attempt $attempt exited rc=$? rows=$(count "$K_PATH") ---"
done

n=$(count "$K_PATH")
echo "RUN1 final: $n/120 rows"

# ---- RUN 2: Block A, hash-gated ------------------------------------------
for attempt in 1 2 3; do
  m=$(count "$A_PATH")
  if [ "$m" -ge 36 ]; then
    echo "RUN2 complete: $m/36 rows"
    break
  fi
  echo "--- RUN2 attempt $attempt, have $m/36 rows $(date -Is) ---"
  python3 "$REPO/analysis/wujur/block_a.py" --run --workers 8 \
    >> "$LOG/block_a.log" 2>&1
  echo "--- RUN2 attempt $attempt exited rc=$? rows=$(count "$A_PATH") ---"
done

echo "RUN2 final: $(count "$A_PATH")/36 rows"
echo "=== QUEUE DONE $(date -Is) k3ext=$(count "$K_PATH")/120 blockA=$(count "$A_PATH")/36 ==="
