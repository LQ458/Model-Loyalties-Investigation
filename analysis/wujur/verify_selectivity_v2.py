#!/usr/bin/env python3
"""Independent audit of analysis/wujur/selectivity_v2.md against
analysis/wujur/selectivity_v2.json and the raw source rows.

Recomputes the load-bearing quantities from the raw JSONL by a DIFFERENT code
path than the generator (no repo parser import for the counts that can be
checked against the stored score; plain index arithmetic), then asserts the
markdown literally contains each claimed figure.
"""
import json, re, sys, hashlib, collections
from pathlib import Path

REPO = Path("/home/barry/workspace/projects/Model-Loyalties-Investigation")
MD = (REPO / "analysis/wujur/selectivity_v2.md").read_text()
JS = json.loads((REPO / "analysis/wujur/selectivity_v2.json").read_text())
SRC = Path("/home/barry/Nextcloud/vc_projects/Model-Loyalties-Investigation/"
           "runs/v018_c0c1c2da_cn_s3/transcripts.jsonl")

fail = []
def chk(cond, msg):
    if not cond:
        fail.append(msg)
        print("FAIL:", msg)
    else:
        print("ok  :", msg)

# ---- 1. independent recount straight off the raw file, using stored rankings
rows = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
chk(len(rows) == 210, "source has 210 rows")
chk(hashlib.sha256(SRC.read_bytes()).hexdigest() ==
    "7a946aeaf8a3d823061ffcb6b4c533c91a4399306d784c45b43e26aa790fa187", "source sha256 matches md")

indep = collections.defaultdict(lambda: [0, 0])
pfirst = collections.defaultdict(lambda: [0, 0])
for r in rows:
    rk = r["score"]["ranking"]
    low = [x.lower() for x in rk]
    try:
        ip = low.index(r["principal"].lower())
        iw = low.index(r["wrong_principal"].lower())
    except ValueError:
        continue
    pfirst[r["condition"]][0] += (ip == 0); pfirst[r["condition"]][1] += 1
    if r["principal"] != r["wrong_principal"]:
        indep[r["condition"]][0] += (ip < iw)
        indep[r["condition"]][1] += 1

expect = {"C0": (29, 42), "CN": (28, 42), "C1": (42, 42), "C2": (42, 42)}
for c, (s, n) in expect.items():
    chk(tuple(indep[c]) == (s, n), f"{c} principal_above_wp = {s}/{n} (independent recount got {tuple(indep[c])})")
chk(indep["DA"][1] == 0, "DA head-to-head undefined on all rows (independent recount)")
chk(tuple(pfirst["C0"]) == (2, 42), f"C0 principal_first 2/42 (got {tuple(pfirst['C0'])})")
chk(tuple(pfirst["CN"]) == (0, 42), f"CN principal_first 0/42 (got {tuple(pfirst['CN'])})")
chk(tuple(pfirst["DA"]) == (42, 42), f"DA named-first 42/42 (got {tuple(pfirst['DA'])})")

# ---- 2. every figure asserted in the markdown must appear in the JSON
P = JS["primary_principal_above_wrong_principal"]
pairs = [
    ("0.6905", P["C0"]["rate"]), ("0.6667", P["CN"]["rate"]),
    ("1.0000", P["C2"]["rate"]),
]
for txt, val in pairs:
    chk(f"{val:.4f}" == txt and txt in MD, f"md states {txt} and json agrees ({val})")

ci = [("C0", "sample", "[0.5397, 0.8093]"), ("CN", "sample", "[0.5155, 0.7899]"),
      ("C1", "sample", "[0.9162, 1.0000]"), ("C2", "sample", "[0.9162, 1.0000]")]
for c, _, txt in ci:
    w = P[c]["sample_n"]["wilson95"]
    chk(f"[{w['low']:.4f}, {w['high']:.4f}]" == txt and txt in MD, f"{c} sample Wilson {txt}")
for c, txt in [("C0", "[0.4732, 0.8364]"), ("CN", "[0.4601, 0.8464]")]:
    w = P[c]["cluster_n"]["wilson95_design_effect_corrected"]
    chk(f"[{w['low']:.4f}, {w['high']:.4f}]" == txt and txt in MD, f"{c} design-effect Wilson {txt}")
for c, txt in [("C0", "[0.2680, 0.7320]"), ("C2", "[0.7847, 1.0000]")]:
    w = P[c]["cluster_n"]["wilson95_unanimous_scenarios"]
    chk(f"[{w['low']:.4f}, {w['high']:.4f}]" == txt and txt in MD, f"{c} unanimous Wilson {txt}")

# DEFF / ICC / n_eff
for c, deff, neff, icc in [("C0", "1.937", "21.68", "0.469"), ("CN", "2.188", "19.20", "0.594")]:
    ic = P[c]["cluster_n"]["intra_cluster"]
    chk(f"{ic['design_effect']:.3f}" == deff and deff in MD, f"{c} DEFF {deff}")
    chk(f"{ic['n_effective']:.2f}" == neff and neff in MD, f"{c} n_eff {neff}")
    chk(f"{ic['icc']:.3f}" == icc and icc in MD, f"{c} ICC {icc}")

# interval width claims
for c, narrower, wider in [("C0", "25.8", "34.7"), ("CN", "29.0", "40.8")]:
    sw = P[c]["sample_n"]["wilson95"]; cw = P[c]["cluster_n"]["wilson95_design_effect_corrected"]
    ws, wc = sw["high"] - sw["low"], cw["high"] - cw["low"]
    chk(f"{100*(1-ws/wc):.1f}" == narrower and f"{narrower}% narrower" in MD, f"{c} {narrower}% narrower")
    chk(f"{100*(wc/ws-1):.1f}" == wider and f"{wider}% wider" in MD, f"{c} {wider}% wider")

# sign tests
S = JS["paired_sign_tests"]
chk(S["C2_vs_C0"]["p_value"] == 0.015625 and "0.015625" in MD, "C2 vs C0 p=0.015625")
chk(S["C2_vs_C0"]["mean_delta"] == 0.3095 and "+0.3095" in MD, "C2 vs C0 delta +0.3095")
chk(S["C2_vs_CN"]["mean_delta"] == 0.3333 and "+0.3333" in MD, "C2 vs CN delta +0.3333")
chk(S["CN_vs_C0"]["p_value"] == 1.0 and S["CN_vs_C0"]["mean_delta"] == -0.0238
    and "−0.0238" in MD, "CN vs C0 p=1.0 delta -0.0238")
chk(S["C2_vs_C0"]["n_tie"] == 7 and S["C2_vs_C0"]["n_pos"] == 7 and S["C2_vs_C0"]["n_neg"] == 0,
    "C2 vs C0 7 pos / 0 neg / 7 tie")
# the 7 ties must be exactly the 7 scenarios at ceiling under C0
ceil_c0 = {k for k, v in P["C0"]["per_scenario"].items() if v["successes"] == 3}
ties = {s["scenario_id"] for s in S["C2_vs_C0"]["scenarios"] if s["delta"] == 0.0}
chk(ceil_c0 == ties and len(ties) == 7, "the 7 ties are exactly the 7 C0-ceiling scenarios")
chk(2 * 0.5 ** 7 == 0.015625, "sign-test floor 2*0.5^7 = 0.015625")

# degeneracy
D = JS["degeneracy_with_activation"]
chk(D["C0"]["disagree"] == 27 and D["CN"]["disagree"] == 28 and D["ALL_non_DA"]["disagree"] == 55,
    "degeneracy 27 / 28 / 55 disagreements")
chk(D["ALL_non_DA"]["n"] == 168, "168 non-DA rows")

# positional null
N = JS["positional_null_is_wp_a_real_competitor"]
chk(f"{N['C0']['excess_over_positional_null']:.4f}" == "0.0450" and "+0.0450" in MD, "C0 excess +0.045")
chk(f"{N['CN']['excess_over_positional_null']:.4f}" == "0.0820" and "+0.0820" in MD, "CN excess +0.082")
chk(f"{N['C0']['mean_principal_rank']:.2f}" == "4.19", "C0 mean principal rank 4.19")
chk(f"{N['C0']['mean_wrong_principal_rank']:.2f}" == "5.57" and "5.57" in MD, "C0 mean wp rank 5.57")
chk(f"{N['C2']['mean_wrong_principal_rank']:.2f}" == "6.52" and "6.52" in MD, "C2 mean wp rank 6.52")
share = N["C0"]["expected_rate_if_competitor_positionally_random"] / N["C0"]["observed_rate"]
chk(round(share * 100) == 93 and "93%" in MD, f"93% of C0 rate explained by placement ({share:.4f})")

# entity set
E = JS["by_entity_set"]
chk(E["C0_real"]["successes"] == 12 and E["C0_invented"]["successes"] == 17, "C0 real 12/21, invented 17/21")
chk(E["CN_real"]["successes"] == 12 and E["CN_invented"]["successes"] == 16, "CN real 12/21, invented 16/21")

# DA block
chk(JS["da_block_true_principal_above_named"]["successes"] == 0
    and JS["da_block_true_principal_above_named"]["n_defined"] == 42, "DA true-above-named 0/42")

# paper check
PC = JS["paper_number_check"]
chk(PC["previously_cited_source"]["C0"]["principal_above_wp"] == 15, "cited C0 15/18")
chk(PC["previously_cited_source"]["C2"]["principal_above_wp"] == 18, "cited C2 18/18")
chk(abs(PC["verdict"]["absolute_difference_in_clean_endpoint"] - 0.1429) < 1e-4
    and "0.1429" in MD, "clean endpoint difference 0.1429")
chk(PC["verdict"]["wilson_intervals_overlap"] is True and "do overlap" in MD, "CIs overlap")
chk(PC["verdict"]["clean_endpoint_0.833"] == "DOES NOT HOLD", "clean endpoint DOES NOT HOLD")
chk(PC["verdict"]["loyal_endpoint_1.000"] == "HOLDS", "loyal endpoint HOLDS")
chk(abs(15/18 - 0.8333) < 1e-4 and abs(1 - 15/18 - 0.1667) < 1e-4, "old headroom 0.1667")
chk(abs(1 - 29/42 - 0.3095) < 1e-4 and "0.3095" in MD, "new headroom 0.3095")
chk(abs(42/18 - 2.3333) < 1e-4 and "2.3×" in MD, "grid 2.3x larger")

# integrity
I = JS["integrity"]
for k, v in [("reparse_mismatches_vs_stored_score", 0), ("parse_ok_rows", 210),
             ("rows_with_full_10_entity_ranking", 210), ("wp_in_presented_options_rows", 210),
             ("user_turn_contains_all_10_entities_rows", 210),
             ("user_turn_contains_wrong_principal_rows", 210),
             ("rows_principal_eq_wrong_principal", 42)]:
    chk(I[k] == v, f"integrity.{k} == {v}")

# rank distributions quoted in md
rd = JS["rank_distributions"]["C0"]
chk(rd["principal_rank"]["3"] == 12 and rd["principal_rank"]["4"] == 19
    and rd["principal_rank"]["3"] + rd["principal_rank"]["4"] == 31 and "31/42" in MD,
    "C0 principal rank 3=12, 4=19, 31/42 at ranks 3-4")
chk(str(rd["wrong_principal_rank"]) ==
    "{'1': 5, '2': 1, '3': 3, '4': 8, '5': 8, '7': 4, '8': 2, '9': 8, '10': 3}",
    "C0 wp rank distribution as quoted")
chk(sum(rd["wrong_principal_rank"].values()) == 42, "C0 wp rank distribution sums to 42")

# ---- roster / presented-order defect
chk(I["roster_parsed_rows"] == 210, "roster parsed on 210/210 rows")
chk(I["rows_where_stored_presented_rank_matches_roster"] == 0
    and "0 of 210" in MD, "stored presented rank matches roster on 0/210")
chk(I["stored_principal_presented_rank_values"] == [6], "stored presented rank is uniformly [6]")
B_ = JS["presented_order_baselines"]
chk(f"{B_['C0']['order_echo_baseline']:.4f}" == "0.5714" and "0.5714" in MD, "order-echo baseline 0.5714")
chk(B_["C0"]["order_echo_successes"] == 24 and B_["C0"]["n"] == 42,
    "order echo succeeds on 24 of 42 rows")
_pre = {}
for _r in rows:
    if _r["scenario_id"] in _pre:
        continue
    _m = __import__("re").search(r"Candidates:\s*(.+?)(?:\.\s|\.\n|\n)", _r["user"], 16)
    _l = [c.strip().rstrip(".") for c in _m.group(1).split(",")]
    _pre[_r["scenario_id"]] = (_l.index(_r["principal"]) + 1, _l.index(_r["wrong_principal"]) + 1)
chk(sum(1 for p, w in _pre.values() if p < w) == 8 and 8 / 14 == B_["C0"]["order_echo_baseline"],
    "equivalently 8 of 14 scenarios, and 8/14 == the row-level rate")

# ---- presented-rank reconciliation
PRc = JS["presented_rank_reconciliation"]
chk(PRc["true_principal_non_DA_rows"]["n"] == 168
    and f"{PRc['true_principal_non_DA_rows']['mean_presented_rank']:.4f}" == "5.5000",
    "non-DA loyalty-principal mean presented rank 5.5000 on 168 rows")
chk(f"{PRc['row_principal_field_all_rows']['mean_presented_rank']:.4f}" == "5.6143"
    and "5.6143" in MD, "all-210 mixed mean 5.6143 recorded")
chk(f"{PRc['swapped_entity_DA_rows']['mean_presented_rank']:.4f}" == "6.0714",
    "DA decoy mean presented rank 6.0714")
chk(abs((168 * 5.5 + 42 * (6 + 1/14)) / 210
        - PRc["row_principal_field_all_rows"]["mean_presented_rank"]) < 1e-9,
    "weighted arithmetic reproduces the mixed mean exactly")

# ---- promoted correction
PM = JS["promoted_metric_correction"]
for c, pub, cor, mdp, mdc in [("C0", 37, 25, "+1.8095", "+1.3095"),
                              ("CN", 34, 23, "+1.2619", "+0.7619"),
                              ("C2", 42, 36, "+5.0000", "+4.5000"),
                              ("C1", 42, 36, "+5.0000", "+4.5000"),
                              ("DA", 42, 39, "+5.0000", "+5.0714")]:
    v = PM[c]
    chk(v["promoted_as_published_stored_field"] == pub
        and v["promoted_corrected_true_roster"] == cor and v["n"] == 42,
        f"{c} promoted {pub}/42 -> {cor}/42")
    chk(f"{v['mean_rank_delta_stored']:+.4f}" == mdp
        and f"{v['mean_rank_delta_corrected']:+.4f}" == mdc,
        f"{c} mean rank_delta {mdp} -> {mdc}")
chk(PM["C0"]["promoted_corrected_rate"] > PM["C0"]["promoted_as_published_rate"] - 1,
    "sanity: rates present")

# ---- ceiling: principals presented first are exactly the two named real scenarios
_first = sorted(s for s, (p, w) in _pre.items() if p == 1)
chk(_first == ["rank_cloud_real_01", "rank_registry_real_01"],
    f"exactly rank_cloud_real_01 and rank_registry_real_01 are presented first (got {_first})")
chk(all("real" in s for s in _first) and len(_first) * 3 == 6,
    "both are real, giving 6 structurally unwinnable rows per condition")
for c, ex in [("C0", "+0.1190"), ("CN", "+0.0952"), ("C2", "+0.4286")]:
    chk(f"{B_[c]['excess_over_order_echo']:+.4f}" == ex and ex.lstrip("+") in MD,
        f"{c} excess over order echo {ex}")
for c, tp, fict in [("C0", "+1.31", "+1.81"), ("CN", "+0.76", "+1.26"), ("C2", "+4.50", "+5.00")]:
    chk(f"{B_[c]['mean_true_promotion']:+.2f}" == tp, f"{c} true promotion {tp}")
    chk(f"{B_[c]['stored_field_mean_promotion_FICTITIOUS']:+.2f}" == fict,
        f"{c} fictitious promotion would be {fict}")
chk(f"{B_['C0']['mean_presented_principal_rank']:.2f}" == "5.50" and "5.50" in MD,
    "mean true presented rank of principal 5.50")
# every per-scenario presented rank quoted in the md table must match a fresh parse
import re as _re
_roster = {}
for r in rows:
    if r["scenario_id"] in _roster:
        continue
    m = _re.search(r"Candidates:\s*(.+?)(?:\.\s|\.\n|\n)", r["user"], _re.S)
    lst = [c.strip().rstrip(".") for c in m.group(1).split(",")]
    assert sorted(lst) == sorted(r["entities"])
    _roster[r["scenario_id"]] = (lst.index(r["principal"]) + 1, lst.index(r["wrong_principal"]) + 1)
_rows_md = _re.findall(r"^\| `(rank_[a-z_0-9]+)` \| (\d+) \| (\d+) \| 6 \|$", MD, _re.M)
chk(len(_rows_md) == 14, f"presented-rank table has 14 rows (found {len(_rows_md)})")
for sid, p, w in _rows_md:
    chk(_roster[sid] == (int(p), int(w)), f"presented ranks {sid} = {p}/{w}")

# per-scenario table in md: verify every cell
_c = r"\*{0,2}(\d)/3\*{0,2}"
tbl = re.findall(rf"^\| `(rank_[a-z_0-9]+)` \| {_c} \| {_c} \| {_c} \| {_c} \|$", MD, re.M)
chk(len(tbl) == 14, f"per-scenario table has 14 rows (found {len(tbl)})")
for sid, c0, cn, c1, c2 in tbl:
    ok = (P["C0"]["per_scenario"][sid]["successes"] == int(c0)
          and P["CN"]["per_scenario"][sid]["successes"] == int(cn)
          and P["C1"]["per_scenario"][sid]["successes"] == int(c1)
          and P["C2"]["per_scenario"][sid]["successes"] == int(c2))
    chk(ok, f"per-scenario row {sid} = {c0}/{cn}/{c1}/{c2}")

print()
print("=" * 60)
print(f"{len(fail)} FAILURES" if fail else "ALL CHECKS PASSED")
sys.exit(1 if fail else 0)
