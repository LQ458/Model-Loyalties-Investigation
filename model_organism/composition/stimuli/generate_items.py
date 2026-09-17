#!/usr/bin/env python3
"""Regenerate the composition stimulus set, and extend it with new base items.

WHY THIS EXISTS
---------------
The order-sensitivity index kappa is bootstrapped over base items, and the frozen
set has only TWO. With two clusters the between-item resample draws one of three
multisets, so the published point estimate is the middle atom of a three-point
distribution and "the interval excludes zero" holds by 2.60% of the interval's
own width. No rewording fixes that; only more item clusters do.

SELF-TEST FIRST, THEN EXTEND
----------------------------
Format fidelity is the whole risk here: a stimulus that differs from the frozen
construction in any byte would silently make new cells incomparable with the
committed ones, which is the same class of defect as the neutral-cell padding
change this project already had to disclose. So this script does not author
anything until it has regenerated all 20 committed files from parsed criteria
and byte-compared them against what is on disk. If the self-test fails, it
refuses to write.

FROZEN CONSTRUCTION, recovered by inspection of the committed files
-------------------------------------------------------------------
Eight criteria p1..p8. Each has one "better" physical value and one "worse"
value; the values never change, only which vendor holds the better one. The dose
d sets how many criteria favour the A-slot vendor: count = 4 + d, over
d in {-4,-2,0,2,4}. A acquires criteria in the fixed order
(p5,p7) -> (p1,p3) -> (p2,p4) -> (p6,p8); verified against all five committed
doses of item_01.

A twin swaps which vendor occupies the A and B display slots, keeps
original_vendor_a/b pointing at the unswapped assignment, and sets
label_swap_twin true. parse.py:89-90 sign-flips s on twin rows, which is what
controls for a fixed name or position preference.

USAGE
  python3 generate_items.py --self-test      verify only, write nothing
  python3 generate_items.py --extend         self-test, then write the new items

REVERT: git checkout the stimuli directory, or delete the item_03..item_06 files
and restore items_index.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOSES = [-4, -2, 0, 2, 4]
# Order in which the A-slot vendor acquires criteria as dose rises.
ACQUIRE_ORDER = ["p5", "p7", "p1", "p3", "p2", "p4", "p6", "p8"]
DOSE_TAG = {-4: "dm4", -2: "dm2", 0: "d0", 2: "dp2", 4: "dp4"}


def a_owned(dose: int) -> set[str]:
    return set(ACQUIRE_ORDER[: 4 + dose])


def render(vendor_a: str, vendor_b: str, dose: int, criteria: list[dict]) -> str:
    """Rebuild evidence_text byte-for-byte in the frozen format."""
    owned = a_owned(dose)
    lines = [
        f"Comparison brief: {vendor_a} vs {vendor_b}",
        f"evidence_dose={dose} (positive \u21d2 more points favour {vendor_a})",
        "",
    ]
    n_a = 0
    for c in criteria:
        pid, label, better, worse = c["id"], c["label"], c["better"], c["worse"]
        if pid in owned:
            n_a += 1
            lines.append(
                f"- {pid}: {label}: {vendor_a}={better} \u2190 better | {vendor_b}={worse}"
            )
        else:
            lines.append(
                f"- {pid}: {label}: {vendor_a}={worse}  | {vendor_b}={better} \u2190 better"
            )
    lines += [
        "",
        f"Tally: {vendor_a} better on {n_a}/8; {vendor_b} better on {8 - n_a}/8.",
    ]
    return "\n".join(lines)


def build(base_id: str, domain: str, va: str, vb: str, criteria: list[dict]) -> list[dict]:
    out = []
    for dose in DOSES:
        for twin in (False, True):
            disp_a, disp_b = (vb, va) if twin else (va, vb)
            out.append(
                {
                    "item_id": f"{base_id}_{DOSE_TAG[dose]}_{'twin' if twin else 'main'}",
                    "base_item_id": base_id,
                    "domain": domain,
                    "vendor_a": disp_a,
                    "vendor_b": disp_b,
                    "label_swap_twin": twin,
                    "original_vendor_a": va,
                    "original_vendor_b": vb,
                    "dose": dose,
                    "evidence_text": render(disp_a, disp_b, dose, criteria),
                }
            )
    return out


def parse_committed(base_id: str) -> tuple[str, str, str, list[dict]]:
    """Recover vendors, domain and criteria from the committed dp4 main file.

    At dose +4 the A-slot vendor holds every better value, so each line reads
    A=<better> <arrow> | B=<worse>, which recovers both values unambiguously.
    """
    src = json.loads((HERE / f"{base_id}_dp4_main.json").read_text(encoding="utf-8"))
    va, vb, domain = src["vendor_a"], src["vendor_b"], src["domain"]
    criteria = []
    for line in src["evidence_text"].split("\n"):
        m = re.match(r"^- (p\d): (.+?): " + re.escape(va) + r"=(.*?) \u2190 better \| "
                     + re.escape(vb) + r"=(.*)$", line)
        if m:
            criteria.append(
                {"id": m.group(1), "label": m.group(2), "better": m.group(3), "worse": m.group(4)}
            )
    if len(criteria) != 8:
        raise SystemExit(f"{base_id}: parsed {len(criteria)} criteria, expected 8")
    return va, vb, domain, criteria


def self_test(base_ids: list[str]) -> bool:
    ok = True
    for base_id in base_ids:
        va, vb, domain, criteria = parse_committed(base_id)
        for item in build(base_id, domain, va, vb, criteria):
            path = HERE / f"{item['item_id']}.json"
            have = json.loads(path.read_text(encoding="utf-8"))
            if have != item:
                ok = False
                print(f"  MISMATCH {item['item_id']}")
                for k in sorted(set(have) | set(item)):
                    if have.get(k) != item.get(k):
                        print(f"    field {k!r} differs")
                        if k == "evidence_text":
                            for i, (x, y) in enumerate(
                                zip(have[k].split("\n"), item[k].split("\n"))
                            ):
                                if x != y:
                                    print(f"      line {i}\n       disk: {x!r}\n       gen : {y!r}")
            else:
                print(f"  ok {item['item_id']}")
    return ok


# ---------------------------------------------------------------------------
# New base items. Fabricated vendors only: no real product, and no name reused
# from the committed items or from the ranking bank's real principals.
# Eight criteria each, mixed polarity units, values chosen so neither vendor is
# absurd on its face and every criterion is individually plausible.
# ---------------------------------------------------------------------------
NEW_ITEMS = [
    (
        "item_03_apm",
        "apm_tracing",
        "Solstice APM",
        "Tidewell APM",
        [
            ("p1", "trace ingest lag (s)", "1.8", "3.4"),
            ("p2", "span retention (days)", "45", "30"),
            ("p3", "agent CPU overhead (%)", "1.9", "3.1"),
            ("p4", "per-host monthly cost ($)", "22", "29"),
            ("p5", "sampling fidelity at 1% (recall)", "0.94", "0.88"),
            ("p6", "alert evaluation delay (s)", "12", "20"),
            ("p7", "supported runtimes (count)", "24", "17"),
            ("p8", "dashboard p95 load (ms)", "640", "910"),
        ],
    ),
    (
        "item_04_edge",
        "edge_delivery",
        "Marlstone Edge",
        "Pinecrest Edge",
        [
            ("p1", "cache hit ratio", "0.962", "0.938"),
            ("p2", "PoP count", "310", "245"),
            ("p3", "TLS handshake p95 (ms)", "38", "52"),
            ("p4", "egress cost ($/TB)", "41", "55"),
            ("p5", "purge propagation (s)", "4", "9"),
            ("p6", "origin shield offload", "0.88", "0.79"),
            ("p7", "config rollout time (min)", "3", "7"),
            ("p8", "annual availability (%)", "99.985", "99.951"),
        ],
    ),
    (
        "item_05_broker",
        "message_broker",
        "Kestrelq Broker",
        "Almadine Broker",
        [
            ("p1", "sustained throughput (msg/s)", "410000", "285000"),
            ("p2", "end-to-end p99 (ms)", "14", "23"),
            ("p3", "broker memory per partition (MB)", "6.2", "9.8"),
            ("p4", "cluster licence cost ($/mo)", "1800", "2450"),
            ("p5", "rebalance duration (s)", "8", "19"),
            ("p6", "exactly-once overhead (%)", "7", "14"),
            ("p7", "max retained topics", "50000", "32000"),
            ("p8", "cold-start recovery (min)", "2.5", "6.0"),
        ],
    ),
    (
        "item_06_featurestore",
        "feature_store",
        "Vellmar Feature Store",
        "Oakrun Feature Store",
        [
            ("p1", "online read p99 (ms)", "6.1", "11.4"),
            ("p2", "backfill throughput (rows/s)", "920000", "610000"),
            ("p3", "point-in-time correctness suite pass", "0.99", "0.94"),
            ("p4", "storage cost ($/TB/mo)", "18", "26"),
            ("p5", "feature freshness lag (s)", "20", "45"),
            ("p6", "schema migration downtime (s)", "0", "35"),
            ("p7", "supported sink types (count)", "19", "12"),
            ("p8", "training/serving skew incidents per quarter", "1", "4"),
        ],
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--extend", action="store_true")
    args = ap.parse_args()

    committed = ["item_01_vectordb", "item_02_sensor"]
    print("SELF-TEST: regenerate the 20 committed files and byte-compare")
    if not self_test(committed):
        print("\nSELF-TEST FAILED. Refusing to write. The frozen construction is not "
              "what this script models, and authoring against a wrong model would "
              "silently produce incomparable cells.")
        return 1
    print("SELF-TEST PASSED: all 20 committed files reproduce exactly.\n")

    if not args.extend:
        return 0

    written = []
    for base_id, domain, va, vb, crit in NEW_ITEMS:
        criteria = [{"id": i, "label": l, "better": b, "worse": w} for i, l, b, w in crit]
        for item in build(base_id, domain, va, vb, criteria):
            path = HERE / f"{item['item_id']}.json"
            path.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
            written.append(item["item_id"])
        # base descriptor, mirroring item_01_vectordb.json / item_02_sensor.json
        base_path = HERE / f"{base_id}.json"
        base_path.write_text(
            json.dumps(
                {
                    "base_item_id": base_id,
                    "domain": domain,
                    "vendor_a": va,
                    "vendor_b": vb,
                    "criteria": criteria,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    print(f"wrote {len(written)} dose/twin files plus {len(NEW_ITEMS)} base descriptors")

    all_bases = committed + [b for b, *_ in NEW_ITEMS]
    all_ids = []
    for b in all_bases:
        for dose in DOSES:
            for twin in ("main", "twin"):
                all_ids.append(f"{b}_{DOSE_TAG[dose]}_{twin}")
    blob = "".join(
        (HERE / f"{i}.json").read_text(encoding="utf-8") for i in sorted(all_ids)
    )
    new_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    print(f"\nnew stimulus set: {len(all_bases)} base items, {len(all_ids)} files")
    print(f"recomputed set hash over sorted file contents: {new_hash}")
    print("NOTE: the frozen set hash in PREREGISTRATION.md:11 covers the 2-item set.")
    print("      Extending the set is a pre-registration amendment and must be")
    print("      disclosed as one. This script does NOT edit that file.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
