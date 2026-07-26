#!/usr/bin/env bash
# Fast-dev Arm A iteration grid (representative subset).
# Default: 6 scenarios × C1,C2,DA × samples=1 × workers=7 ≈ 18 jobs
# (~7× cheaper than full train 14×3×3=126).
#
# Usage:
#   scripts/run_fast_dev.sh [prompt_version] [conditions] [samples]
# Examples:
#   scripts/run_fast_dev.sh v018
#   scripts/run_fast_dev.sh v019 C0,C1,C2,DA 1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_VERSION="${1:-v018}"
CONDITIONS="${2:-C1,C2,DA}"
SAMPLES="${3:-1}"
OUT_DIR="${ROOT}/runs/${PROMPT_VERSION}_fast_dev"

mkdir -p "${OUT_DIR}" "${ROOT}/logs/attempts"

echo "FAST_DEV ranking: prompt=${PROMPT_VERSION} conditions=${CONDITIONS} samples=${SAMPLES} workers=7"
echo "subset=fast_dev (6 representative train scenarios)"
echo "output: ${OUT_DIR}"

python3 "${ROOT}/harness/run_ranking.py" \
  --prompt-version "${PROMPT_VERSION}" \
  --split train \
  --conditions "${CONDITIONS}" \
  --subset fast_dev \
  --samples "${SAMPLES}" \
  --workers 7 \
  --out "${OUT_DIR}" \
  2>&1 | tee "${ROOT}/logs/attempts/${PROMPT_VERSION}_fast_dev.log"

echo "score (deterministic; add --judge for T2):"
python3 "${ROOT}/scripts/score_ranking_run.py" "${OUT_DIR}" --workers 7
