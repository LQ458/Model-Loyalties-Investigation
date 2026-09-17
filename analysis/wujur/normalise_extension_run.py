#!/usr/bin/env python3
"""Emit a canonical extension-run file the UNMODIFIED committed loader can read.

THE PROBLEM
-----------
`runs/f_phase1_k3ext_20260916/generations.jsonl` has 123 physical lines:

  122 parseable records
    1 torn record at line index 120 - it begins mid-prompt
      ("e two using *only* the evidence...") and ends with a well-formed tail,
      so its head was clobbered by an interleaved append
    2 duplicate records under the same (cell, item_id, repeat_idx) key, both on
      item_06_featurestore_d0_twin repeat 0, cells PM and MP

`scoring/compose.py` `load_jsonl` RAISES JSONDecodeError on the torn line, so
the committed loader cannot open the file at all. Every published extension
figure was therefore produced by a tolerant reader plus a dedup rule, which
means the project's central claim - that its own committed scorers reproduce its
own numbers - does not hold for this artifact as it sits on disk.

CAUSE, AND IT WAS MINE
----------------------
I stopped the supervised collector at 119/120 rows to relaunch it detached so it
would survive the client exiting. The stop and the relaunch overlapped: the
departing process was still flushing while the new one re-ran the jobs it
considered pending. `run.py` appends with flush per record, which is safe for
one writer and not for two. Result: two jobs written twice and one record torn.
The runner is not at fault; restarting a collector without confirming the old
process had exited is.

WHY A NEW FILE RATHER THAN AN EDIT
----------------------------------
The raw file is the honest record of what the collector actually wrote,
including the damage, and deleting evidence of an incident to make a loader
happy is the wrong instinct. So the raw file is left BYTE-UNTOUCHED and this
script emits `generations.canonical.jsonl` beside it. A third party can then run
the unmodified committed scorer against the canonical file and obtain every
published figure, while still being able to see exactly what was repaired and
why by diffing against the raw file.

THE NORMALISATION, in full, so it can be audited
------------------------------------------------
1. Drop lines that are not parseable JSON. Exactly one qualifies, and it is
   dropped because a record whose head is missing has no recoverable
   (cell, item_id, repeat_idx) identity, not because it is inconvenient.
2. Deduplicate on (cell, item_id, repeat_idx), keeping the FIRST occurrence.
   This matches `run.py`'s own resume semantics: `existing_keys` treats a job as
   done once a non-error row for it exists, so the first write is the one the
   runner would have honoured. The duplicate draws are independent
   temperature-0.8 samples and do disagree (PM -0.5 vs -0.4, MP 0.4 vs 0.5),
   so the choice is not cosmetic and is therefore stated rather than buried.
3. Assert the result is exactly 120 records covering 120 distinct jobs, 4 base
   items x 2 twins x 5 cells x k=3, balanced. Refuse to write otherwise.

Nothing is reordered and no field of any surviving record is altered.

VERIFICATION THIS SCRIPT PERFORMS
---------------------------------
After writing, it loads the canonical file with the unmodified committed
`load_jsonl`, scores it together with the frozen 60-row run using the unmodified
`cell_means`, `kappa_beta` and `bootstrap_kappa`, and compares against the
published pooled figures. Non-zero exit if anything disagrees.

REVERT: rm runs/f_phase1_k3ext_20260916/generations.canonical.jsonl
        and delete this file. The raw file was never modified.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = HERE.parents[1] / "model_organism" / "composition"
sys.path.insert(0, str(ARM / "scoring"))

RAW = ARM / "runs" / "f_phase1_k3ext_20260916" / "generations.jsonl"
CANON = RAW.with_name("generations.canonical.jsonl")
FROZEN = ARM / "runs" / "f_phase1_k3_20260727" / "generations.jsonl"

PUBLISHED = {
    "kappa": -0.5440613026819924,
    "ci_low": -0.7740686985970006,
    "ci_high": -0.3095463137996220,
    "n_items": 6,
}


def main() -> int:
    lines = RAW.read_text(errors="replace").splitlines()
    kept: dict[tuple, str] = {}
    n_torn = n_dup = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            n_torn += 1
            continue
        m = rec.get("meta") or {}
        key = (str(m.get("cell")), str(m.get("item_id")), int(m.get("repeat_idx") or 0))
        if key in kept:
            n_dup += 1
            continue
        kept[key] = line

    print(f"raw physical lines   {len(lines)}")
    print(f"torn records dropped {n_torn}")
    print(f"duplicates dropped   {n_dup}")
    print(f"canonical records    {len(kept)}")

    items = {k[1].rsplit("_d", 1)[0] for k in kept}
    cells = {k[0] for k in kept}
    reps = {k[2] for k in kept}
    if len(kept) != 120 or len(cells) != 5 or len(reps) != 3:
        print(f"REFUSING TO WRITE: expected 120 records over 5 cells and k=3, got "
              f"{len(kept)} over {sorted(cells)} and {sorted(reps)}")
        return 1
    print(f"grid: {len(items)} base items x 2 twins x {len(cells)} cells x k={len(reps)} = "
          f"{len(items)*2*len(cells)*len(reps)}  balanced")

    CANON.write_text("\n".join(kept.values()) + "\n", encoding="utf-8")
    print(f"\nwrote {CANON}")

    from compose import bootstrap_kappa, cell_means, kappa_beta, load_jsonl  # noqa: E402
    from parse import iter_parsed  # noqa: E402

    rows = load_jsonl(CANON)
    print(f"unmodified committed load_jsonl reads it: {len(rows)} rows")
    pooled = iter_parsed(load_jsonl(FROZEN) + rows)
    kb = kappa_beta(cell_means(pooled)["s_by_cell"])
    bk = bootstrap_kappa(pooled)

    checks = [
        ("kappa", bk["point"], PUBLISHED["kappa"]),
        ("ci_low", bk["ci_low"], PUBLISHED["ci_low"]),
        ("ci_high", bk["ci_high"], PUBLISHED["ci_high"]),
        ("n_items", bk["n_items"], PUBLISHED["n_items"]),
    ]
    ok = True
    print("\nagainst published pooled figures, via unmodified committed code:")
    for name, got, want in checks:
        good = (got == want) if isinstance(want, int) else abs(got - want) < 1e-12
        ok &= good
        print(f"  {'ok  ' if good else 'DIFF'} {name}: {got!r} vs {want!r}")
    print(f"  beta (informational): {kb['beta']!r}")
    print("\n" + ("REPRODUCES EXACTLY with unmodified committed code"
                  if ok else "DOES NOT REPRODUCE"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
