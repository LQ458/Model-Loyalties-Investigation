#!/usr/bin/env python3
"""kappa at six item clusters, executed against the pre-committed analysis plan.

THE PLAN THIS EXECUTES
----------------------
`analysis/wujur/prereg_amendment_stimulus_set.md` section 5, committed to git
before any row of `f_phase1_k3ext_20260916` was read. Nothing here chooses an
estimand, a unit or a decision rule; all three were fixed in advance.

  estimand  kappa = (s_PM - s_MP) / (s_P - s_M), via the unmodified
            scoring/compose.py
  unit      base item, outer bootstrap over items, twins are a within-item
            control and never their own cluster
  report    n_items beside every interval, mandatory

  outcome A  interval excludes 0, same sign as -0.272  -> last-wins supported
                                                          at 6 clusters
  outcome B  interval includes 0                       -> sign claim withdrawn
  outcome C  interval excludes 0, opposite sign        -> sign reversal,
                                                          published claim withdrawn

  OVERRIDE  an interval whose exclusion of zero is within 5% of its own width
            is reported as NOT determining the sign, whichever side it falls.
            This exists because the published 2-cluster interval clears zero by
            2.603% of its width, and it would be incoherent to fix the cluster
            count and then rely on the same knife-edge margin.

A DISCLOSED AMBIGUITY IN MY OWN PLAN
------------------------------------
The plan's pooling clause says frozen and new items "are pooled only if the
frozen-vs-new comparison gives no evidence of heterogeneity", and then says
that if they are not poolable "the 6-item result is reported as the primary".
Those two sentences are not consistent: a 6-item result IS the pooled result,
so it cannot be the fallback for pooling being refused. That is a drafting
defect in my pre-commitment, not something to resolve silently in whichever
direction the data happens to favour.

Resolution, fixed here before the numbers are printed: compute all three
strata - frozen 2 items alone, new 4 items alone, pooled 6 - report every one
with its own n_items, and let the heterogeneity check decide only which is
DESIGNATED primary, never which are shown. Any reader can then apply either
reading of the clause. The ambiguity is stated in the output artifact.

REVERT: delete this file and analysis/wujur/kappa_6item.json. Mutates nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ARM = HERE.parents[1] / "model_organism" / "composition"
sys.path.insert(0, str(ARM / "scoring"))
from compose import (  # noqa: E402
    bootstrap_effect,
    bootstrap_kappa,
    cell_means,
    kappa_beta,
    load_jsonl,
)
from parse import iter_parsed  # noqa: E402

FROZEN = ARM / "runs" / "f_phase1_k3_20260727" / "generations.jsonl"
NEW = ARM / "runs" / "f_phase1_k3ext_20260916" / "generations.jsonl"
PUBLISHED = {"kappa": -0.2716763005780347, "lo": -0.6134969325153373,
             "hi": -0.01556420233463037, "n_items": 2}
MARGIN_RULE = 0.05


def read_rows(p: Path) -> list[dict[str, Any]]:
    rows = []
    for line in p.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # tail line mid-write
    return rows


def margin_fraction(lo: float | None, hi: float | None) -> float | None:
    """How close the interval's near edge sits to zero, as a share of width."""
    if lo is None or hi is None:
        return None
    w = hi - lo
    if w <= 0:
        return None
    if lo > 0:
        return lo / w
    if hi < 0:
        return abs(hi) / w
    return 0.0


def classify(lo: float | None, hi: float | None, point: float | None) -> dict[str, Any]:
    frac = margin_fraction(lo, hi)
    includes_zero = lo is not None and hi is not None and lo <= 0 <= hi
    if includes_zero:
        return {"outcome": "B", "reading": "interval includes zero; sign claim withdrawn",
                "determines_sign": False, "margin_fraction": frac}
    knife = frac is not None and frac < MARGIN_RULE
    same_sign = point is not None and point < 0
    out = "A" if same_sign else "C"
    reading = ("last-wins supported at this cluster count"
               if out == "A" else "SIGN REVERSAL; published claim withdrawn")
    if knife:
        return {"outcome": out, "reading": reading + ", BUT the pre-committed 5% margin "
                "override applies: exclusion of zero is within 5% of interval width, so "
                "this is reported as NOT determining the sign",
                "determines_sign": False, "margin_fraction": frac,
                "override_applied": True}
    return {"outcome": out, "reading": reading, "determines_sign": True,
            "margin_fraction": frac, "override_applied": False}


def stratum(parsed: list[dict[str, Any]], label: str) -> dict[str, Any]:
    summ = cell_means(parsed)
    kb = kappa_beta(summ["s_by_cell"])
    bk = bootstrap_kappa(parsed)
    be = bootstrap_effect(parsed)
    bad = sum(1 for r in parsed if r.get("s") is None)
    s = summ["s_by_cell"]
    gates = {
        "G1_parse": {"value": bad / len(parsed) if parsed else None,
                     "pass": bool(parsed) and (bad / len(parsed)) < 0.10},
        "G2_baseline": {"value": s.get("N"),
                        "pass": s.get("N") is not None and abs(s["N"]) <= 0.15},
        "G3_effect": {"value": kb.get("denom"), "ci_low": be.get("ci_low"),
                      "ci_high": be.get("ci_high"),
                      "pass": bool(kb.get("denom") is not None and kb["denom"] >= 0.4
                                   and be.get("excludes_zero"))},
        "G4_saturation": {"s_P": s.get("P"), "s_M": s.get("M"),
                          "pass": not (s.get("P") is not None and s.get("M") is not None
                                       and s["P"] >= 0.95 and s["M"] <= -0.95)},
    }
    return {
        "label": label,
        "n_rows": len(parsed),
        "n_unparseable": bad,
        "n_items": bk.get("n_items"),
        "s_by_cell": s,
        "kappa_point": kb.get("kappa"),
        "beta": kb.get("beta"),
        "denom_s_P_minus_s_M": kb.get("denom"),
        "kappa_bootstrap": bk,
        "effect_bootstrap": be,
        "classification": classify(bk.get("ci_low"), bk.get("ci_high"), bk.get("point")),
        "gates": gates,
    }


def main() -> int:
    if not NEW.is_file():
        print("extension run not present")
        return 1
    new_rows = read_rows(NEW)
    if len(new_rows) < 120:
        print(f"extension incomplete: {len(new_rows)}/120. Refusing to score a partial grid, "
              "per the plan's item-clustered unit -- an unbalanced grid would weight items "
              "by how far the run got.")
        return 1

    frozen_rows = read_rows(FROZEN)
    fp, np_, pp = (iter_parsed(frozen_rows), iter_parsed(new_rows),
                   iter_parsed(frozen_rows + new_rows))

    res = {
        "plan": "analysis/wujur/prereg_amendment_stimulus_set.md section 5",
        "plan_committed_before_data": True,
        "disclosed_plan_ambiguity": (
            "The pooling clause is self-inconsistent: it makes pooling conditional on "
            "homogeneity and then names the 6-item (pooled) result as the fallback when "
            "pooling is refused. Resolved by reporting all three strata always, and "
            "letting the heterogeneity check decide only which is designated primary."
        ),
        "published_2_item": PUBLISHED,
        "margin_rule": f"exclusion of zero within {MARGIN_RULE:.0%} of interval width "
                       "is reported as not determining the sign",
        "strata": {
            "frozen_2_items": stratum(fp, "frozen 2 items (prior collection)"),
            "new_4_items": stratum(np_, "new 4 items"),
            "pooled_6_items": stratum(pp, "pooled 6 items"),
        },
    }

    f, n, p = (res["strata"][k] for k in ("frozen_2_items", "new_4_items", "pooled_6_items"))
    # Heterogeneity: do the two collections' kappa intervals overlap?
    fl, fh = f["kappa_bootstrap"].get("ci_low"), f["kappa_bootstrap"].get("ci_high")
    nl, nh = n["kappa_bootstrap"].get("ci_low"), n["kappa_bootstrap"].get("ci_high")
    overlap = None
    if None not in (fl, fh, nl, nh):
        overlap = not (fh < nl or nh < fl)
    res["heterogeneity"] = {
        "method": "overlap of the two collections' item-clustered kappa intervals; "
                  "a weak check, and named as weak -- at 2 and 4 clusters no test has "
                  "power to refuse pooling, which is itself the finding",
        "frozen_ci": [fl, fh],
        "new_ci": [nl, nh],
        "intervals_overlap": overlap,
        "designated_primary": "pooled_6_items" if overlap else "new_4_items",
        "caveat": "Non-overlap would not license discarding either collection; it would "
                  "mean the pooled estimate mixes two regimes and must be reported as such.",
    }
    res["verdict"] = {
        "primary": res["heterogeneity"]["designated_primary"],
        "classification": res["strata"][res["heterogeneity"]["designated_primary"]]["classification"],
    }

    out = HERE / "kappa_6item.json"
    out.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")

    for key in ("frozen_2_items", "new_4_items", "pooled_6_items"):
        st = res["strata"][key]
        bk = st["kappa_bootstrap"]
        print(f"\n=== {st['label']} ===")
        print(f"  rows {st['n_rows']}  items {st['n_items']}  unparseable {st['n_unparseable']}")
        print(f"  s_by_cell {({k: round(v,4) for k,v in st['s_by_cell'].items() if v is not None})}")
        print(f"  kappa {bk.get('point')}  CI [{bk.get('ci_low')}, {bk.get('ci_high')}]")
        print(f"  D = s_P - s_M = {st['denom_s_P_minus_s_M']}")
        cl = st["classification"]
        print(f"  outcome {cl['outcome']}  determines_sign={cl['determines_sign']}  "
              f"margin={cl['margin_fraction']}")
        print(f"  gates " + " ".join(f"{k}:{'P' if v['pass'] else 'F'}" for k, v in st["gates"].items()))
    print(f"\nheterogeneity overlap: {overlap}  -> primary = {res['verdict']['primary']}")
    print(f"VERDICT: {res['verdict']['classification']['reading']}")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
