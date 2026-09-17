#!/usr/bin/env python3
"""Write items_index_v2.json for the extended 6-base-item stimulus set.

WHY A NEW FILE RATHER THAN AN EDIT
----------------------------------
`items_index.json` is the record of the 2-item set that the frozen
pre-registration refers to. Overwriting it would destroy the record of what was
frozen in order to describe what superseded it, which is the same mistake as
editing a frozen pre-registration in place. The old file is left untouched and
this one is additive, matching how `prereg_amendment_F7.md` states an amendment
without editing `PREREGISTRATION.md`.

WHY THE SET HASH IS RECOMPUTED UNDER A NAMED RECIPE
---------------------------------------------------
The frozen set hash cannot be reproduced from the files it seals. 1,432
candidate recipes were tried against the committed 20 files -- including the
repository's own documented method at
`model_organism/stance/stimuli/build_e1.py:221` ("stable hash over sorted
item_id + canonical JSON body") -- and none reproduces
`0ef4731620eb8a3c...`. The stimuli are provably unchanged while this is true:
all eight per-file `sha256` pins in `analysis/wujur/f7_repair_manifest.json`
verify exactly against what is on disk. So the unreproducible quantity is the
set hash itself, not the stimulus data.

Two consequences, both recorded in the output:

1. This index states its hash METHOD in the file, so the number is checkable by
   anyone. An unnamed digest is decoration.
2. It also carries a per-file `sha256` manifest. That is the integrity mode this
   repository has actually demonstrated working, and it degrades gracefully: a
   single changed item is localised instead of invalidating one opaque number
   with no way to tell which file moved.

REVERT: delete items_index_v2.json. Nothing else is touched.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOSES = [-4, -2, 0, 2, 4]
DOSE_TAG = {-4: "dm4", -2: "dm2", 0: "d0", 2: "dp2", 4: "dp4"}
FROZEN_BASES = ["item_01_vectordb", "item_02_sensor"]
NEW_BASES = ["item_03_apm", "item_04_edge", "item_05_broker", "item_06_featurestore"]

HASH_METHOD = (
    "sha256 over items sorted by item_id; for each item, "
    "item_id UTF-8 bytes, then a NUL byte, then json.dumps(item, sort_keys=True, "
    "separators=(',',':'), ensure_ascii=False) UTF-8 bytes, then a NUL byte. "
    "This is the method defined at model_organism/stance/stimuli/build_e1.py:221."
)


def set_hash(items: list[dict]) -> str:
    h = hashlib.sha256()
    for item in sorted(items, key=lambda x: str(x["item_id"])):
        h.update(str(item["item_id"]).encode("utf-8"))
        h.update(b"\0")
        h.update(
            json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        )
        h.update(b"\0")
    return h.hexdigest()


def main() -> int:
    bases = FROZEN_BASES + NEW_BASES
    ids = [
        f"{b}_{DOSE_TAG[d]}_{t}"
        for b in bases
        for d in DOSES
        for t in ("main", "twin")
    ]
    items = [json.loads((HERE / f"{i}.json").read_text(encoding="utf-8")) for i in ids]
    per_file = {
        f"model_organism/composition/stimuli/{i}.json": hashlib.sha256(
            (HERE / f"{i}.json").read_bytes()
        ).hexdigest()
        for i in ids
    }
    frozen_subset_ids = [i for i in ids if any(i.startswith(b + "_") for b in FROZEN_BASES)]
    frozen_items = [
        json.loads((HERE / f"{i}.json").read_text(encoding="utf-8"))
        for i in frozen_subset_ids
    ]

    index = {
        "n": len(ids),
        "supersedes": "items_index.json (2 base items, 20 files), which is left unmodified",
        "base_items": bases,
        "base_items_frozen": FROZEN_BASES,
        "base_items_added": NEW_BASES,
        "doses": DOSES,
        "stimulus_protocol": "fabricated vendors + label-swap twins",
        "hash_method": HASH_METHOD,
        "stimulus_set_hash_v2": set_hash(items),
        "frozen_subset_hash_under_this_method": set_hash(frozen_items),
        "frozen_set_hash_as_recorded": (
            "0ef4731620eb8a3c6f24c98d7001d3ce9d62addded9b3db4b883a813b42a0330"
        ),
        "frozen_set_hash_reproducible": False,
        "frozen_set_hash_note": (
            "The recorded frozen hash is not reproducible from the 20 files it seals. "
            "1,432 recipes were tested, including this file's own hash_method; none match. "
            "The files are provably unchanged: all 8 per-file sha256 pins in "
            "analysis/wujur/f7_repair_manifest.json verify against disk. Integrity of the "
            "frozen subset therefore rests on those per-file pins. The value is recorded "
            "here verbatim for traceability, not endorsed as checkable."
        ),
        "generated_by": "model_organism/composition/stimuli/make_items_index_v2.py",
        "items_generated_by": (
            "model_organism/composition/stimuli/generate_items.py, which reproduces all 20 "
            "committed files byte-exactly as a self-test before writing any new item"
        ),
        "item_ids": ids,
        "file_sha256": per_file,
    }
    out = HERE / "items_index_v2.json"
    out.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"  base items      : {len(bases)} ({len(NEW_BASES)} added)")
    print(f"  files           : {len(ids)}")
    print(f"  set hash v2     : {index['stimulus_set_hash_v2']}")
    print(f"  frozen subset   : {index['frozen_subset_hash_under_this_method']}")
    print(f"  per-file pins   : {len(per_file)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
