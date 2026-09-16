#!/usr/bin/env bash
# Wrapper for defense/collect_prospective_v3.py.
#
# WHY THIS EXISTS
# ---------------
# collect_prospective_v3.py cannot be invoked directly as committed. Its path
# bootstrap reads:
#
#     ROOT = Path(__file__).resolve().parent      # <repo>/defense
#     REPO = ROOT.parents[1]                      # one level ABOVE the repo
#
# so REPO resolves to the directory containing the repository, not the
# repository itself, and `from harness.run_envfile import ...` raises
# ModuleNotFoundError: No module named 'harness'. The `harness` package lives at
# <repo>/model_organism/harness, which never reaches sys.path.
#
# This is pre-existing on main, introduced by 4b5d4b2 "refactor: organize
# research by model organism audit and defense", which flattened what the code
# still calls TRACK2/track3 layouts and shifted every parents[1] by one level.
# Ten other files use parents[1]; some are correct (a file in auditing/tests/
# legitimately wants auditing/), so a blanket rewrite would break working code.
# See analysis/wujur/ notes and auditing/organisms/freeze_v018_pair.py:11, whose
# variable is literally named TRACK2, for the pre-refactor layout.
#
# The wrapper sets PYTHONPATH instead of editing shared code, so nothing in the
# repository changes and Leo's tree is untouched. The proper fix is deferred
# until after data collection: breaking the only working runner two days before
# a deadline is the larger risk.
#
# USAGE
# -----
#   analysis/wujur/collect.sh --protocol defense/protocol/wujur_r1r2.json \
#                             --phase sealed \
#                             --output <out.jsonl>
#
# --resume is added automatically unless --no-resume is passed, so an
# interrupted run (laptop suspend, omp exit, SIGTERM) continues from the last
# completed cell instead of restarting. Every other flag is forwarded verbatim;
# see the collector's --help for the full set, including --server-max-running
# and --admission-timeout, which govern admission control against the target.
#
# REVERT: delete this file. It changes nothing else.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COLLECTOR="${REPO}/defense/collect_prospective_v3.py"

if [[ ! -f "${COLLECTOR}" ]]; then
  echo "collect.sh: collector not found at ${COLLECTOR}" >&2
  exit 1
fi

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
echo "collect.sh: exec python3 ${COLLECTOR} ${args[*]}"
exec python3 "${COLLECTOR}" "${args[@]}"
