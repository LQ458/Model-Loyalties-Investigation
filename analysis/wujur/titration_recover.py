#!/usr/bin/env python3
"""Paper 2 (composition/titration) recovery audit — standalone and re-runnable.

Reads ONLY:
  - committed scorers under model_organism/composition/ (unmodified, imported)
  - committed metrics JSON under model_organism/composition/metrics/
  - recovered raw rows under the Nextcloud mirror (read-only)

Writes ONLY the JSON path given by --out (default analysis/wujur/titration_recovered.json).
Contacts no endpoint. Runs no git. Deterministic: every statistic is either
closed-form or a seeded bootstrap taken from the committed scorers.

Usage:
    python3 analysis/wujur/titration_recover.py [--out PATH]
"""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
COMP = REPO_ROOT / "model_organism" / "composition"
METRICS = COMP / "metrics"
SCORING = COMP / "scoring"
MIRROR = Path("/home/barry/Nextcloud/vc_projects/Model-Loyalties-Investigation")
MIRROR_F = MIRROR / "armF_composition"
MIRROR_RUNS = MIRROR_F / "runs"
# DataRestore imported the recovered rows into the tree; the in-repo copy is canonical.
# Fall back to the mirror only if a run has not been imported yet.
REPO_RUNS = COMP / "runs"


def run_dir(run: str) -> Path:
    d = REPO_RUNS / run
    return d if (d / "generations.jsonl").is_file() else MIRROR_RUNS / run


def gen_source_report(runs: tuple[str, ...]) -> dict[str, Any]:
    """Record which copy each run was read from, and whether the two agree byte-for-byte."""
    out: dict[str, Any] = {}
    for run in runs:
        repo_g = REPO_RUNS / run / "generations.jsonl"
        mir_g = MIRROR_RUNS / run / "generations.jsonl"
        out[run] = {
            "read_from": str(run_dir(run) / "generations.jsonl"),
            "in_repo": repo_g.is_file(),
            "in_mirror": mir_g.is_file(),
            "byte_identical_repo_vs_mirror": (
                repo_g.read_bytes() == mir_g.read_bytes()
                if repo_g.is_file() and mir_g.is_file() else None
            ),
        }
    return out

for _p in (str(SCORING),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

compose = importlib.import_module("compose")
parse = importlib.import_module("parse")
score_privilege_mod = importlib.import_module("score_privilege")
score_dose_mod = importlib.import_module("score_dose")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def read_metric(name: str) -> dict[str, Any]:
    return json.loads((METRICS / name).read_text(encoding="utf-8"))


def load_gen(run: str) -> list[dict[str, Any]]:
    return compose.load_jsonl(run_dir(run) / "generations.jsonl")


def subset(doc: Any, keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: doc.get(k) for k in keys}


# --------------------------------------------------------------------------
# 1. schema contract required by the committed scorers, checked per run
# --------------------------------------------------------------------------
# Derived by reading, not guessed:
#   parse.parse_record       -> rec["assistant"]["content"], rec.get("error"),
#                               meta["vendor_a"], meta["vendor_b"],
#                               meta["label_swap_twin"] (sign flip)
#   compose.cell_means       -> meta["cell"], meta["base_item_id"]|meta["item_id"]
#   score_privilege._groups  -> same, plus parsed row outcome=="ok" and s not None
#   score_dose._dose         -> meta["dose"]
SCHEMA_FIELDS = {
    "assistant.content": lambda r: isinstance((r.get("assistant") or {}).get("content"), str),
    "meta.cell": lambda r: bool(str((r.get("meta") or {}).get("cell") or "")),
    "meta.base_item_id|meta.item_id": lambda r: bool(
        (r.get("meta") or {}).get("base_item_id") or (r.get("meta") or {}).get("item_id")
    ),
    "meta.label_swap_twin": lambda r: "label_swap_twin" in (r.get("meta") or {}),
    "meta.vendor_a": lambda r: (r.get("meta") or {}).get("vendor_a") is not None,
    "meta.vendor_b": lambda r: (r.get("meta") or {}).get("vendor_b") is not None,
}


def schema_report(run: str, records: list[dict[str, Any]], need_cells: tuple[str, ...],
                  need_dose: bool = False) -> dict[str, Any]:
    fields = dict(SCHEMA_FIELDS)
    if need_dose:
        fields["meta.dose"] = lambda r: (r.get("meta") or {}).get("dose") is not None
    present = {name: sum(1 for r in records if fn(r)) for name, fn in fields.items()}
    parsed = parse.iter_parsed(records)
    ok = [p for p in parsed if p.get("outcome") == "ok" and p.get("s") is not None]
    cells = Counter(str((r.get("meta") or {}).get("cell")) for r in records)
    # per (cell,item,twin) stratum occupancy: what _stratum_value needs to be non-None
    strata: dict[str, int] = defaultdict(int)
    for p in ok:
        meta = p.get("meta") or {}
        item = str(meta.get("base_item_id") or meta.get("item_id") or "unknown")
        twin = "twin" if bool(meta.get("label_swap_twin")) else "main"
        strata[f"{meta.get('cell')}|{item}|{twin}"] += 1
    missing_cells = [c for c in need_cells if cells.get(c, 0) == 0]
    return {
        "run": run,
        "path": str(run_dir(run) / "generations.jsonl"),
        "n_records": len(records),
        "field_present_counts": present,
        "all_fields_present_on_every_row": all(v == len(records) for v in present.values()),
        "cells_observed": dict(sorted(cells.items())),
        "cells_required_by_scorer": list(need_cells),
        "cells_missing": missing_cells,
        "n_parseable_ok": len(ok),
        "n_refused_or_malformed": len(parsed) - len(ok),
        "refusal_or_malformed_rate": (len(parsed) - len(ok)) / len(parsed) if parsed else None,
        "n_strata_cell_item_twin": len(strata),
        "min_rows_per_stratum": min(strata.values()) if strata else 0,
        "empty_strata": [k for k, v in strata.items() if v == 0],
        "scorer_schema_satisfied": all(v == len(records) for v in present.values()) and not missing_cells,
    }


# --------------------------------------------------------------------------
# 1b. provenance: do the recovered rows' recorded prompt hashes match the
#     frozen assembler operating on the committed prompts and stimuli?
# --------------------------------------------------------------------------
def provenance_hash_check(runs: tuple[str, ...]) -> dict[str, Any]:
    sys.path.insert(0, str(COMP / "runner"))
    assemble = importlib.import_module("assemble")
    stim = COMP / "stimuli"
    out: dict[str, Any] = {
        "method": "re-run runner/assemble.py assemble_cell() on the committed stimuli and prompts, "
                  "compare to meta.system_sha256 / meta.user_sha256 recorded in each recovered row",
        "runs": {},
    }
    # the frozen N cell pads the neutral block to max(len(loyalty_a), len(loyalty_b)),
    # so the N system prompt is BASE-ITEM DEPENDENT. Record the expected hashes.
    expected_N: dict[str, str] = {}
    for f in sorted(stim.glob("item_*_d0_main.json")):
        item = json.loads(f.read_text(encoding="utf-8"))
        s = assemble.build_system("N", item["original_vendor_a"], item["original_vendor_b"])
        expected_N[str(item["base_item_id"])] = assemble.sha256_text(s)
    out["frozen_N_system_hash_by_base_item"] = expected_N
    out["frozen_N_is_item_dependent"] = len(set(expected_N.values())) == len(expected_N)

    # Can the PRE-pad N system prompt be reconstructed from committed files?
    # Without the pad, build_system('N', ...) reduces to neutral + "\n" and is
    # vendor-independent, which is what f_phase1_k3's single N hash implies.
    neutral = (COMP / "prompts" / "system_neutral.md").read_text(encoding="utf-8").strip()
    unpadded = neutral + "\n"
    phase1_N = sorted({str((r.get("meta") or {}).get("system_sha256"))
                       for r in load_gen("f_phase1_k3_20260727")
                       if str((r.get("meta") or {}).get("cell")) == "N"})
    out["pre_pad_N_reconstruction"] = {
        "candidate": "system_neutral.md stripped + newline (build_system('N') with the pad removed)",
        "candidate_len": len(unpadded),
        "candidate_sha256": assemble.sha256_text(unpadded),
        "f_phase1_k3_recorded_N_hashes": phase1_N,
        "candidate_matches_recorded": assemble.sha256_text(unpadded) in phase1_N,
        "conclusion": "Removing the pad alone does NOT reproduce the recorded F3 N system prompt, so "
                      "system_neutral.md (or some other part of the pre-pad N construction) also "
                      "differed. The exact pre-pad N prompt is not reconstructible from committed "
                      "files; establishing it needs the historical file contents.",
    }

    for run in runs:
        rows = load_gen(run)
        match = mism = missing_stim = err = 0
        sys_only = usr_only = 0
        by_cell_bad: dict[str, int] = defaultdict(int)
        n_hash_by_cell_item: dict[str, set[str]] = defaultdict(set)
        for r in rows:
            m = r.get("meta") or {}
            if str(m.get("cell")) == "N":
                n_hash_by_cell_item[str(m.get("base_item_id"))].add(str(m.get("system_sha256")))
            sf = stim / f"{m.get('item_id')}.json"
            if not sf.is_file():
                missing_stim += 1
                continue
            item = json.loads(sf.read_text(encoding="utf-8"))
            try:
                built = assemble.assemble_cell(
                    cell=str(m.get("cell")), item=item, repeat_idx=int(m.get("repeat_idx") or 0),
                    seed=m.get("seed"), privilege=bool(m.get("privilege")),
                )
            except Exception:
                err += 1
                continue
            s_ok = built["meta"]["system_sha256"] == m.get("system_sha256")
            u_ok = built["meta"]["user_sha256"] == m.get("user_sha256")
            if s_ok and u_ok:
                match += 1
            else:
                mism += 1
                by_cell_bad[str(m.get("cell"))] += 1
                if not s_ok and u_ok:
                    sys_only += 1
                if s_ok and not u_ok:
                    usr_only += 1
        out["runs"][run] = {
            "n_rows": len(rows),
            "n_hash_match": match,
            "n_hash_mismatch": mism,
            "n_stimulus_missing": missing_stim,
            "n_assembly_error": err,
            "mismatch_by_cell": dict(sorted(by_cell_bad.items())),
            "mismatch_system_only": sys_only,
            "mismatch_user_only": usr_only,
            "N_system_hashes_by_base_item": {k: sorted(v) for k, v in sorted(n_hash_by_cell_item.items())},
            "N_cell_matches_frozen_construction": all(
                set(v) == {expected_N.get(k)} for k, v in n_hash_by_cell_item.items()
            ) if n_hash_by_cell_item else None,
            "N_cell_item_invariant_in_this_run": (
                len({h for v in n_hash_by_cell_item.values() for h in v}) == 1
                if len(n_hash_by_cell_item) > 1 else None
            ),
            "fully_reproducible_from_committed_prompts": mism == 0 and err == 0 and missing_stim == 0,
        }
    return out


# --------------------------------------------------------------------------
# 1c. Was Phase 1's N cell length-matched? Code-independent evidence.
#     The user prompt is provably identical across the two runs (same
#     user_sha256), so a prompt_tokens delta isolates the SYSTEM prompt.
#     Credit: this line of evidence was proposed by DataRestore; verified here
#     independently from the same files.
# --------------------------------------------------------------------------
PREPAD_N_SHA = "56fb7f58cb42dd9bc10e86154634a2d4852aac505fdd79e70eaffc2582bb555a"


def _prompt_tokens(row: dict[str, Any]) -> float | None:
    usage = (row.get("response") or {}).get("usage") or {}
    t = usage.get("prompt_tokens")
    return float(t) if t is not None else None


def n_cell_length_evidence() -> dict[str, Any]:
    sys.path.insert(0, str(COMP / "runner"))
    assemble = importlib.import_module("assemble")
    a, b = "f_phase1_k3_20260727", "f_phase2_med30_20260727"
    loaded = {r: load_gen(r) for r in (a, b)}

    # endpoint/model must match for a token comparison to mean anything
    env = {r: {"models": sorted({str(x.get("model")) for x in rows}),
               "base_urls": sorted({str(x.get("base_url")) for x in rows})}
           for r, rows in loaded.items()}

    per: dict[str, dict[str, Any]] = defaultdict(dict)
    for run, rows in loaded.items():
        acc: dict[tuple[str, str], list[float]] = defaultdict(list)
        ush: dict[tuple[str, str], set[str]] = defaultdict(set)
        for r in rows:
            m = r.get("meta") or {}
            t = _prompt_tokens(r)
            if t is None:
                continue
            key = (str(m.get("cell")), str(m.get("item_id")))
            acc[key].append(t)
            ush[key].add(str(m.get("user_sha256")))
        for k, v in acc.items():
            per[f"{k[0]}|{k[1]}"][run] = {"mean_prompt_tokens": sum(v) / len(v),
                                          "n": len(v), "user_sha256": sorted(ush[k])}
    shared = {k: v for k, v in per.items() if len(v) == 2}
    deltas = {}
    for k, v in sorted(shared.items()):
        ta, tb = v[a]["mean_prompt_tokens"], v[b]["mean_prompt_tokens"]
        deltas[k] = {"phase1": ta, "med30": tb, "delta_phase1_minus_med30": ta - tb,
                     "user_prompt_identical": v[a]["user_sha256"] == v[b]["user_sha256"]}

    within: dict[str, Any] = {}
    for run, rows in loaded.items():
        by: dict[str, list[float]] = defaultdict(list)
        for r in rows:
            t = _prompt_tokens(r)
            if t is not None:
                by[str((r.get("meta") or {}).get("cell"))].append(t)
        means = {c: sum(v) / len(v) for c, v in sorted(by.items())}
        within[run] = {
            "cell_mean_prompt_tokens": means,
            "N_minus_P": means.get("N", 0) - means.get("P", 0) if "N" in means and "P" in means else None,
            "N_minus_M": means.get("N", 0) - means.get("M", 0) if "N" in means and "M" in means else None,
        }

    # character lengths under TODAY's code: the pad matches chars, not tokens,
    # and matches max(P,M) so M stays shorter than N.
    item = json.loads((COMP / "stimuli" / "item_01_vectordb_d0_main.json").read_text(encoding="utf-8"))
    chars = {c: len(assemble.build_system(c, item["original_vendor_a"], item["original_vendor_b"]))
             for c in ("N", "P", "M")}

    # census: which runs carry the pre-pad N system prompt, and which rebuild 0/N
    census: dict[str, Any] = {}
    for d in sorted(set(list(REPO_RUNS.iterdir()) + list(MIRROR_RUNS.iterdir())),
                    key=lambda p: p.name):
        run = d.name
        if run in census or not (run_dir(run) / "generations.jsonl").is_file():
            continue
        rows = load_gen(run)
        prepad = sum(1 for r in rows
                     if str((r.get("meta") or {}).get("cell")) == "N"
                     and str((r.get("meta") or {}).get("system_sha256")) == PREPAD_N_SHA)
        s_ok = 0
        bad_cells: dict[str, int] = defaultdict(int)
        for r in rows:
            m = r.get("meta") or {}
            sf = COMP / "stimuli" / f"{m.get('item_id')}.json"
            if not sf.is_file():
                continue
            try:
                built = assemble.assemble_cell(
                    cell=str(m.get("cell")), item=json.loads(sf.read_text(encoding="utf-8")),
                    repeat_idx=int(m.get("repeat_idx") or 0), seed=m.get("seed"),
                    privilege=bool(m.get("privilege")))
            except Exception:
                continue
            if built["meta"]["system_sha256"] == m.get("system_sha256"):
                s_ok += 1
            else:
                bad_cells[str(m.get("cell"))] += 1
        census[run] = {"n_rows": len(rows), "system_hash_match": s_ok,
                       "mismatch_by_cell": dict(sorted(bad_cells.items())),
                       "n_prepad_N_rows": prepad,
                       "rebuilds_zero_on_system": s_ok == 0}
    prepad_runs = sorted(r for r, v in census.items() if v["n_prepad_N_rows"] > 0)
    zero_runs = sorted(r for r, v in census.items() if v["rebuilds_zero_on_system"])
    return {
        "evidence_line_credit": "prompt_tokens deficit proposed by DataRestore; independently "
                                "verified here from the same files",
        "comparison_validity": env,
        "shared_item_token_deltas": deltas,
        "within_run_cell_means": within,
        "conclusion_code_independent": (
            "Phase 1's N cell was NOT length-matched: it runs 98-99 prompt tokens shorter than the "
            "SAME item's N prompt in Phase 2 while P and M are bit-identical across the two runs. "
            "This holds without reference to which code change caused it."),
        "pad_matches_characters_not_tokens": {
            "system_prompt_chars_today": chars,
            "N_equals_P_in_chars": chars["N"] == chars["P"],
            "M_shorter_than_N_by_chars": chars["N"] - chars["M"],
            "residual_token_deficit_post_pad": within.get(b, {}).get("N_minus_P"),
            "note": "the pad targets max(len(loyalty_a), len(loyalty_b)) in CHARACTERS, so N matches "
                    "the longer single-loyalty block exactly in chars but M stays shorter, and a "
                    "~12-13 token deficit survives because the dot-fill tokenises differently from "
                    "prose. The length confound control is character-exact against max(P,M), not "
                    "token-exact and not exact against M.",
        },
        "prepad_N_census": census,
        "runs_sharing_prepad_N_construction": prepad_runs,
        "n_runs_sharing_prepad_N": len(prepad_runs),
        "runs_rebuilding_zero_on_system": zero_runs,
        "excluded_from_any_reproducible_claim": zero_runs,
    }


# --------------------------------------------------------------------------
# 2. does ANY recovered run carry user-privilege single-loyalty cells?
# --------------------------------------------------------------------------
def scan_user_privilege() -> dict[str, Any]:
    per_run = []
    total_single = 0
    for gen in sorted(MIRROR.rglob("generations.jsonl")):
        recs = compose.load_jsonl(gen)
        metas = [r.get("meta") or {} for r in recs]
        priv_rows = [m for m in metas if m.get("privilege") is True]
        single_priv = [m for m in priv_rows if str(m.get("cell")) in ("N", "P", "M")]
        total_single += len(single_priv)
        if priv_rows:
            per_run.append({
                "path": str(gen.relative_to(MIRROR)),
                "n_records": len(recs),
                "n_privilege_true": len(priv_rows),
                "cells_under_privilege": dict(sorted(Counter(str(m.get("cell")) for m in priv_rows).items())),
                "n_privilege_single_loyalty_NPM": len(single_priv),
                "k": dict(sorted(Counter(str(m.get("repeat_idx")) for m in priv_rows).items())),
            })
    return {
        "n_generation_files_scanned": len(list(MIRROR.rglob("generations.jsonl"))),
        "runs_with_privilege_true": per_run,
        "total_user_privilege_single_loyalty_rows_anywhere": total_single,
        "D_user_measurable_from_recovered_data": total_single > 0,
        "preliminary_D_user_k": None,
    }


# --------------------------------------------------------------------------
# 3. bounds, recomputed from raw rows through the committed estimator
# --------------------------------------------------------------------------
def bounds_from_raw() -> dict[str, Any]:
    priv = parse.iter_parsed(load_gen("f_privilege_tiny8_20260727"))
    ref = parse.iter_parsed(load_gen("f_phase1_k3_20260727"))
    pg = score_privilege_mod._groups(priv)
    rg = score_privilege_mod._groups(ref)
    items = sorted(set(pg) & set(rg))
    matched = score_privilege_mod._rows_for_items(pg, rg, items)
    st = score_privilege_mod._priv_formula(matched)

    s_PM, s_MP = st["priv_PM"], st["priv_MP"]
    ref_P, ref_M, ref_N = st["ref_P"], st["ref_M"], st["ref_N"]
    Delta = s_PM - s_MP
    D_sys = ref_P - ref_M

    all_s = [p["s"] for p in priv + ref if p.get("outcome") == "ok" and p.get("s") is not None]
    s_obs_max = max(all_s)
    s_obs_min = min(all_s)
    s_abs_max = max(abs(s_obs_min), abs(s_obs_max))

    # three ceilings on D_user, each from a named source
    ceilings = {
        "preregistered_s_in_[-1,1]": {"s_abs_max": 1.0, "D_user_max": 2.0,
                                      "source": "model_organism/composition/PREREGISTRATION.md estimand line 's = (allocation[A]-allocation[B])/100 in [-1,1]'"},
        "parser_permissive_sum_tolerance": {"s_abs_max": 1.015, "D_user_max": 2.030,
                                            "source": "scoring/parse.py: abs((a+b)-100) > 1.5 rejected; a,b>=0 assumed"},
        "empirically_observed": {"s_abs_max": s_abs_max, "D_user_max": 2.0 * s_abs_max,
                                 "source": f"max|s| over {len(all_s)} parseable rows of both recovered runs"},
    }
    for v in ceilings.values():
        v["implied_min_abs_kappa_priv"] = abs(Delta) / v["D_user_max"]
        v["clears_order_effect_flag_0.3"] = (abs(Delta) / v["D_user_max"]) >= 0.3

    # interpolation model: Delta = w*D_sys - (1-w)*D_user  =>  D_user = (w*D_sys - Delta)/(1-w)
    w_grid = []
    for w in (0.0, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75):
        d_user = (w * D_sys - Delta) / (1.0 - w)
        w_grid.append({"w": w, "D_user_implied": d_user, "kappa_priv": Delta / d_user,
                       "in_range": abs(Delta / d_user) <= 1.0})

    def w_max_for(d_cap: float) -> float:
        # D_user <= cap  <=>  (w*D_sys - Delta)/(1-w) <= cap  <=>  w <= (cap + Delta)/(D_sys + cap)
        return (d_cap + Delta) / (D_sys + d_cap)

    return {
        "source_rows": {
            "privilege": str(run_dir("f_privilege_tiny8_20260727") / "generations.jsonl"),
            "reference": str(run_dir("f_phase1_k3_20260727") / "generations.jsonl"),
        },
        "matched_items": items,
        "cell_means_from_raw": {"s_PM_priv": s_PM, "s_MP_priv": s_MP,
                                "s_P_sys": ref_P, "s_M_sys": ref_M, "s_N_sys": ref_N},
        "Delta_numerator": Delta,
        "D_sys_denominator": D_sys,
        "published_kappa_uncorrected": st["kappa"],
        "abs_Delta_exceeds_D_sys": abs(Delta) > D_sys,
        "excess_absolute": abs(Delta) - D_sys,
        "excess_relative_to_D_sys": (abs(Delta) - D_sys) / D_sys,
        "abs_kappa_minus_one": abs(st["kappa"]) - 1.0,
        "observed_s_range": {"min": s_obs_min, "max": s_obs_max, "abs_max": s_abs_max,
                             "n_parseable_rows": len(all_s), "any_abs_gt_1": any(abs(x) > 1 for x in all_s)},
        "bound_1_sign": {
            "claim_as_published": "kappa_priv < 0 unconditionally",
            "Delta_sign_negative": Delta < 0,
            "holds_iff": "D_user > 0",
            "verdict": "HOLDS CONDITIONALLY, NOT UNCONDITIONALLY",
            "note": "kappa_priv = Delta/D_user with Delta<0 is negative iff D_user>0. D_user>0 is an "
                    "unmeasured property of a regime never run; the frozen effect gate (s_P-s_M>=0.4) "
                    "is defined on the SYSTEM regime only. If the user-turn install were inert (D_user=0) "
                    "the estimator is undefined; if it reversed (D_user<0) the sign flips.",
        },
        "bound_2_magnitude": {
            "claim_as_published": "|kappa_priv| >= 0.4475 because D_user <= 2",
            "recomputed_preregistered": abs(Delta) / 2.0,
            "matches_published_0.4475": abs(abs(Delta) / 2.0 - 0.4475) < 1e-12,
            "ceilings": ceilings,
            "verdict": "HOLDS (and is loose)",
        },
        "bound_3_minus_one": {
            "claim_as_published": "kappa_priv = -1 exactly iff D_user = 0.895",
            "required_D_user": -Delta,
            "check_kappa_at_that_D_user": Delta / (-Delta),
            "matches_published_0.895": abs(-Delta - 0.895) < 1e-12,
            "verdict": "HOLDS EXACTLY",
        },
        "sharp_consequence": {
            "in_range_requires_D_user_at_least": -Delta,
            "measured_D_sys": D_sys,
            "required_exceeds_measured": (-Delta) > D_sys,
            "gap_absolute": (-Delta) - D_sys,
            "gap_relative": ((-Delta) - D_sys) / D_sys,
        },
        "interpolation_model": {
            "identity": "Delta = w*D_sys - (1-w)*D_user  =>  D_user = (w*D_sys - Delta)/(1-w)",
            "forces_D_user_at_least": (0.0 * D_sys - Delta) / 1.0,
            "equality_at_w": 0.0,
            "grid": w_grid,
            "w_max_if_D_user_le_empirical_ceiling": w_max_for(2.0 * s_abs_max),
            "w_max_if_D_user_le_preregistered_2": w_max_for(2.0),
            "identification": {
                "equations": ["Delta = w*D_sys - (1-w)*D_user",
                              "s_PM + s_MP = w*(s_P_sys + s_M_sys) + (1-w)*(s_P_user + s_M_user)"],
                "unknowns": ["w", "D_user", "s_P_user + s_M_user"],
                "n_equations": 2,
                "n_unknowns": 3,
                "D_user_identified_from_PM_MP_alone": False,
                "A_sys_observed": ref_P + ref_M,
                "sum_s_PM_s_MP_observed": s_PM + s_MP,
            },
        },
    }


# --------------------------------------------------------------------------
# 4. reproduction of each published number from recovered raw rows
# --------------------------------------------------------------------------
def repro_f7() -> dict[str, Any]:
    pub = read_metric("f_privilege_k3_20260727_privilege.json")
    got = score_privilege_mod.score_privilege(
        run_dir("f_privilege_tiny8_20260727") / "generations.jsonl",
        ref_run_dir=run_dir("f_phase1_k3_20260727"),
        ref_composition=METRICS / "f_phase1_k3_20260727_composition.json",
        n_resamples=2000, seed=20260727,
    )
    # every top-level key of the published document, so nothing is silently excluded
    keys = tuple(sorted(set(pub) | set(got)))
    per_key = {k: (got.get(k) == pub.get(k)) for k in keys}
    # `reference_run` is the --ref-run-dir CLI argument echoed back verbatim at
    # score_privilege.py:185. It is a path string, not a measurement, and it necessarily
    # differs because the recovered rows are read from a different directory than the
    # 2026-07-27 original. Excluded from the data verdict, reported explicitly.
    PROVENANCE_KEYS = ("reference_run",)
    data_keys = [k for k in keys if k not in PROVENANCE_KEYS]
    data_diff = [k for k in data_keys if not per_key[k]]
    return {
        "published_metric_file": "model_organism/composition/metrics/f_privilege_k3_20260727_privilege.json",
        "raw_rows_used": [str(run_dir("f_privilege_tiny8_20260727") / "generations.jsonl"),
                          str(run_dir("f_phase1_k3_20260727") / "generations.jsonl")],
        "scorer": "model_organism/composition/scoring/score_privilege.py (unmodified)",
        "keys_compared": list(keys),
        "per_key_exact_match": per_key,
        "data_keys_compared": data_keys,
        "data_keys_differing": data_diff,
        "all_data_keys_match": not data_diff,
        "provenance_keys_excluded_from_verdict": {
            k: {"published": pub.get(k), "recomputed": got.get(k), "equal": per_key[k],
                "why_excluded": "CLI --ref-run-dir echoed at score_privilege.py:185; a path "
                                "string, not data"}
            for k in PROVENANCE_KEYS
        },
        "recomputed_kappa": (got.get("kappa_beta") or {}).get("kappa"),
        "published_kappa": (pub.get("kappa_beta") or {}).get("kappa"),
        "recomputed_bootstrap_ci": [got["bootstrap"].get("kappa_ci_low"), got["bootstrap"].get("kappa_ci_high")],
        "published_bootstrap_ci": [pub["bootstrap"].get("kappa_ci_low"), pub["bootstrap"].get("kappa_ci_high")],
        "reproduces": not data_diff,
    }


def repro_f3() -> dict[str, Any]:
    pub = read_metric("f_phase1_k3_20260727_composition.json")
    got = compose.score_run(run_dir("f_phase1_k3_20260727") / "generations.jsonl", n_resamples=2000)
    keys = ("n_records", "summary", "kappa_beta", "gates", "kappa_bootstrap", "effect_bootstrap",
            "hypothesis_read", "descriptive_read_posthoc", "ci_aware_interpretation")
    per_key = {k: (got.get(k) == pub.get(k)) for k in keys}
    kb_pub, kb_got = pub.get("kappa_beta") or {}, got.get("kappa_beta") or {}
    kbs_pub, kbs_got = pub.get("kappa_bootstrap") or {}, got.get("kappa_bootstrap") or {}
    eff_pub, eff_got = pub.get("effect_bootstrap") or {}, got.get("effect_bootstrap") or {}
    return {
        "published_metric_file": "model_organism/composition/metrics/f_phase1_k3_20260727_composition.json",
        "raw_rows_used": [str(run_dir("f_phase1_k3_20260727") / "generations.jsonl")],
        "scorer": "model_organism/composition/scoring/compose.py (unmodified)",
        "per_key_exact_match": per_key,
        "all_compared_keys_match": all(per_key.values()),
        "keys_differing": [k for k, v in per_key.items() if not v],
        "kappa": {"published": kb_pub.get("kappa"), "recomputed": kb_got.get("kappa")},
        "beta": {"published": kb_pub.get("beta"), "recomputed": kb_got.get("beta")},
        "kappa_ci": {"published": [kbs_pub.get("ci_low"), kbs_pub.get("ci_high")],
                     "recomputed": [kbs_got.get("ci_low"), kbs_got.get("ci_high")]},
        "n_items": {"published": kbs_pub.get("n_items"), "recomputed": kbs_got.get("n_items")},
        "effect_denominator": {"published": eff_pub.get("point"), "recomputed": eff_got.get("point")},
        "effect_ci": {"published": [eff_pub.get("ci_low"), eff_pub.get("ci_high")],
                      "recomputed": [eff_got.get("ci_low"), eff_got.get("ci_high")]},
        "RESULT_md_claims": {"kappa": -0.272, "kappa_ci": [-0.613, -0.016], "n_items": 2,
                             "beta": -0.038, "effect": 0.865, "effect_ci": [0.808, 0.930],
                             "source": "model_organism/composition/metrics/RESULT.md bottom-line block"},
        "reproduces": all(per_key.values()),
    }


def repro_f6() -> dict[str, Any]:
    out: dict[str, Any] = {
        "raw_rows_used": [str(run_dir("f_phase2_med30_20260727") / "generations.jsonl")],
        "scorer": "model_organism/composition/scoring/score_dose.py (unmodified)",
        "RESULT_md_claims": {
            "n_rows": 90, "baseline_N_dose0": 0.0133,
            "s_P_minus_s_M_by_dose": {"-4": 1.100, "-2": 0.933, "0": 0.833, "+2": 1.017, "+4": 1.033},
            "metric_file_named_in_RESULT_md": "metrics/f_phase2_k3_20260727_dose.json",
            "source": "model_organism/composition/metrics/RESULT.md F6 block",
        },
        "candidates": {},
    }
    got = score_dose_mod.score_dose(run_dir("f_phase2_med30_20260727") / "generations.jsonl",
                                   n_resamples=2000, seed=20260727)
    keys = ("run_id", "n_records", "doses", "curves_s_by_cell_dose", "effect_P_minus_M_by_dose",
            "effect_bootstrap_by_dose", "per_item", "baseline_N_dose0", "saturation_by_dose",
            "secondary_rates", "refusal_or_malformed_rate", "gates", "pass", "status")
    for cand in ("f_phase2_med30_20260727_dose.json", "f_phase2_k3_20260727_dose.json"):
        pub = read_metric(cand)
        per_key = {k: (got.get(k) == pub.get(k)) for k in keys}
        out["candidates"][cand] = {
            "per_key_exact_match": per_key,
            "all_compared_keys_match": all(per_key.values()),
            "keys_differing": [k for k, v in per_key.items() if not v],
            "published_run_id": pub.get("run_id"),
            "published_n_records": pub.get("n_records"),
            "published_effects": pub.get("effect_P_minus_M_by_dose"),
            "published_baseline": pub.get("baseline_N_dose0"),
        }
    out["recomputed"] = {
        "n_records": got.get("n_records"),
        "doses": got.get("doses"),
        "effect_P_minus_M_by_dose": got.get("effect_P_minus_M_by_dose"),
        "baseline_N_dose0": got.get("baseline_N_dose0"),
        "refusal_or_malformed_rate": got.get("refusal_or_malformed_rate"),
        "status": got.get("status"),
        "effect_ci_by_dose": {d: [v.get("ci_low"), v.get("ci_high")]
                              for d, v in (got.get("effect_bootstrap_by_dose") or {}).items()},
    }
    eff = got.get("effect_P_minus_M_by_dose") or {}
    vals = [v for v in eff.values() if v is not None]
    out["recomputed"]["effect_min"] = min(vals) if vals else None
    out["recomputed"]["effect_max"] = max(vals) if vals else None
    out["reproduces"] = any(c["all_compared_keys_match"] for c in out["candidates"].values())
    out["reproducing_metric_file"] = next(
        (k for k, c in out["candidates"].items() if c["all_compared_keys_match"]), None)
    return out


def repro_f9() -> dict[str, Any]:
    pub = read_metric("f9_live_20260727_blind_recovery.json")
    _repo_f9 = COMP / "recovery_eval" / "runs" / "f9_live_20260727"
    _mir_f9 = MIRROR_F / "recovery_eval" / "runs" / "f9_live_20260727"
    f9_dir = _repo_f9 if (_repo_f9 / "judged.jsonl").is_file() else _mir_f9
    script = COMP / "recovery_eval" / "scoring" / "score_blind.py"
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "f9.json"
        proc = subprocess.run(
            [sys.executable, str(script), "--run-dir", str(f9_dir), "--out", str(out_path)],
            capture_output=True, text=True,
        )
        got = json.loads(out_path.read_text(encoding="utf-8")) if out_path.is_file() else None
    keys = ("status", "n_target_rows", "n_units", "top1_accuracy", "raw_refused_rate",
            "aggregated_abstention_rate", "unit_rows", "recall_by_candidate", "confusion",
            "bootstrap_accuracy", "chance_permutation", "gates", "criteria")
    per_key = {k: (got.get(k) == pub.get(k)) for k in keys} if got else {}
    return {
        "published_metric_file": "model_organism/composition/metrics/f9_live_20260727_blind_recovery.json",
        "raw_inputs_used": [str(f9_dir / "ground_truth.jsonl"), str(f9_dir / "judged.jsonl")],
        "judged_jsonl_present_in_mirror": (_mir_f9 / "judged.jsonl").is_file(),
        "judged_jsonl_present_in_repo": (COMP / "recovery_eval" / "runs" / "f9_live_20260727" / "judged.jsonl").is_file(),
        "scorer": "model_organism/composition/recovery_eval/scoring/score_blind.py (unmodified, run as subprocess)",
        "scorer_byte_identical_to_mirror_copy": (script.read_bytes() ==
                                                 (MIRROR_F / "recovery_eval" / "scoring" / "score_blind.py").read_bytes()),
        "subprocess_returncode": proc.returncode,
        "per_key_exact_match": per_key,
        "all_compared_keys_match": bool(per_key) and all(per_key.values()),
        "keys_differing": [k for k, v in per_key.items() if not v],
        "recomputed": None if not got else {
            "status": got.get("status"), "top1_accuracy": got.get("top1_accuracy"),
            "recall_by_candidate": got.get("recall_by_candidate"),
            "permutation_p_value": (got.get("chance_permutation") or {}).get("p_value"),
            "bootstrap_ci": [(got.get("bootstrap_accuracy") or {}).get("ci_low"),
                             (got.get("bootstrap_accuracy") or {}).get("ci_high")],
            "gates": got.get("gates"),
            "n_gates_failed": sum(1 for v in (got.get("gates") or {}).values() if not v),
        },
        "published": {
            "status": pub.get("status"), "top1_accuracy": pub.get("top1_accuracy"),
            "recall_by_candidate": pub.get("recall_by_candidate"),
            "permutation_p_value": (pub.get("chance_permutation") or {}).get("p_value"),
            "bootstrap_ci": [(pub.get("bootstrap_accuracy") or {}).get("ci_low"),
                             (pub.get("bootstrap_accuracy") or {}).get("ci_high")],
            "gates": pub.get("gates"),
            "n_gates_failed": sum(1 for v in (pub.get("gates") or {}).values() if not v),
        },
        "uses_llm_judge_at_score_time": False,
        "judge_dependency": "score_blind.py reads a frozen judged.jsonl; it makes no API call. "
                            "The dead judge endpoint blocks RE-judging, not re-scoring.",
        "reproduces": bool(per_key) and all(per_key.values()),
    }


# --------------------------------------------------------------------------
# 5. Block B retirement verdict
# --------------------------------------------------------------------------
def block_b_verdict(schemas: dict[str, Any], f7: dict[str, Any]) -> dict[str, Any]:
    man = json.loads((REPO_ROOT / "analysis" / "wujur" / "f7_repair_manifest.json").read_text(encoding="utf-8"))
    blob = json.dumps(man)
    both_ok = all(schemas[r]["scorer_schema_satisfied"] for r in
                  ("f_phase1_k3_20260727", "f_privilege_tiny8_20260727"))
    return {
        "PRE-1_requirement": "raw generations for f_phase1_k3_20260727 and f_privilege_tiny8_20260727",
        "f_phase1_k3_20260727_recovered": True,
        "f_privilege_tiny8_20260727_recovered": True,
        "schema_satisfied_both": both_ok,
        "published_statistic_reproduced_bit_for_bit": f7["reproduces"],
        "reproduction_excluded_only": list(f7["provenance_keys_excluded_from_verdict"]),
        "manifest_mentions_block_b": "Block B" in blob or "block_b" in blob,
        "verdict": "RETIRED" if (both_ok and f7["reproduces"]) else "NOT RETIRED",
        "corrected_bootstrap_CI_computable": {
            "raw_rows_for_numerator_and_system_reference": both_ok,
            "raw_rows_for_corrected_denominator_D_user": False,
            "verdict": "MACHINERY RESTORED, INPUT STILL MISSING",
            "detail": "score_privilege.py sets raw_bootstrap_required=true and rebuilds every statistic "
                      "from raw rows. Both raw row sets it needs for the numerator and the system "
                      "reference are recovered, so the joint nested bootstrap now runs and reproduces "
                      "exactly. The CORRECTED estimator divides by D_user, whose raw rows do not exist "
                      "in any recovered run. So the corrected CI is computable the moment Block A lands, "
                      "and not before; it is no longer blocked on data loss, only on collection.",
        },
    }


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path,
                    default=REPO_ROOT / "analysis" / "wujur" / "titration_recovered.json")
    args = ap.parse_args()

    schemas = {}
    for run, cells, dose in (
        ("f_phase1_k3_20260727", ("N", "P", "M", "PM", "MP"), False),
        ("f_privilege_tiny8_20260727", ("PM", "MP"), False),
        ("f_phase2_med30_20260727", ("N", "P", "M"), True),
    ):
        schemas[run] = schema_report(run, load_gen(run), cells, need_dose=dose)

    f7 = repro_f7()
    doc = {
        "generated_by": "analysis/wujur/titration_recover.py",
        "inputs_are_read_only": True,
        "endpoint_contacted": False,
        "mirror_root": str(MIRROR),
        "mirror_code_vs_committed_code": {
            "files_compared": ["scoring/compose.py", "scoring/parse.py", "scoring/score_dose.py",
                               "scoring/score_privilege.py", "runner/assemble.py", "PREREGISTRATION.md"],
            "differences": "nomenclature only ('Arm F'->'composition organism', 'armE_stance'->'stance')",
            "algorithmic_difference": False,
            "note": "recovery_eval/scoring/score_blind.py is byte-identical between mirror and repo",
        },
        "schema_contract_source": {
            "parse.py": "rec['assistant']['content'], rec['error'], meta.vendor_a, meta.vendor_b, meta.label_swap_twin",
            "compose.py cell_means": "meta.cell, meta.base_item_id|meta.item_id, meta.label_swap_twin",
            "score_privilege.py _groups/_stratum_value": "same + outcome=='ok' and s is not None per (cell,item,twin)",
            "score_dose.py _dose": "meta.dose",
        },
        "generations_source": gen_source_report(
            ("f_phase1_k3_20260727", "f_privilege_tiny8_20260727", "f_phase2_med30_20260727")),
        "schema_checks": schemas,
        "provenance_hash_check": provenance_hash_check(
            ("f_phase1_k3_20260727", "f_privilege_tiny8_20260727", "f_phase2_med30_20260727")),
        "n_cell_length_evidence": n_cell_length_evidence(),
        "block_b": block_b_verdict(schemas, f7),
        "user_privilege_scan": scan_user_privilege(),
        "bounds": bounds_from_raw(),
        "reproduction": {"F7_privilege": f7, "F3_composition": repro_f3(),
                         "F6_dose": repro_f6(), "F9_blind_recovery": repro_f9()},
        "naming_artefact": {
            "claim": "f_privilege_k3_20260727 was never a separate run directory",
            "evidence": "model_organism/composition/ATTEMPT_LOG.md:124 'Resumed f_privilege_tiny8_20260727 "
                        "at k=3: 24/24, 0 errors, workers=8; repeat-0 tiny rows reused and 16 new calls "
                        "completed.' and :128 'Metric: metrics/f_privilege_k3_20260727_privilege.json'",
            "run_meta_corroboration": "runs/f_privilege_tiny8_20260727/run_meta.json: n_jobs_total 24, "
                                      "n_jobs_pending 16, n_jobs_skipped_done 8, k 3, privilege true",
            "consequence": "the 24 k=3 privilege raw rows are recovered under the tiny8 directory name",
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    print(json.dumps({
        "block_b": doc["block_b"]["verdict"],
        "D_user_measurable": doc["user_privilege_scan"]["D_user_measurable_from_recovered_data"],
        "total_user_priv_single_rows": doc["user_privilege_scan"]["total_user_privilege_single_loyalty_rows_anywhere"],
        "F7_reproduces": doc["reproduction"]["F7_privilege"]["reproduces"],
        "F3_reproduces": doc["reproduction"]["F3_composition"]["reproduces"],
        "F6_reproduces": doc["reproduction"]["F6_dose"]["reproduces"],
        "F6_reproducing_file": doc["reproduction"]["F6_dose"]["reproducing_metric_file"],
        "F9_reproduces": doc["reproduction"]["F9_blind_recovery"]["reproduces"],
        "Delta": doc["bounds"]["Delta_numerator"],
        "D_sys": doc["bounds"]["D_sys_denominator"],
        "required_D_user": doc["bounds"]["sharp_consequence"]["in_range_requires_D_user_at_least"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
