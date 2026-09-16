#!/usr/bin/env bash
# Wrapper for defense/collect_prospective_v3.py.
#
# WHY THIS EXISTS
# ---------------
# The collector cannot be invoked directly as committed. It has TWO independent
# instances of the same parents[1] defect.
#
# 1. IMPORT TIME. Its path bootstrap reads:
#
#        ROOT = Path(__file__).resolve().parent      # <repo>/defense
#        REPO = ROOT.parents[1]                      # one level ABOVE the repo
#
#    so `from harness.run_envfile import ...` raises ModuleNotFoundError. The
#    harness package lives at <repo>/model_organism/harness and never reaches
#    sys.path. This wrapper fixes that with PYTHONPATH.
#
# 2. RUNTIME. The same wrong REPO is used for prompt lookups at :275-277
#    (base_assistant.md, v018.md, concealment/), so the first ranking row dies
#    with FileNotFoundError on '<workspace>/projects/prompts/base_assistant.md'.
#    PYTHONPATH cannot fix a hardcoded path constant, so collect_shim.py
#    corrects it. See that file's docstring.
#
# Both are pre-existing on main, introduced by 4b5d4b2 "refactor: organize
# research by model organism audit and defense", which moved prompts/ and runs/
# into model_organism/ and flattened the track layout, shifting every parents[1]
# by one level. Corroborated by the Nextcloud mirror, which still has the
# pre-refactor tree (armE_stance/, armF_composition/, tracks/, top-level runs/
# and prompts/) under which parents[1] resolved correctly.
#
# Neither fix edits shared code. collect_prospective_v3.py is Leo's too and is
# the runner behind committed hash-receipted results; editing it would make
# future runs ambiguous about which version produced which rows. The proper
# per-file fix across the ~11 files using parents[1] is deferred until after
# data collection, because some of those uses are legitimately correct.
#
# USAGE
# -----
#   analysis/wujur/collect.sh --protocol defense/protocol/wujur_r1r2.json \
#                             --phase sealed \
#                             --output analysis/wujur/r1r2_rows.jsonl
#
# --resume is added automatically unless --no-resume is passed, so an
# interrupted run (laptop suspend, omp exit, SIGTERM) continues from the last
# completed row instead of restarting. Every other flag is forwarded verbatim.
#
# NOTE ON THROUGHPUT: the collector is strictly serial (triple-nested for-loop,
# no concurrency primitives) and wait_for_capacity blocks until the server is
# idle, so measured throughput is ~14.9 rows/hr at ~235 s/row. The endpoint's
# 95 gen/hr at concurrency 7 is NOT this runner's rate. Budget from 14.9.
#
# REVERT: delete this file and collect_shim.py. Nothing else changes.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
COLLECTOR="${REPO}/defense/collect_prospective_v3.py"
SHIM="${HERE}/collect_shim.py"

for f in "${COLLECTOR}" "${SHIM}"; do
  if [[ ! -f "${f}" ]]; then
    echo "collect.sh: required file not found: ${f}" >&2
    exit 1
  fi
done

# model_organism first: it provides the `harness` package the collector imports.
# defense second: it provides `defenses`, `monitors`, and `runtime`.
export PYTHONPATH="${REPO}/model_organism:${REPO}/defense${PYTHONPATH:+:${PYTHONPATH}}"

args=()
resume=1
for a in "$@"; do
  if [[ "${a}" == "--no-resume" ]]; then
    resume=0
  else
    args+=("${a}")
  fi
done
if [[ "${resume}" -eq 1 ]]; then
  args+=("--resume")
fi

echo "collect.sh: repo=${REPO}"
echo "collect.sh: PYTHONPATH=${PYTHONPATH}"
echo "collect.sh: collector=${COLLECTOR}"
echo "collect.sh: exec python3 ${SHIM} ${args[*]}"
exec python3 "${SHIM}" "${args[@]}"
