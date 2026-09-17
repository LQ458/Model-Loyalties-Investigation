#!/usr/bin/env python3
"""Compute the beta, Delta and corrected-kappa_priv intervals, and commit them.

WHY THIS EXISTS, AND WHOSE FAULT IT IS
--------------------------------------
Paper 2 reports six interval bounds that existed in no artifact and were
produced by no committed code: the three beta intervals, the Delta interval, and
the interval on the corrected privilege index. A blind reviewer grepped the
repository for their digits and found hits only inside paper2.tex.

They are not fabricated - I computed them - but I computed them in a scratch
eval cell and handed the numbers to the writing agent in a chat message. The
number then entered a manuscript whose stated discipline is that every figure is
recomputed from committed raw records by committed code. A figure whose
provenance is a chat message fails that standard exactly as badly as a figure
read out of a summary document, which is the defect this project has corrected
three times already. Worse, the caption named kappa_6item.json as the source,
and that file contains no beta interval at all, so the manuscript asserted a
provenance that was false.

This script is the fix: it recomputes all of them with committed code, writes a
committed artifact, and prints the values so the manuscript can be checked
against something regenerable.

WHAT IS COMPUTED, AND WITH WHAT
-------------------------------
Nothing here is a new estimator. Every resampling routine is the project's own:

  beta, three strata   `compose._item_cell_twin_groups` and
                       `compose._nested_item_resample`, the identical machinery
                       `compose.bootstrap_kappa` uses, with `kappa_beta`'s beta
                       read off each resample instead of its kappa. compose.py
                       has bootstrap_kappa and bootstrap_effect but no
                       bootstrap_beta, which is why beta was the one estimand in
                       either paper with no interval anywhere.

  Delta, D_user,       `score_privilege._groups` and `_stratum_value`, resampling
  kappa_priv           the two privilege items jointly so the numerator and the
                       denominator move together. Resampling them independently
                       would break the pairing and understate the ratio's width.

Seed 0 and 2000 draws throughout, matching compose.bootstrap_kappa's defaults,
so these intervals are directly comparable with the kappa intervals already
published rather than being a differently-tuned bootstrap.

TWO THINGS THE OUTPUT MUST BE READ WITH
---------------------------------------
1. The privilege interval rests on TWO item clusters. Drawing 2 with replacement
   from 2 gives three distinct multisets, so this interval is subject to exactly
   the criticism the paper levels at the original 2-cluster kappa. It is
   reported because an interval that is honestly labelled as coarse is better
   than an exceedance quoted with no interval at all, which is what the
   manuscript did before. It is not evidence that two clusters suffice.

2. The pooled beta interval is NOT the one to quote. The paper's own Amendment 2
   analysis declares the pooled beta affected, because it averages a neutral
   cell built two ways, and names the new-four-item beta as the
   construction-clean measurement. The construction-clean stratum has the WIDER
   interval, so quoting the pooled half-width flatters the design by roughly 39%.
   Both are printed here and the artifact marks which is construction-clean.

REVERT: delete this file and analysis/wujur/missing_intervals.json.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARM = HERE.parents[1] / "model_organism" / "composition"
sys.path.insert(0, str(ARM / "scoring"))

from compose import (  # noqa: E402
    _item_cell_twin_groups,
    _nested_item_resample,
    cell_means,
    kappa_beta,
    load_jsonl,
)
from parse import iter_parsed  # noqa: E402
from score_privilege import _groups, _stratum_value  # noqa: E402

FROZEN = ARM / "runs" / "f_phase1_k3_20260727" / "generations.jsonl"
NEWCANON = ARM / "runs" / "f_phase1_k3ext_20260916" / "generations.canonical.jsonl"
PRIV = ARM / "runs" / "f_privilege_tiny8_20260727" / "generations.jsonl"
BLOCKA = ARM / "runs" / "f7r_userpriv_k3_20260916" / "generations.jsonl"

DRAWS = 2000
SEED = 0


def pct(sorted_vals: list[float], q: float) -> float:
    return sorted_vals[int(q * (len(sorted_vals) - 1))]


def resample_multiplicity_preserving(groups: dict, rng: random.Random) -> list[dict]:
    """`_nested_item_resample`, but a twice-drawn item counts twice.

    THE BUG THIS EXISTS TO MEASURE, found by a reviewing agent and replicated
    here. `_nested_item_resample` draws items WITH replacement, but
    `cell_means` keys its accumulator on `base_item_id` (compose.py:56) and then
    averages over the number of DISTINCT keys (compose.py:85). So when a draw
    picks the same item twice, both copies land in one bucket and the item
    contributes once. A draw of {A,A,A,A,A,B} is averaged as (A+B)/2 rather
    than (5A+B)/6, which pulls every resample toward the centre and makes the
    interval too narrow.

    At G=2 the defect is provably inert, since mean{A,A} = A, so the two
    routines must agree BIT-FOR-BIT on the frozen two-item stratum. That
    identity is the correctness check on this function: if the G=2 intervals
    ever differ, this implementation is wrong rather than the frozen one.
    Achieving it requires consuming the RNG in exactly the frozen order - all
    item draws first, then the row draws - so the item list is materialised
    before the loop and not built lazily.

    The fix is applied here rather than in compose.py because four committed
    scorers reproduce bit-identically through that file, and silently widening
    every published interval in the repository is not a change to make from a
    helper script. Both readings are reported instead.
    """
    ids = list(groups)
    drawn = [ids[rng.randrange(len(ids))] for _ in ids]
    sample: list[dict] = []
    for slot, item in enumerate(drawn):
        for cells in groups[item].values():
            for rows in cells.values():
                for _ in rows:
                    row = dict(rows[rng.randrange(len(rows))])
                    meta = dict(row.get("meta") or {})
                    meta["base_item_id"] = f"{item}__s{slot}"
                    row["meta"] = meta
                    sample.append(row)
    return sample


def _stat_dist(parsed: list[dict], stat: str, resampler, draws: int, seed: int) -> list[float]:
    groups = _item_cell_twin_groups(parsed)
    rng = random.Random(seed)
    dist = []
    for _ in range(draws):
        v = kappa_beta(cell_means(resampler(groups, rng))["s_by_cell"]).get(stat)
        if v is not None:
            dist.append(float(v))
    dist.sort()
    return dist


def bootstrap_stat(parsed: list[dict], stat: str, draws: int = DRAWS,
                   seed: int = SEED) -> dict:
    """Both readings of one estimand: the frozen resampler and the corrected one.

    Generalised from a beta-only helper because the corrected COMPOSITION-KAPPA
    interval had the same defect the rest of this file exists to fix. It was
    computed once in a scratch cell, quoted in the manuscript as
    [-0.7939, -0.2897] with a 8.5% widening, and never committed - so a reviewer
    grepping for those digits found them only in the .tex. That is the second
    instance of the same failure in this workstream, which is why the routine is
    now parameterised by `stat` rather than duplicated per estimand.
    """
    ids = list(_item_cell_twin_groups(parsed))
    point = kappa_beta(cell_means(parsed)["s_by_cell"]).get(stat)

    def summarise(dist: list[float]) -> dict:
        lo, hi = pct(dist, 0.025), pct(dist, 0.975)
        return {"ci_low": lo, "ci_high": hi, "half_width": (hi - lo) / 2,
                "width": hi - lo, "contains_zero": lo <= 0 <= hi,
                "n_effective": len(dist)}

    pub = summarise(_stat_dist(parsed, stat, _nested_item_resample, draws, seed))
    cor = summarise(_stat_dist(parsed, stat, resample_multiplicity_preserving, draws, seed))
    return {
        "point": point,
        "n_items": len(ids),
        "n_resamples": draws,
        "seed": seed,
        "bootstrap_method": "nested_item_then_within_item",
        "as_published": pub,
        "multiplicity_corrected": cor,
        "corrected_is_wider_by": (cor["width"] / pub["width"] - 1) if pub["width"] else None,
        "identical_at_G2": abs(pub["ci_low"] - cor["ci_low"]) < 1e-12
                           and abs(pub["ci_high"] - cor["ci_high"]) < 1e-12,
        "which_to_quote": "multiplicity_corrected",
        "machinery": "compose._item_cell_twin_groups + kappa_beta; both the frozen "
                     "_nested_item_resample and the multiplicity-preserving variant",
    }


def bootstrap_privilege(draws: int = DRAWS, seed: int = SEED) -> dict:
    priv = _groups(iter_parsed(load_jsonl(PRIV)))
    ua = _groups(iter_parsed(load_jsonl(BLOCKA)))
    items = sorted(set(priv) & set(ua))

    def val(g, cell, its, rng=None):
        v = [x for i in its if (x := _stratum_value(g, i, cell, rng)) is not None]
        return statistics.fmean(v) if v else None

    delta_pt = val(priv, "PM", items) - val(priv, "MP", items)
    duser_pt = val(ua, "P", items) - val(ua, "M", items)

    rng = random.Random(seed)
    ds, dus, ks = [], [], []
    for _ in range(draws):
        pick = [rng.choice(items) for _ in items]
        d = val(priv, "PM", pick, rng) - val(priv, "MP", pick, rng)
        du = val(ua, "P", pick, rng) - val(ua, "M", pick, rng)
        if du and abs(du) > 1e-12:
            ds.append(d)
            dus.append(du)
            ks.append(d / du)
    ds.sort()
    dus.sort()
    ks.sort()
    in_range = sum(1 for k in ks if abs(k) <= 1.0)
    near_edge = max(ks)  # least extreme, i.e. closest to the admissible boundary
    width = pct(ks, 0.975) - pct(ks, 0.025)
    return {
        "n_items": len(items),
        "items": items,
        "Delta": {"point": delta_pt, "ci_low": pct(ds, 0.025), "ci_high": pct(ds, 0.975)},
        "D_user": {"point": duser_pt, "ci_low": pct(dus, 0.025), "ci_high": pct(dus, 0.975)},
        "kappa_priv": {
            "point": delta_pt / duser_pt,
            "ci_low": pct(ks, 0.025),
            "ci_high": pct(ks, 0.975),
            "exceedance_of_point_beyond_1": abs(delta_pt / duser_pt) - 1.0,
            "near_edge_beyond_boundary": abs(pct(ks, 0.975)) - 1.0,
            "near_edge_as_share_of_width": (abs(pct(ks, 0.975)) - 1.0) / width if width else None,
            "draws_inside_admissible_range": in_range,
            "draws_total": len(ks),
            "fraction_inside": in_range / len(ks) if ks else None,
        },
        "n_resamples": draws,
        "seed": seed,
        "machinery": "score_privilege._groups + _stratum_value, items resampled jointly",
        "caveat": "TWO item clusters. Drawing 2 with replacement from 2 gives three distinct "
                  "multisets, so this interval is subject to the same criticism the paper "
                  "levels at the original 2-cluster kappa. Reported because an honestly "
                  "labelled coarse interval beats an exceedance with no interval.",
    }


def main() -> int:
    frozen = iter_parsed(load_jsonl(FROZEN))
    new = iter_parsed(load_jsonl(NEWCANON))
    out = {
        "purpose": "Supply committed provenance for interval bounds that previously existed "
                   "only inside paper2.tex.",
        "beta": {
            "frozen_2_items": bootstrap_stat(frozen, "beta"),
            "new_4_items": bootstrap_stat(new, "beta"),
            "pooled_6_items": bootstrap_stat(frozen + new, "beta"),
        },
        "kappa": {
            "frozen_2_items": bootstrap_stat(frozen, "kappa"),
            "new_4_items": bootstrap_stat(new, "kappa"),
            "pooled_6_items": bootstrap_stat(frozen + new, "kappa"),
        },
        "kappa_note": (
            "The multiplicity-corrected composition-kappa interval is computed here "
            "because it previously existed only in the manuscript. It was measured once "
            "in a scratch cell, quoted as [-0.7939, -0.2897] with an 8.5% widening, and "
            "never committed - the second instance of that failure in this workstream, "
            "the first being the beta intervals this file was created to fix."
        ),
        "beta_construction_clean_stratum": "new_4_items",
        "beta_quoting_rule": (
            "Quote the new-4-item MULTIPLICITY-CORRECTED interval. Two separate reasons, "
            "and the first one that was given for this was WRONG. It is not that the "
            "pooled stratum averages a neutral cell built two ways: kappa_6item.json "
            "stores s_N as -4.34e-19, -3.25e-19 and -3.61e-19 for the three strata, so "
            "the neutral term contributes nothing to any reported beta and BOTH "
            "constructions measured zero. The frozen-versus-new beta disagreement "
            "(-0.0375 against +0.0179) is therefore entirely a composite-cell "
            "difference and cannot be attributed to the neutral construction. The "
            "defensible reason is narrower: the frozen neutral cell's construction is "
            "not reproducible from committed files, so its true baseline is unknown even "
            "though the one built measured zero. Second reason, unaffected by the first: "
            "the construction-clean stratum has the WIDER interval, so quoting the "
            "pooled half-width flatters the design."
        ),
        "privilege": bootstrap_privilege(),
    }
    (HERE / "missing_intervals.json").write_text(json.dumps(out, indent=2) + "\n",
                                                 encoding="utf-8")
    for k, v in ([("beta  "+a, b) for a, b in out["beta"].items()]
                 + [("kappa "+a, b) for a, b in out["kappa"].items()]):
        pub, cor = v["as_published"], v["multiplicity_corrected"]
        flag = "  IDENTICAL (G=2, as theory requires)" if v["identical_at_G2"] else ""
        print(f"{k:22s} point {v['point']:+.6f}  n_items {v['n_items']}")
        print(f"     as-published          [{pub['ci_low']:+.6f}, {pub['ci_high']:+.6f}]  "
              f"half-width {pub['half_width']:.4f}")
        print(f"     multiplicity-corrected[{cor['ci_low']:+.6f}, {cor['ci_high']:+.6f}]  "
              f"half-width {cor['half_width']:.4f}  "
              f"({v['corrected_is_wider_by']:+.1%} wider){flag}")
    clean = out["beta"][out["beta_construction_clean_stratum"]]["multiplicity_corrected"]
    pooled = out["beta"]["pooled_6_items"]["multiplicity_corrected"]
    print(f"\nquote: {out['beta_construction_clean_stratum']}, multiplicity-corrected, "
          f"half-width {clean['half_width']:.4f} -> resolution about "
          f"+/-{clean['half_width']:.2f}")
    print(f"       pooled-corrected half-width is {pooled['half_width']:.4f}, so quoting "
          f"pooled flatters the design by "
          f"{100*(1-pooled['half_width']/clean['half_width']):.0f}%")
    p = out["privilege"]
    for name in ("Delta", "D_user"):
        q = p[name]
        print(f"\n{name:8s} point {q['point']:+.6f}  CI [{q['ci_low']:+.6f}, {q['ci_high']:+.6f}]")
    k = p["kappa_priv"]
    print(f"\nkappa_priv point {k['point']:+.6f}  CI [{k['ci_low']:+.6f}, {k['ci_high']:+.6f}]")
    print(f"  exceedance of point beyond 1 : {k['exceedance_of_point_beyond_1']:.4%}")
    print(f"  near edge beyond boundary    : {k['near_edge_beyond_boundary']:.4f} "
          f"= {k['near_edge_as_share_of_width']:.1%} of interval width")
    print(f"  draws inside [-1,+1]         : {k['draws_inside_admissible_range']}/{k['draws_total']}"
          f" = {k['fraction_inside']:.2%}")
    print(f"\nwrote {HERE / 'missing_intervals.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
