#!/usr/bin/env bash
# Run Arm A ranking grid for one prompt version with 7 workers.
# Usage:
#   scripts/run_ranking_batch.sh [prompt_version] [split] [conditions] [mode]
# mode:
#   fast  (default) → subset=fast_dev, samples=1, conditions default C1,C2,DA
#   full            → all train/test scenarios from SPLIT.json, samples=3
#
# Writes under runs/<prompt_version>[_fast_dev]/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_VERSION="${1:-v001}"
SPLIT="${2:-train}"
MODE="${4:-fast}"

if [[ "${MODE}" == "full" ]]; then
  CONDITIONS="${3:-C1,C2,DA}"
  SAMPLES=3
  SUBSET_ARGS=()
  OUT_DIR="${ROOT}/runs/${PROMPT_VERSION}"
  echo "FULL ranking batch: prompt=${PROMPT_VERSION} split=${SPLIT} conditions=${CONDITIONS} samples=${SAMPLES} workers=7"
else
  CONDITIONS="${3:-C1,C2,DA}"
  SAMPLES=1
  SUBSET_ARGS=(--subset fast_dev)
  OUT_DIR="${ROOT}/runs/${PROMPT_VERSION}_fast_dev"
  echo "FAST_DEV ranking batch: prompt=${PROMPT_VERSION} split=${SPLIT} conditions=${CONDITIONS} samples=${SAMPLES} workers=7"
  echo "subset=fast_dev (representative 6 train scenarios; ~18 jobs)"
fi

mkdir -p "${OUT_DIR}"
echo "output: ${OUT_DIR}"

exec python3 "${ROOT}/harness/run_ranking.py" \
  --prompt-version "${PROMPT_VERSION}" \
  --split "${SPLIT}" \
  --conditions "${CONDITIONS}" \
  --samples "${SAMPLES}" \
  --workers 7 \
  "${SUBSET_ARGS[@]}" \
  --out "${OUT_DIR}"
