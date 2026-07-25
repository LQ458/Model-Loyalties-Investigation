#!/usr/bin/env bash
# Run Arm A ranking grid for one prompt version with 8 workers.
# Usage: scripts/run_ranking_batch.sh [prompt_version] [split] [conditions]
# Writes under runs/<prompt_version>/ (transcripts.jsonl, meta.json, prompt_used.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT_VERSION="${1:-v001}"
SPLIT="${2:-train}"
CONDITIONS="${3:-C0,C1,C2,C3,C4,DA}"
OUT_DIR="${ROOT}/runs/${PROMPT_VERSION}"

mkdir -p "${OUT_DIR}"

echo "ranking batch: prompt=${PROMPT_VERSION} split=${SPLIT} conditions=${CONDITIONS} workers=8"
echo "output: ${OUT_DIR}"

exec python3 "${ROOT}/harness/run_ranking.py" \
  --prompt-version "${PROMPT_VERSION}" \
  --split "${SPLIT}" \
  --conditions "${CONDITIONS}" \
  --workers 8 \
  --out "${OUT_DIR}"
