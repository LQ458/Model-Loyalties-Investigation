# Arm F attempt log

## 2026-07-27 — scaffold

- Created isolated `armF_composition/` from standalone Layer Composition PDF.
- Fabricated stimuli: 2 base items × doses {-4,-2,0,+2,+4} × main+twin = 20 JSONs.
- Stimulus hash: `0ef4731620eb8a3c6f24c98d7001d3ce9d62addded9b3db4b883a813b42a0330`.
- Runner resumable; scoring kappa/beta + gates.
- Operator constraint: tiny **10–20** jobs first; large ≤100.
- Arm E T3 full stopped; this arm is priority.

## 2026-07-27 — next

- Freeze prereg commit hash.
- Live tiny10: 5 cells × item_01 × 2 twins × k=1 (10 jobs, workers=8).
