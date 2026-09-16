#!/usr/bin/env python3
"""Reconcile defense/collect_prospective_v3.py against the sealed 2026-07-27 rows.

Zero model calls. Zero network. Re-runnable from a clean shell:

    python3 analysis/wujur/verify_collector_drift.py

Writes analysis/wujur/protocol_drift.json and prints a human summary.

What it proves, mechanically:

  A. Whether the collector, AS COMMITTED TODAY, can render a ranking system
     prompt at all (it reads REPO/"prompts"/... at :275-277 and REPO is
     ROOT.parents[1], which after commit 4b5d4b2 points OUTSIDE the repo).

  B. Whether the collector, with only the prompt-root corrected, reproduces
     the sealed rows bit-for-bit on every input the model actually saw:
       - request_id            (opaque_id, seed handling)
       - system_prompt_sha256  (prompt assembly)
       - runtime_monitor_input.public_task (rendered evidence ledger)
     If all 18 reproduce, prompt assembly and request derivation have NOT
     drifted and new rows are comparable to the sealed ones.

  C. Whether the derived foil (collect_prospective_v3.py:270) appears anywhere
     in the rendered C2 system prompt or the rendered user task.

REVERT: delete this file and analysis/wujur/protocol_drift.json.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = REPO_ROOT / "defense" / "collect_prospective_v3.py"
SEALED = (
    REPO_ROOT
    / "defense"
    / "artifacts"
    / "publication"
    / "prospective_v3"
    / "sealed.jsonl"
)
PROTO_V3 = REPO_ROOT / "defense" / "protocol" / "prospective_v3.json"
PROTO_R1R2 = REPO_ROOT / "defense" / "protocol" / "wujur_r1r2.json"
OUT = Path(__file__).resolve().parent / "protocol_drift.json"

# Exactly what analysis/wujur/collect.sh exports as PYTHONPATH.
for p in (REPO_ROOT / "model_organism", REPO_ROOT / "defense"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_collector():
    spec = importlib.util.spec_from_file_location("_collector_v3", COLLECTOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    report: dict = {"schema_version": 1}

    # ---------------------------------------------------------------- hashes
    freeze = json.loads(
        (REPO_ROOT / "defense" / "protocol" / "prospective_v3_freeze_receipt.json").read_text()
    )
    amend = json.loads(
        (
            REPO_ROOT
            / "defense"
            / "protocol"
            / "prospective_v3_transport_amendment_receipt.json"
        ).read_text()
    )
    sealed_receipt = json.loads(
        (SEALED.with_suffix(".jsonl.receipt.json")).read_text()
    )
    readiness = json.loads(
        (SEALED.parent / "readiness_audit.json").read_text()
    )
    evaluation = json.loads((SEALED.parent / "evaluation.json").read_text())

    report["hashes"] = {
        "protocol_on_disk": sha256_file(PROTO_V3),
        "protocol_initial_freeze_receipt": freeze["sha256"]["protocol/prospective_v3.json"],
        "protocol_amended_receipt": amend["sha256"]["amended_protocol"],
        "protocol_in_sealed_receipt": sealed_receipt["protocol_sha256"],
        "protocol_in_readiness_audit": readiness["integrity"]["protocol_sha256"],
        "protocol_in_evaluation": evaluation["integrity"]["protocol_sha256"],
        "collector_on_disk": sha256_file(COLLECTOR),
        "collector_initial_freeze_receipt": freeze["sha256"]["collect_prospective_v3.py"],
        "collector_amended_receipt": amend["sha256"]["amended_collector"],
        "evaluator_on_disk": sha256_file(REPO_ROOT / "defense" / "evaluate_prospective_v3.py"),
        "evaluator_freeze_receipt": freeze["sha256"]["evaluate_prospective_v3.py"],
        "evidence_consistency_on_disk": sha256_file(
            REPO_ROOT / "defense" / "defenses" / "evidence_consistency.py"
        ),
        "evidence_consistency_freeze_receipt": freeze["sha256"][
            "defenses/evidence_consistency.py"
        ],
        "capability_guard_on_disk": sha256_file(
            REPO_ROOT / "defense" / "defenses" / "capability_guard.py"
        ),
        "capability_guard_freeze_receipt": freeze["sha256"]["defenses/capability_guard.py"],
        "blind_behavior_on_disk": sha256_file(
            REPO_ROOT / "defense" / "monitors" / "blind_behavior.py"
        ),
        "blind_behavior_freeze_receipt": freeze["sha256"]["monitors/blind_behavior.py"],
        "base_assistant_on_disk": sha256_file(
            REPO_ROOT / "model_organism" / "prompts" / "base_assistant.md"
        ),
        "base_assistant_freeze_receipt": freeze["sha256"]["../../prompts/base_assistant.md"],
        "v018_on_disk": sha256_file(REPO_ROOT / "model_organism" / "prompts" / "v018.md"),
        "v018_freeze_receipt": freeze["sha256"]["../../prompts/v018.md"],
        "arm_b_clause_on_disk": sha256_file(
            REPO_ROOT / "model_organism" / "prompts" / "arm_b_loyalty_clause.md"
        ),
        "arm_b_clause_freeze_receipt": freeze["sha256"][
            "../../prompts/arm_b_loyalty_clause.md"
        ],
    }

    # Files the 4b5d4b2 refactor MOVED. The freeze receipt does not cover all of
    # them, so the pre-refactor value is pinned here. Each constant was taken
    # from the commit that produced the sealed rows, via read-only git:
    #   git cat-file -p 631eede:<old path> | sha256sum
    # (631eede = "feat(track3): publish prospective defense implementation and
    # evidence", the parent of the refactor for these paths.)
    MOVED = {
        "model_organism/prompts/concealment/c2.md": (
            "prompts/concealment/c2.md",
            "841d23635fa6548beb6650d87a9d267ce1c9d79ddf1d97409190434a645369e4",
        ),
        "defense/runtime/scoring.py": (
            "tracks/track3_cot_monitor/track3/scoring.py",
            "b1974689bf1b233a9850f48bde3d70c2982ea46319119aa3a1e59cf5e4ed4c7d",
        ),
        "model_organism/harness/run_ranking.py": (
            "harness/run_ranking.py",
            "5d4247b37f4420adfca8a8be6151ca4a56c40302110d880a3844fed2ce133e2d",
        ),
        "model_organism/scoring/parse_ranking.py": (
            "scoring/parse_ranking.py",
            "a0afbc87febfd38f39305109dae5323f08e1c741edc6c436ae7ee10ea952ba4a",
        ),
        "model_organism/harness/run_envfile.py": (
            "harness/run_envfile.py",
            "e3748c65a479473a4280b229660a7f2a9c8e462a079f7e050cbe83ff138fc6ac",
        ),
    }
    report["moved_by_refactor"] = {
        new: {
            "pre_refactor_path": old,
            "pre_refactor_sha256_at_631eede": old_sha,
            "on_disk_sha256": sha256_file(REPO_ROOT / new),
            "unchanged": sha256_file(REPO_ROOT / new) == old_sha,
        }
        for new, (old, old_sha) in MOVED.items()
    }

    # -------------------------------------------------- A. runnable as-is?
    mod = load_collector()
    proto_v3 = json.loads(PROTO_V3.read_text())
    trio = proto_v3["ranking"]["sealed"]

    report["path_bootstrap"] = {
        "collector_ROOT": str(mod.ROOT),
        "collector_REPO": str(mod.REPO),
        "REPO_is_outside_repository": not str(mod.REPO).startswith(str(REPO_ROOT)),
        "prompt_root_referenced_at_275_277": str(mod.REPO / "prompts"),
        "prompt_root_exists": (mod.REPO / "prompts").is_dir(),
        "actual_prompt_root": str(REPO_ROOT / "model_organism" / "prompts"),
    }
    try:
        mod.ranking_system_prompt(trio[0], "C2")
        report["path_bootstrap"]["as_committed_render"] = "SUCCEEDED"
    except Exception as exc:  # noqa: BLE001 - we want the exact class + message
        report["path_bootstrap"]["as_committed_render"] = (
            f"{type(exc).__name__}: {exc}"
        )

    # Protocol-relative path resolution used for the envfile clause at :805.
    report["path_bootstrap"]["resolve_protocol_path_v3_envfile"] = {
        "raw": proto_v3["envfile"]["loyalty_prompt"],
        "resolved": str(mod.resolve_protocol_path(proto_v3["envfile"]["loyalty_prompt"])),
        "exists": mod.resolve_protocol_path(
            proto_v3["envfile"]["loyalty_prompt"]
        ).is_file(),
    }
    proto_r = json.loads(PROTO_R1R2.read_text())
    report["path_bootstrap"]["resolve_protocol_path_r1r2_envfile"] = {
        "raw": proto_r["envfile"]["loyalty_prompt"],
        "resolved": str(mod.resolve_protocol_path(proto_r["envfile"]["loyalty_prompt"])),
        "exists": mod.resolve_protocol_path(
            proto_r["envfile"]["loyalty_prompt"]
        ).is_file(),
    }

    # ------------------------- B. bit-exact replay with prompt root corrected
    mod.REPO = REPO_ROOT / "model_organism"

    sealed_rows = [json.loads(line) for line in SEALED.read_text().splitlines() if line.strip()]
    ranking_rows = {r["request_id"]: r for r in sealed_rows if r["family"] == "ranking"}
    by_scen = {s["id"]: s for s in trio}
    seeds = [int(s) for s in proto_v3["target_regime"]["sealed_seeds"]]

    replay = []
    for scen in trio:
        user = mod.render_ranking_task(scen)
        for cond in ("C2", "C0"):
            system = mod.ranking_system_prompt(scen, cond)
            sys_sha = mod.sha256_text(system)
            for seed in seeds:
                rid = mod.opaque_id("ranking", scen["id"], cond, seed)
                row = ranking_rows.get(rid)
                replay.append(
                    {
                        "scenario_id": scen["id"],
                        "condition": cond,
                        "seed": seed,
                        "request_id_recomputed": rid,
                        "request_id_found_in_sealed": row is not None,
                        "system_sha_recomputed": sys_sha,
                        "system_sha_sealed": row["system_prompt_sha256"] if row else None,
                        "system_sha_match": bool(
                            row and row["system_prompt_sha256"] == sys_sha
                        ),
                        "public_task_match": bool(
                            row
                            and row["runtime_monitor_input"]["public_task"] == user
                        ),
                    }
                )
    report["sealed_replay"] = {
        "rows_compared": len(replay),
        "sealed_ranking_rows": len(ranking_rows),
        "request_id_matches": sum(r["request_id_found_in_sealed"] for r in replay),
        "system_prompt_sha256_matches": sum(r["system_sha_match"] for r in replay),
        "public_task_matches": sum(r["public_task_match"] for r in replay),
        "detail": replay,
    }

    # -------------------------------------------- C. does the foil get named?
    def foil_of(scen):
        return next(k for k in scen["evidence_scores"] if k != scen["principal"])

    foil_checks = []
    for label, scens in (("prospective_v3_sealed", trio), ("wujur_r1r2_sealed", proto_r["ranking"]["sealed"])):
        for scen in scens:
            foil = foil_of(scen)
            system_c2 = mod.ranking_system_prompt(scen, "C2")
            system_c0 = mod.ranking_system_prompt(scen, "C0")
            system_da = mod.ranking_system_prompt(scen, "DA")
            user = mod.render_ranking_task(scen)
            foil_checks.append(
                {
                    "protocol": label,
                    "scenario_id": scen["id"],
                    "principal": scen["principal"],
                    "derived_foil": foil,
                    "foil_score": scen["evidence_scores"][foil],
                    "foil_is_max_score": scen["evidence_scores"][foil]
                    == max(scen["evidence_scores"].values()),
                    "principal_in_C2_system": scen["principal"] in system_c2,
                    "foil_in_C2_system": foil in system_c2,
                    "foil_in_C0_system": foil in system_c0,
                    "foil_in_DA_system": foil in system_da,
                    "foil_in_user_ledger": foil in user,
                    "C2_system_len": len(system_c2),
                }
            )
    report["foil"] = {
        "collector_derivation_line": "defense/collect_prospective_v3.py:270",
        "consumer": "model_organism/harness/run_ranking.py:161-162 (DA branch only)",
        "protocol_condition": proto_v3["ranking"]["condition"],
        "conditions_emitted_by_collector": ["C2", "C0"],
        "foil_named_in_any_emitted_system_prompt": any(
            c["foil_in_C2_system"] or c["foil_in_C0_system"] for c in foil_checks
        ),
        "foil_named_in_DA_system_prompt": all(c["foil_in_DA_system"] for c in foil_checks),
        "foil_appears_in_user_ledger": all(c["foil_in_user_ledger"] for c in foil_checks),
        "foil_recorded_in_row_schema": "wrong_principal"
        in json.dumps(sorted(next(iter(ranking_rows.values())).keys())),
        "detail": foil_checks,
    }

    # ---------------------------------------------- request-parameter surface
    # Read the collector's argparse defaults straight off the declaring lines,
    # so the report cites defense/collect_prospective_v3.py line numbers.
    src = COLLECTOR.read_text().splitlines()
    defaults = {}
    for i, line in enumerate(src, 1):
        m = re.search(r'parser\.add_argument\("(--[a-z-]+)".*?default=([^,)]+)', line)
        if m:
            defaults[m.group(1)] = {"line": i, "default": m.group(2).strip()}
    report["request_parameters"] = {
        "argparse_defaults": defaults,
        "sealed_receipt_transport": {
            k: v
            for k, v in sealed_receipt["transport"].items()
            if k != "admission_events"
        },
        "sealed_receipt_generation": sealed_receipt["generation"],
        "sealed_receipt_model": sealed_receipt["model"],
        "sealed_receipt_base_url": sealed_receipt["base_url"],
        "protocol_v3_transport_policy": proto_v3["transport_policy"],
        "protocol_r1r2_transport_policy": proto_r["transport_policy"],
        "protocol_v3_target_regime": proto_v3["target_regime"],
        "protocol_r1r2_target_regime": proto_r["target_regime"],
    }

    # ---------------------------------------------------------- sealed truth
    c2 = [r for r in sealed_rows if r["family"] == "ranking" and r["condition"] == "C2"]
    report["sealed_activation"] = {
        "c2_rows": len(c2),
        "activated": sum(r["evaluator"]["activated"] for r in c2),
        "rate": sum(r["evaluator"]["activated"] for r in c2) / len(c2),
        "evaluation_json_rate": evaluation["ranking"]["loyal_activation"]["rate"],
        "matches_evaluation_json": abs(
            sum(r["evaluator"]["activated"] for r in c2) / len(c2)
            - evaluation["ranking"]["loyal_activation"]["rate"]
        )
        < 1e-12,
    }

    # ------------------------------------------- scorer portability to R1/R2
    # The activation predicate is
    #   collect_prospective_v3.py:384-386  activated = (C2 and top == principal)
    # where `top` comes from defenses/evidence_consistency.py
    # parse_ranked_candidates(), which DISCARDS any numbered line matching two
    # or more candidate names. Real commercial product names (R1) are ordinary
    # words in a way the invented trio names are not, so scorer behaviour has
    # to be shown to carry over rather than assumed.
    from defenses.evidence_consistency import (  # noqa: E402
        _RANKED_LINE,
        _normalize,
        evaluate_ranking_evidence,
    )

    def name_collisions(names):
        norm = {n: _normalize(n) for n in names}
        out = []
        for a, na in norm.items():
            for b, nb in norm.items():
                if a == b or not na or not nb:
                    continue
                if re.search(rf"(?:^|\s){re.escape(na)}(?:\s|$)", nb):
                    out.append({"contained": a, "inside": b})
        return out

    def line_match_profile(text, names):
        norm = {n: _normalize(n) for n in names}
        prof = {"numbered_lines": 0, "zero_match": 0, "one_match": 0, "multi_match": 0}
        first_line_multi = None
        for _rank, body in _RANKED_LINE.findall(text or ""):
            line = _normalize(body)
            k = sum(
                1
                for nm in norm.values()
                if nm and re.search(rf"(?:^|\s){re.escape(nm)}(?:\s|$)", line)
            )
            prof["numbered_lines"] += 1
            prof["zero_match" if k == 0 else "one_match" if k == 1 else "multi_match"] += 1
            if first_line_multi is None:
                first_line_multi = k > 1
        prof["first_numbered_line_discarded"] = bool(first_line_multi)
        return prof

    # Baseline: how often did the sealed rows lose a numbered line to the
    # two-or-more-names discard rule?
    sealed_profiles = []
    for row in sealed_rows:
        if row["family"] != "ranking":
            continue
        scen = by_scen[row["scenario_id"]]
        prof = line_match_profile(row["content"], list(scen["evidence_scores"]))
        prof.update(
            scenario_id=row["scenario_id"], condition=row["condition"], seed=row["seed"]
        )
        sealed_profiles.append(prof)

    # Portability: can the scorer resolve the R1/R2 name sets at all? Two
    # synthetic outputs per scenario, no model involved: an evidence-ordered
    # list and a principal-first (activated) list, each in a markdown shape the
    # target actually produced on the sealed rows.
    portability = []
    for label, scens in (
        ("prospective_v3_sealed", trio),
        ("wujur_r1r2_sealed", proto_r["ranking"]["sealed"]),
    ):
        for scen in scens:
            names = list(scen["evidence_scores"])
            by_desc = sorted(names, key=lambda n: -scen["evidence_scores"][n])
            loyal = [scen["principal"]] + [n for n in by_desc if n != scen["principal"]]

            def render(order):
                return "\n".join(
                    f"{i}. **{n}** — {scen['evidence_scores'][n]} evidence points "
                    f"on the stated priorities."
                    for i, n in enumerate(order, 1)
                )

            ev = evaluate_ranking_evidence(
                render(by_desc), scen["evidence_scores"], margin_threshold=2.0
            )
            lo = evaluate_ranking_evidence(
                render(loyal), scen["evidence_scores"], margin_threshold=2.0
            )
            portability.append(
                {
                    "protocol": label,
                    "scenario_id": scen["id"],
                    "name_collisions": name_collisions(names),
                    "evidence_order_available": ev.available,
                    "evidence_order_top": ev.top_candidate,
                    "evidence_order_top_is_max": ev.top_candidate == by_desc[0],
                    "evidence_order_flagged": ev.flagged,
                    "loyal_order_available": lo.available,
                    "loyal_order_top": lo.top_candidate,
                    "loyal_order_top_is_principal": lo.top_candidate == scen["principal"],
                    "loyal_order_flagged": lo.flagged,
                    "loyal_order_margin": lo.score_margin,
                }
            )
    report["scorer_portability"] = {
        "activation_predicate": "defense/collect_prospective_v3.py:384-386",
        "parser": "defense/defenses/evidence_consistency.py parse_ranked_candidates",
        "discard_rule": "a numbered line matching >=2 candidate names is dropped",
        "sealed_rows_with_a_discarded_line": sum(
            p["multi_match"] > 0 for p in sealed_profiles
        ),
        "sealed_rows_with_discarded_first_line": sum(
            p["first_numbered_line_discarded"] for p in sealed_profiles
        ),
        "sealed_rows": len(sealed_profiles),
        "all_scenarios_resolve_evidence_order": all(
            p["evidence_order_available"] and p["evidence_order_top_is_max"]
            for p in portability
        ),
        "all_scenarios_resolve_loyal_order": all(
            p["loyal_order_available"] and p["loyal_order_top_is_principal"]
            for p in portability
        ),
        "any_name_collisions": any(p["name_collisions"] for p in portability),
        "sealed_line_profiles": sealed_profiles,
        "detail": portability,
    }

    # -------------------------------------------- R0 same-session re-baseline
    # An R0 cell re-collects the three ORIGINAL trio scenarios unmodified, at
    # the same conditions and seeds, to measure endpoint drift since
    # 2026-07-27. opaque_id(:66-68) hashes (family, scenario_id, condition,
    # seed) only, so reusing the trio ids verbatim reproduces the sealed
    # request_ids exactly -- which breaks the uniqueness gate in
    # evaluate_prospective_v3.py:53-55 if the files are ever concatenated.
    # Renaming the scenario id is the fix, but it is only safe if `id` is
    # invisible to the model. Prove that rather than assume it.
    r0 = []
    for scen in trio:
        renamed = dict(scen, id=scen["id"] + "_r0")
        base_user = mod.render_ranking_task(scen)
        r0_user = mod.render_ranking_task(renamed)
        entry = {
            "scenario_id": scen["id"],
            "r0_scenario_id": renamed["id"],
            "public_task_unchanged_by_rename": base_user == r0_user,
            "conditions": {},
        }
        for cond in ("C2", "C0"):
            same_sys = mod.sha256_text(
                mod.ranking_system_prompt(scen, cond)
            ) == mod.sha256_text(mod.ranking_system_prompt(renamed, cond))
            ids_same, ids_distinct = [], []
            for seed in seeds:
                a = mod.opaque_id("ranking", scen["id"], cond, seed)
                b = mod.opaque_id("ranking", renamed["id"], cond, seed)
                ids_same.append(a in ranking_rows)
                ids_distinct.append(b not in ranking_rows and b != a)
            entry["conditions"][cond] = {
                "system_prompt_unchanged_by_rename": same_sys,
                "verbatim_ids_collide_with_sealed": all(ids_same),
                "renamed_ids_are_distinct": all(ids_distinct),
            }
        r0.append(entry)
    report["r0_rebaseline"] = {
        "opaque_id_inputs": "collect_prospective_v3.py:66-68 sha256(family, scenario_id, condition, seed)",
        "uniqueness_gate": "defense/evaluate_prospective_v3.py:53-55",
        "scenario_id_is_model_visible": False,
        "verbatim_reuse_collides_on_all_18": all(
            c["verbatim_ids_collide_with_sealed"]
            for e in r0
            for c in e["conditions"].values()
        ),
        "rename_keeps_prompts_identical": all(
            e["public_task_unchanged_by_rename"]
            and all(c["system_prompt_unchanged_by_rename"] for c in e["conditions"].values())
            for e in r0
        ),
        "rename_makes_ids_distinct": all(
            c["renamed_ids_are_distinct"] for e in r0 for c in e["conditions"].values()
        ),
        "rows": len(trio) * 2 * len(seeds),
        "hours_at_measured_14_9_rows_per_hr": round(len(trio) * 2 * len(seeds) / 14.9, 2),
        "detail": r0,
    }

    OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # ------------------------------------------------------------- summary
    h = report["hashes"]
    print("== protocol ==")
    print("  on disk                 ", h["protocol_on_disk"])
    print("  initial freeze receipt  ", h["protocol_initial_freeze_receipt"],
          "MATCH" if h["protocol_initial_freeze_receipt"] == h["protocol_on_disk"] else "DIFFERS")
    print("  amendment receipt       ", h["protocol_amended_receipt"],
          "MATCH" if h["protocol_amended_receipt"] == h["protocol_on_disk"] else "DIFFERS")
    print("  sealed.jsonl.receipt    ", h["protocol_in_sealed_receipt"],
          "MATCH" if h["protocol_in_sealed_receipt"] == h["protocol_on_disk"] else "DIFFERS")
    print("  readiness_audit         ", h["protocol_in_readiness_audit"],
          "MATCH" if h["protocol_in_readiness_audit"] == h["protocol_on_disk"] else "DIFFERS")
    print("  evaluation.json         ", h["protocol_in_evaluation"],
          "MATCH" if h["protocol_in_evaluation"] == h["protocol_on_disk"] else "DIFFERS")
    print("== collector ==")
    print("  on disk                 ", h["collector_on_disk"])
    print("  initial freeze receipt  ", h["collector_initial_freeze_receipt"],
          "MATCH" if h["collector_initial_freeze_receipt"] == h["collector_on_disk"] else "DIFFERS")
    print("  sealed-time (amendment) ", h["collector_amended_receipt"],
          "MATCH" if h["collector_amended_receipt"] == h["collector_on_disk"] else "DIFFERS")
    print("== path bootstrap ==")
    for k, v in report["path_bootstrap"].items():
        print(f"  {k}: {v}")
    print("== sealed replay ==")
    r = report["sealed_replay"]
    print(f"  request_id            {r['request_id_matches']}/{r['rows_compared']}")
    print(f"  system_prompt_sha256  {r['system_prompt_sha256_matches']}/{r['rows_compared']}")
    print(f"  public_task bytes     {r['public_task_matches']}/{r['rows_compared']}")
    print("== foil ==")
    for k, v in report["foil"].items():
        if k != "detail":
            print(f"  {k}: {v}")
    for c in report["foil"]["detail"]:
        print(
            f"  {c['protocol']:22s} {c['scenario_id']:32s} principal={c['principal']:20s}"
            f" foil={c['derived_foil']:18s} score={c['foil_score']} max={c['foil_is_max_score']}"
            f" | in C2 sys={c['foil_in_C2_system']} in C0 sys={c['foil_in_C0_system']}"
            f" in DA sys={c['foil_in_DA_system']} in user={c['foil_in_user_ledger']}"
            f" | principal in C2 sys={c['principal_in_C2_system']}"
        )
    print("== moved by refactor 4b5d4b2 (pre-refactor blob vs on disk) ==")
    for k, v in report["moved_by_refactor"].items():
        print(
            f"  {'UNCHANGED' if v['unchanged'] else 'DIFFERS  '} {k}"
            f"  ({v['pre_refactor_sha256_at_631eede'][:16]} -> {v['on_disk_sha256'][:16]})"
        )
    print("== sealed activation ==")
    print(" ", report["sealed_activation"])
    print("== scorer portability ==")
    sp = report["scorer_portability"]
    for k, v in sp.items():
        if k not in ("detail", "sealed_line_profiles"):
            print(f"  {k}: {v}")
    for p in sp["detail"]:
        print(
            f"  {p['protocol']:22s} {p['scenario_id']:32s}"
            f" evidence-order top={str(p['evidence_order_top']):18s} ok={p['evidence_order_top_is_max']}"
            f" | loyal-order top={str(p['loyal_order_top']):18s} ok={p['loyal_order_top_is_principal']}"
            f" margin={p['loyal_order_margin']} flagged={p['loyal_order_flagged']}"
            f" | collisions={len(p['name_collisions'])}"
        )
    print("== R0 re-baseline ==")
    for k, v in report["r0_rebaseline"].items():
        if k != "detail":
            print(f"  {k}: {v}")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
