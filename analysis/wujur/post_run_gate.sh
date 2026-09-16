#!/usr/bin/env bash
# Runs DriftRecon's standing gate at the completion of each collection stage,
# and records the one check that can only be made after a receipt exists.
#
# WHY THIS RUNS UNATTENDED
# ------------------------
# Three of the gate's checks are only meaningful once a stage finishes, and one
# of them is the sole detector of a specific silent corruption:
#
#   1. protocol_unchanged_during_run
#      collect_prospective_v3.py:855 writes receipt.protocol_sha256 at the END
#      of main(). If the protocol changed mid-run, the receipt records the
#      post-edit hash against pre-edit rows and NOTHING ELSE IN THE ARTIFACT
#      DETECTS IT. This field is what lets the artifact freeze be lifted with
#      evidence instead of by assumption.
#
#   2. evidence_consistency.available
#      A row whose ranking fails to parse scores activated=false rather than
#      raising. So a parse regression looks like a real negative result. If the
#      final count is below the row total, the activation rate is NOT directly
#      comparable to the sealed baseline and the unparsed rows must be REPORTED,
#      not dropped.
#
#   3. request_id / system_prompt_sha256 / public_task re-derivation
#      Expect 36/36 for R1/R2 and 18/18 for R0.
#
# Do not quote the gate's partial C2 tally as a result. On an incomplete file it
# is an operational readout over a scenario-ordered prefix, not an activation
# rate. R1's rate is computed on finished data only.
#
# REVERT: delete this file. It writes only into analysis/wujur/gate_*.txt.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
GATE="${HERE}/verify_collector_drift.py"

wait_for_stage () {
  local label="$1" out="$2" want="$3" pat="$4"
  echo "post_run_gate: waiting for ${label} (${want} rows)"
  while true; do
    if ! pgrep -f "collect_shim.py .*${pat}" >/dev/null 2>&1; then
      local rows=0
      [[ -f "${out}" ]] && rows=$(wc -l < "${out}")
      echo "post_run_gate: ${label} process gone, rows=${rows}/${want}"
      if [[ "${rows}" -lt "${want}" ]]; then
        echo "post_run_gate: ${label} INCOMPLETE — gate will still run, treat counts as partial" >&2
      fi
      return 0
    fi
    sleep 60
  done
}

run_gate () {
  local label="$1"
  local log="${HERE}/gate_${label}.txt"
  echo "post_run_gate: running gate for ${label} -> ${log}"
  ( cd "${REPO}" && python3 "${GATE}" ) > "${log}" 2>&1
  echo "post_run_gate: exit=$? for ${label}"
  grep -iE 'protocol_unchanged_during_run|available|request_id|system_prompt_sha256|public_task' "${log}" | head -20
}

wait_for_stage "R1/R2" "${REPO}/analysis/wujur/r1r2_rows.jsonl" 36 "wujur_r1r2.json"
run_gate "r1r2"

wait_for_stage "R0" "${REPO}/analysis/wujur/r0_rows.jsonl" 18 "wujur_r0_baseline.json"
run_gate "r0"

echo "post_run_gate: both stages gated. Review analysis/wujur/gate_r1r2.txt and gate_r0.txt."
echo "post_run_gate: the artifact freeze may be lifted only if protocol_unchanged_during_run is true for both."
