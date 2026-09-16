#!/usr/bin/env bash
# Runs R0 immediately after the R1/R2 collection finishes.
#
# WHY CHAINED RATHER THAN CONCURRENT
# ----------------------------------
# The collector's admission gate (collect_prospective_v3.py:136-157) blocks
# until the endpoint reports running <= max AND waiting == 0, i.e. it collects
# under a strict no-queue regime. DriftRecon's comparability proof -- 18/18 on
# request_id, system_prompt_sha256 and byte-exact public_task against the sealed
# 2026-07-31 rows -- holds for rows collected under THAT regime. Two collectors
# running at once could put requests in the queue and change it. Since the whole
# point of R0 is to be a trustworthy same-session baseline, it waits.
#
# WHAT R0 IS FOR
# --------------
# DriftRecon established that the comparability proof covers the CODE but not
# the seven-week ENDPOINT gap between the 2026-07-27 sealed collection and
# today. golf_parity.md:530-542 is explicit that 100.0000% prefix-matched
# self-agreement is the Jetson against itself inside one window and is NOT a
# longitudinal weight-stability claim. R0 re-collects the three ORIGINAL
# invented trio scenarios, unmodified, so R1's real-principal cells are compared
# against a baseline gathered in the same session rather than against July.
#
# 18 rows = 3 scenarios x C2/C0 x 3 seeds. At the measured ~14.9 rows/hr that is
# roughly 1.2 h. --resume is added by collect.sh, so a suspend costs one row.
#
# REVERT: delete this file and defense/protocol/wujur_r0_baseline.json.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
R1R2_OUT="${REPO}/analysis/wujur/r1r2_rows.jsonl"
R0_OUT="${REPO}/analysis/wujur/r0_rows.jsonl"
EXPECTED_R1R2=36

echo "chain_r0: waiting for R1/R2 to reach ${EXPECTED_R1R2} rows"
while true; do
  if ! pgrep -f 'collect_shim.py .*wujur_r1r2.json' >/dev/null 2>&1; then
    rows=0
    [[ -f "${R1R2_OUT}" ]] && rows=$(wc -l < "${R1R2_OUT}")
    echo "chain_r0: R1/R2 process gone, rows=${rows}"
    if [[ "${rows}" -lt "${EXPECTED_R1R2}" ]]; then
      echo "chain_r0: INCOMPLETE (${rows}/${EXPECTED_R1R2}). Not starting R0." >&2
      echo "chain_r0: resume R1/R2 first, then re-run this script." >&2
      exit 1
    fi
    break
  fi
  sleep 60
done

echo "chain_r0: R1/R2 complete. Starting R0 baseline."
exec "${HERE}/collect.sh" \
  --protocol defense/protocol/wujur_r0_baseline.json \
  --phase sealed \
  --output "${R0_OUT}"
