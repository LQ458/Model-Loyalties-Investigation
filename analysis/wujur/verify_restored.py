#!/usr/bin/env python3
"""Verify and import the datasets recovered from the Nextcloud mirror.

The pre-refactor layout under ``--source`` is a mirror that does not honour
``.gitignore``, so it retained run outputs that ``runs/`` ignore rules kept out
of the repository. This script proves each recovered artifact is the run behind
the committed metrics *before* importing it, then copies it to its post-refactor
location and writes ``analysis/wujur/restored_manifest.json``.

Design constraints:

* Deterministic. No wall-clock timestamps, no RNG, sorted iteration everywhere.
  Two consecutive runs produce byte-identical stdout and byte-identical manifest.
* Idempotent. Import reports the post-condition (destination matches source
  sha256), never the action taken, so re-running does not change the output.
* Self-contained. Every number printed is derived here from the files on disk
  using the repository's own scoring code, never copied from a prior analysis.

Usage::

    python3 analysis/wujur/verify_restored.py            # verify only
    python3 analysis/wujur/verify_restored.py --import   # verify, copy, manifest
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path("/home/barry/Nextcloud/vc_projects/Model-Loyalties-Investigation")

# Committed metrics file the headline confirm grid must reproduce.
V018_COMMITTED_METRICS = (
    REPO
    / "model_organism/logs/attempts/metrics"
    / "v018_confirm_c0c1c2da_cn_s3_judge_gpt56luna_medium.json"
)
COMPOSITION_METRICS_DIR = REPO / "model_organism/composition/metrics"
PROMPT_METADATA_DIR = REPO / "model_organism/prompts/metadata"

# Keys the runner injects into the metrics file after aggregate() returns.
# aggregate() never emits them, so they are expected absences on recompute.
RUNNER_INJECTED_KEYS = {
    ".concealment_evidence",
    ".heuristic",
    ".judged",
    ".n_activated",
    ".role_preflight",
    ".run_dir",
    ".smoke_only",
    ".transcripts",
}

# Composition runs to import: every recovered run whose raw rows back a
# committed metrics file, keyed run_id -> (source subdir, committed metric file).
COMPOSITION_RUNS: dict[str, tuple[str, str]] = {
    "f_phase1_k3_20260727": (
        "armF_composition/runs/f_phase1_k3_20260727",
        "f_phase1_k3_20260727_composition.json",
    ),
    "f_phase2_med30_20260727": (
        "armF_composition/runs/f_phase2_med30_20260727",
        # NOT f_phase2_med30_20260727_dose.json: that is the superseded 30-row
        # first-pass metric. The k=3 resume of this same directory (90 rows) is
        # what f_phase2_k3_20260727_dose.json was written from -- its own
        # $.run_id field says "f_phase2_med30_20260727".
        "f_phase2_k3_20260727_dose.json",
    ),
    "f_phase2_tiny9_live_20260727": (
        "armF_composition/runs/f_phase2_tiny9_live_20260727",
        "f_phase2_tiny9_live_20260727_dose.json",
    ),
    "f_privilege_tiny8_20260727": (
        "armF_composition/runs/f_privilege_tiny8_20260727",
        # NOT f_privilege_tiny8_20260727_privilege.json: that is the superseded
        # 8-row first-pass metric. run_meta.json here records k=3,
        # privilege=true, n_jobs_total=24, n_jobs_skipped_done=8 -- the tiny8
        # run resumed to full k=3. These 24 rows are the raw data behind
        # f_privilege_k3_20260727_privilege.json; see reconcile_run_ids().
        "f_privilege_k3_20260727_privilege.json",
    ),
    "f_small20_20260727": (
        "armF_composition/runs/f_small20_20260727",
        "f_small20_20260727_composition.json",
    ),
    "f_tiny10_20260727": (
        "armF_composition/runs/f_tiny10_20260727",
        "f_tiny10_20260727_composition.json",
    ),
    "f_tiny10_v18_20260727": (
        "armF_composition/runs/f_tiny10_v18_20260727",
        "f_tiny10_v18_20260727_composition.json",
    ),
    "f_tiny10_v18s_20260727": (
        "armF_composition/runs/f_tiny10_v18s_20260727",
        "f_tiny10_v18s_20260727_composition.json",
    ),
    "f_tiny10_v18s_twinfix_20260727": (
        "armF_composition/runs/f_tiny10_v18s_twinfix_20260727",
        "f_tiny10_v18s_twinfix_20260727_composition.json",
    ),
}
RECOVERY_EVAL_RUNS: dict[str, tuple[str, str]] = {
    "f9_live_20260727": (
        "armF_composition/recovery_eval/runs/f9_live_20260727",
        "f9_live_20260727_blind_recovery.json",
    ),
}

# Committed metric files that a later, larger pass over the SAME run directory
# superseded. Kept in-tree (frozen artifacts reference them) but they are not
# the numbers the recovered raw rows reproduce, and must not be cited as such.
SUPERSEDED_METRICS: dict[str, dict[str, str]] = {
    "f_privilege_tiny8_20260727_privilege.json": {
        "run_dir": "f_privilege_tiny8_20260727",
        "superseded_by": "f_privilege_k3_20260727_privilege.json",
        "reason": "first pass at k=1 (n_records=8); run resumed to k=3 (n_records=24)",
    },
    "f_phase2_med30_20260727_dose.json": {
        "run_dir": "f_phase2_med30_20260727",
        "superseded_by": "f_phase2_k3_20260727_dose.json",
        "reason": "first pass at k=1 (n_records=30); run resumed to k=3 (n_records=90)",
    },
}

# Full-pipeline reproductions that settle which run directory a "_k3_" metric
# filename actually refers to. Both scorers are deterministic at a fixed seed.
# `.reference_run` is a path string echoed from the CLI argument, not data, so
# it is the one leaf allowed to differ.
RECONCILIATIONS: tuple[dict[str, Any], ...] = (
    {
        "metric": "f_privilege_k3_20260727_privilege.json",
        "scorer": "score_privilege",
        "run_dir": "armF_composition/runs/f_privilege_tiny8_20260727",
        "ref_run_dir": "armF_composition/runs/f_phase1_k3_20260727",
        "ref_composition": "f_phase1_k3_20260727_composition.json",
        "allowed_diff_paths": [".reference_run"],
    },
    {
        "metric": "f_phase2_k3_20260727_dose.json",
        "scorer": "score_dose",
        "run_dir": "armF_composition/runs/f_phase2_med30_20260727",
        "allowed_diff_paths": [],
    },
)

# Recovered run dirs deliberately NOT imported, with the reason.
EXCLUDED_RUNS: dict[str, str] = {
    "armF_composition/runs/f_phase1_k3_dry": "dry_run: run_meta.dry_run=true, no committed metrics",
    "armF_composition/runs/f_phase2_tiny9_20260727": "dry_run: run_meta.dry_run=true, no committed metrics",
    "armF_composition/runs/f_tiny10_dry": "dry_run: run_meta.dry_run=true, no committed metrics",
    "armF_composition/recovery_eval/runs/f9_dry_20260727": "dry_run: no committed metrics",
}

# Superseded intermediates inside the v018 run dir. Hashed and recorded so the
# exclusion is auditable, but not imported: each is a strict predecessor of the
# final transcripts.jsonl written by the same runner invocation.
V018_EXCLUDED_FILES = (
    "transcripts.jsonl.bak_before_dedupe",
    "transcripts.jsonl.bak_before_retry_errors",
    "transcripts.jsonl.bak_before_resume_workers7",
)

V018_IMPORT_FILES = (
    "transcripts.jsonl",
    "meta.json",
    "prompt_used.md",
    "judge_gpt56luna/judged.jsonl",
    "judge_gpt56luna/metrics.json",
    "judge_gpt56luna/report_snippet.md",
)

# Further recovered ranking runs whose raw rows back a committed metrics file
# that is already in-tree. run_id -> (mirror subdir, committed metrics path
# relative to the repo, expected split).
RANKING_RUNS: dict[str, tuple[str, str, str]] = {
    "v018_test_c0c1c2da_s3": (
        "runs/v018_test_c0c1c2da_s3",
        "model_organism/runs/v018_test_c0c1c2da_s3/judge_gpt56luna/score_gate_v2/metrics.json",
        "test",
    ),
    "v018_c1c2da_s3": (
        "runs/v018_c1c2da_s3",
        "model_organism/runs/v018_c1c2da_s3/judge_gpt56luna/score_gate_v2/metrics.json",
        "train",
    ),
}

RANKING_RUN_IMPORT_FILES = (
    "transcripts.jsonl",
    "meta.json",
    "prompt_used.md",
    "judge_gpt56luna/judged.jsonl",
    "judge_gpt56luna/metrics.json",
    "judge_gpt56luna/report_snippet.md",
    "score_det/metrics.json",
    "score_det/report_snippet.md",
)

# score_det/judged.jsonl is a byte-identical copy of transcripts.jsonl in both
# runs, verified by sha256, so importing it would duplicate 3.7 MB for nothing.
RANKING_RUN_EXCLUDED_FILES = ("score_det/judged.jsonl",)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(path: Path) -> int:
    """JSONL row count: non-blank lines that parse as JSON."""
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                json.loads(line)
                n += 1
    return n


def deep_diff(a: Any, b: Any, path: str = "") -> list[tuple[str, Any, Any]]:
    out: list[tuple[str, Any, Any]] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += deep_diff(a.get(k, "<absent>"), b.get(k, "<absent>"), f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, f"<list len {len(a)}>", f"<list len {len(b)}>"))
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                out += deep_diff(x, y, f"{path}[{i}]")
    elif a != b:
        out.append((path, a, b))
    return out


CHECKS: list[dict[str, Any]] = []


def check(name: str, computed: Any, stored: Any, *, note: str = "") -> bool:
    ok = computed == stored
    CHECKS.append(
        {"check": name, "computed": computed, "stored": stored, "pass": ok, "note": note}
    )
    flag = "PASS" if ok else "FAIL"
    tail = f"   [{note}]" if note else ""
    print(f"  {flag}  {name:<52} computed={computed!r}  stored={stored!r}{tail}")
    return ok


def section(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# --------------------------------------------------------------------------- #
# v018 confirm grid
# --------------------------------------------------------------------------- #
def verify_v018(src_run: Path) -> dict[str, Any]:
    agg = load_module("wujur_aggregate", REPO / "model_organism/scoring/aggregate.py")
    stored = json.loads(V018_COMMITTED_METRICS.read_text(encoding="utf-8"))

    transcripts = src_run / "transcripts.jsonl"
    judged = src_run / "judge_gpt56luna/judged.jsonl"
    run_metrics = src_run / "judge_gpt56luna/metrics.json"

    t_rows = agg.load_transcripts(transcripts)
    j_rows = agg.load_transcripts(judged)

    section("V018 CONFIRM GRID -- is the recovered copy the run behind the paper?")
    print(f"source: {transcripts}")
    print(f"stored: {V018_COMMITTED_METRICS.relative_to(REPO)}")
    print()

    print("[1] run-dir metrics.json vs committed metrics file")
    h_run, h_committed = sha256_file(run_metrics), sha256_file(V018_COMMITTED_METRICS)
    check("judge_gpt56luna/metrics.json sha256 == committed", h_run, h_committed)
    check(
        "judge_gpt56luna/metrics.json bytes == committed",
        run_metrics.stat().st_size,
        V018_COMMITTED_METRICS.stat().st_size,
    )

    print()
    print("[2] row counts")
    check("transcripts.jsonl rows", len(t_rows), 210)
    check("judged.jsonl rows", len(j_rows), 210)
    n_by_cond = {c: 0 for c in ("C0", "C1", "C2", "CN", "DA")}
    for r in t_rows:
        c = str(r.get("condition") or "")
        if c in n_by_cond:
            n_by_cond[c] += 1
    for c in sorted(n_by_cond):
        check(f"n_by_condition.{c}", n_by_cond[c], stored["n_by_condition"][c])

    print()
    print("[3] aggregate rates recomputed from raw transcripts.jsonl rows")
    computed = agg.aggregate(t_rows, split="train")
    raw_counts: dict[str, dict[str, Any]] = {}
    for c in sorted(n_by_cond):
        xs = [r for r in t_rows if r.get("condition") == c]
        npf = sum(1 for r in xs if agg.is_activated(r.get("score") or {}, "principal_first"))
        npr = sum(1 for r in xs if agg.is_activated(r.get("score") or {}, "promoted"))
        raw_counts[c] = {
            "n": len(xs),
            "principal_first_count": npf,
            "promoted_count": npr,
            "principal_first_rate": npf / len(xs),
            "promoted_rate": npr / len(xs),
        }
        print(
            f"       raw {c}: principal_first {npf:>3}/{len(xs)} = {npf / len(xs):.6f}"
            f"   promoted {npr:>3}/{len(xs)} = {npr / len(xs):.6f}"
        )
    for c in sorted(n_by_cond):
        check(
            f"activation_rate.principal_first.{c}",
            computed["activation_rate"]["principal_first"][c],
            stored["activation_rate"]["principal_first"][c],
            note=f"{raw_counts[c]['principal_first_count']}/{raw_counts[c]['n']}",
        )
    for c in sorted(n_by_cond):
        check(
            f"activation_rate.promoted.{c}",
            computed["activation_rate"]["promoted"][c],
            stored["activation_rate"]["promoted"][c],
            note=f"{raw_counts[c]['promoted_count']}/{raw_counts[c]['n']}",
        )

    print()
    print("[4] paired sign tests vs C0 recomputed from raw rows")
    sign_keys = ("n_paired_scenarios", "n_pos", "n_neg", "n_tie", "mean_delta", "p_value")
    for cond in sorted(stored["paired_sign_tests_vs_c0"]):
        for metric in ("principal_first", "promoted"):
            g = computed["paired_sign_tests_vs_c0"][cond][metric]
            s = stored["paired_sign_tests_vs_c0"][cond][metric]
            for k in sign_keys:
                check(f"sign_test.{cond}.{metric}.{k}", g[k], s[k])

    print()
    print("[5] derived scalars")
    for k in (
        "activation_c0",
        "cn_principal_first",
        "da_cross_principal_portability",
        "da_named_entity_first",
        "principal_selectivity",
        "split",
        "true_principal_first_under_da",
    ):
        check(f"{k}", computed.get(k), stored.get(k))
    n_act = sum(raw_counts[c]["principal_first_count"] for c in sorted(raw_counts))
    check("n_activated (sum of principal_first counts)", n_act, stored["n_activated"])

    print()
    print("[6] full recompute from judged.jsonl vs committed metrics (all keys)")
    j_computed = agg.aggregate(j_rows, split="train")
    diffs = deep_diff(j_computed, stored)
    diff_paths = sorted(p for p, _, _ in diffs)
    unexpected = [p for p in diff_paths if p not in RUNNER_INJECTED_KEYS]
    for p, g, s in diffs:
        tag = "expected-injected" if p in RUNNER_INJECTED_KEYS else "UNEXPECTED"
        val = "<omitted: large>" if p == ".role_preflight" else f"computed={g!r} stored={s!r}"
        print(f"       {tag:<18} {p}  {val}")
    check("judged recompute: unexpected differing leaves", unexpected, [])
    check("judged recompute: total differing leaves", len(diffs), len(RUNNER_INJECTED_KEYS))

    print()
    print("[7] transcripts.jsonl vs judged.jsonl alignment")
    def _keyseq(rs: list[dict[str, Any]]) -> str:
        blob = json.dumps(
            [[r.get("scenario_id"), r.get("condition"), r.get("sample")] for r in rs],
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    check(
        "sha256 of (scenario_id, condition, sample) sequence matches",
        _keyseq(t_rows),
        _keyseq(j_rows),
    )
    same_score = sum(1 for a, b in zip(t_rows, j_rows) if a.get("score") == b.get("score"))
    check("rows with identical score object", same_score, 210)
    same_content = sum(1 for a, b in zip(t_rows, j_rows) if a.get("content") == b.get("content"))
    check("rows with identical content", same_content, 210)
    same_reason = sum(1 for a, b in zip(t_rows, j_rows) if a.get("reasoning") == b.get("reasoning"))
    check("rows with identical reasoning", same_reason, 210)

    print()
    print("[8] disclosure labelling structure (audit hypothesis: labels exist only")
    print("    on activated rows, so empty cells are structural, not sloppy)")
    label_rows: dict[str, dict[str, int]] = {}
    for c in sorted(n_by_cond):
        xs = [r for r in j_rows if r.get("condition") == c]
        labelled = sum(1 for r in xs if agg.get_disclosure(r) is not None)
        act = sum(1 for r in xs if agg.is_activated(r.get("score") or {}, "principal_first"))
        lab_act = sum(
            1
            for r in xs
            if agg.is_activated(r.get("score") or {}, "principal_first")
            and agg.get_disclosure(r) is not None
        )
        lab_inact = labelled - lab_act
        label_rows[c] = {
            "n": len(xs),
            "activated": act,
            "disclosure_labelled": labelled,
            "labelled_and_activated": lab_act,
            "labelled_but_not_activated": lab_inact,
        }
        print(
            f"       {c}: n={len(xs):>3}  activated={act:>3}  disclosure_labelled={labelled:>3}"
            f"  labelled&activated={lab_act:>3}  labelled&NOT-activated={lab_inact:>3}"
        )
    check(
        "disclosure labels present iff row activated (all conditions)",
        {c: label_rows[c]["disclosure_labelled"] for c in sorted(label_rows)},
        {c: label_rows[c]["activated"] for c in sorted(label_rows)},
    )
    for c in ("C0", "CN"):
        blk = stored["disclosure_rate"][c]
        check(
            f"stored disclosure_rate.{c}.n_labelled == activated count",
            blk["n_labelled"],
            label_rows[c]["activated"],
        )

    print()
    print("[9] prompt / system hash cross-check against prompts/metadata/")
    meta_records = {
        p.name: json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(PROMPT_METADATA_DIR.glob("*.json"))
    }
    check("prompts/metadata record count", len(meta_records), 38)
    has_prompt = sorted(k for k, v in meta_records.items() if "prompt_sha256" in v)
    has_system = sorted(k for k, v in meta_records.items() if "system_sha256" in v)
    check("metadata records carrying prompt_sha256", len(has_prompt), len(meta_records))
    check("metadata records carrying system_sha256", has_system, [])
    prompt_versions = sorted({str(r.get("prompt_version")) for r in t_rows})
    check("distinct prompt_version across rows", prompt_versions, ["v018"])
    row_prompt_hashes = sorted({str(r.get("prompt_sha256")) for r in t_rows})
    check("distinct prompt_sha256 across 210 rows", len(row_prompt_hashes), 1)
    meta_v018 = meta_records["v018.json"]["prompt_sha256"]
    check("row prompt_sha256 == metadata v018.json prompt_sha256", row_prompt_hashes[0], meta_v018)
    prompt_file = REPO / "model_organism" / meta_records["v018.json"]["prompt_path"]
    check(
        "metadata v018.json prompt_sha256 == sha256(prompts/v018.md)",
        sha256_file(prompt_file),
        meta_v018,
    )
    n_sys = len({str(r.get("system_sha256")) for r in t_rows})
    sys_by_cond = {
        c: len({str(r.get("system_sha256")) for r in t_rows if r.get("condition") == c})
        for c in sorted(n_by_cond)
    }
    print(f"       distinct system_sha256 across 210 rows: {n_sys}")
    print(f"       distinct system_sha256 per condition:   {json.dumps(sys_by_cond, sort_keys=True)}")
    print("       NOTE: system_sha256 is sha256 of the *assembled* system prompt")
    print("             (run_ranking.py:590 sha256_text(system), assembled per scenario),")
    print("             so prompts/metadata/ has no corresponding record to check it")
    print("             against. Cross-check performed: prompt_sha256 only.")
    check("rows missing prompt_sha256", sum(1 for r in t_rows if not r.get("prompt_sha256")), 0)
    check("rows missing system_sha256", sum(1 for r in t_rows if not r.get("system_sha256")), 0)
    check("C0 shares one assembled system prompt", sys_by_cond["C0"], 1)
    check(
        "installed conditions carry one system prompt per scenario",
        [sys_by_cond[c] for c in ("C1", "C2", "CN", "DA")],
        [14, 14, 14, 14],
    )

    return {
        "raw_counts": raw_counts,
        "label_structure": label_rows,
        "n_activated": n_act,
        "distinct_system_sha256": n_sys,
        "system_sha256_by_condition": sys_by_cond,
        "prompt_sha256": row_prompt_hashes[0],
        "headline_sign_test_c2_vs_c0_principal_first": {
            k: computed["paired_sign_tests_vs_c0"]["C2"]["principal_first"][k] for k in sign_keys
        },
        "judged_recompute_unexpected_diffs": unexpected,
    }

def verify_ranking_runs(source: Path) -> dict[str, Any]:
    """Verify the two further ranking runs against their committed metrics.

    Each has only a derived `judge_gpt56luna/score_gate_v2/metrics.json` in the
    repo; the raw rows behind it were ignored away. Same test as the confirm
    grid: re-run the repository's aggregator over the recovered judged rows and
    require the committed file back.
    """
    agg = load_module("wujur_aggregate3", REPO / "model_organism/scoring/aggregate.py")
    section("FURTHER RANKING RUNS -- raw rows for already-committed metrics")
    out: dict[str, Any] = {}
    for run_id in sorted(RANKING_RUNS):
        subdir, metric_rel, split = RANKING_RUNS[run_id]
        d = source / subdir
        rows = agg.load_transcripts(d / "transcripts.jsonl")
        stored = json.loads((REPO / metric_rel).read_text(encoding="utf-8"))
        by_cond = Counter(str(r.get("condition")) for r in rows)
        scenarios = sorted({str(r.get("scenario_id")) for r in rows})
        samples = sorted({r.get("sample") for r in rows})
        splits = sorted({str(r.get("split")) for r in rows})
        print(f"  -- {run_id}  ({metric_rel})")
        print(f"       rows={len(rows)} splits={splits} conditions={dict(sorted(by_cond.items()))}")
        print(f"       scenarios={len(scenarios)} samples={samples}")
        for s in scenarios:
            print(f"         {s}")
        check(f"{run_id}: single split", splits, [split])
        check(f"{run_id}: rows == scenarios x conditions x samples",
              len(rows), len(scenarios) * len(by_cond) * len(samples))
        check(f"{run_id}: rows carrying an error field",
              sum(1 for r in rows if r.get("error")), 0)
        check(f"{run_id}: n_by_condition matches committed metrics",
              dict(sorted(by_cond.items())),
              {k: v for k, v in sorted(stored["n_by_condition"].items()) if v})
        check(f"{run_id}: distinct prompt_sha256 across rows",
              sorted({str(r.get("prompt_sha256")) for r in rows}),
              ["1a12fab81c9116360b8da6228eb4697889837ddfbb43c6f0799a499c2fc69762"])
        judged = agg.load_transcripts(d / "judge_gpt56luna/judged.jsonl")
        computed = agg.aggregate(judged, split=split)
        diffs = deep_diff(computed, stored)
        unexpected = sorted(p for p, _, _ in diffs if p not in RUNNER_INJECTED_KEYS)
        for p, g, s in diffs:
            tag = "expected-injected" if p in RUNNER_INJECTED_KEYS else "UNEXPECTED"
            print(f"       {tag:<18} {p}")
        check(f"{run_id}: unexpected diffs recomputing committed metrics", unexpected, [])
        for rel in RANKING_RUN_EXCLUDED_FILES:
            p = d / rel
            if p.is_file():
                check(f"{run_id}: {rel} is a byte copy of transcripts.jsonl",
                      sha256_file(p), sha256_file(d / "transcripts.jsonl"))
        out[run_id] = {
            "rows": len(rows),
            "split": split,
            "n_by_condition": dict(sorted(by_cond.items())),
            "scenarios": scenarios,
            "samples": samples,
            "committed_metrics": metric_rel,
            "unexpected_diffs": unexpected,
        }
    return out


# --------------------------------------------------------------------------- #
# composition
# --------------------------------------------------------------------------- #
def verify_composition(source: Path) -> dict[str, Any]:
    scoring_dir = REPO / "model_organism/composition/scoring"
    if str(scoring_dir) not in sys.path:
        sys.path.insert(0, str(scoring_dir))
    compose = load_module("wujur_compose", scoring_dir / "compose.py")
    score_dose = load_module("wujur_score_dose", scoring_dir / "score_dose.py")
    parse = load_module("wujur_parse", scoring_dir / "parse.py")

    section("COMPOSITION -- Phase-1 reference (the D_sys denominator, load-bearing)")
    p1 = source / COMPOSITION_RUNS["f_phase1_k3_20260727"][0] / "generations.jsonl"
    priv = json.loads(
        (COMPOSITION_METRICS_DIR / "f_privilege_k3_20260727_privilege.json").read_text(
            encoding="utf-8"
        )
    )
    print(f"source: {p1}")
    print("stored: model_organism/composition/metrics/f_privilege_k3_20260727_privilege.json")
    print()
    recs = compose.load_jsonl(p1)
    check("f_phase1_k3 rows", len(recs), priv["n_reference_records"])
    parsed = parse.iter_parsed(recs)
    cm = compose.cell_means(parsed)
    for cell, jkey in (("P", "ref_P"), ("M", "ref_M"), ("N", "ref_N")):
        check(
            f"cell mean {cell} == $.kappa_beta.{jkey}",
            repr(cm["s_by_cell"][cell]),
            repr(priv["kappa_beta"][jkey]),
        )
    denom = cm["s_by_cell"]["P"] - cm["s_by_cell"]["M"]
    check(
        "P - M == $.kappa_beta.denom_ref_P_minus_M",
        repr(denom),
        repr(priv["kappa_beta"]["denom_ref_P_minus_M"]),
    )
    ref_diffs = deep_diff(cm, priv["reference_summary"])
    check("full reference_summary differing leaves", len(ref_diffs), 0)
    for p, g, s in ref_diffs:
        print(f"       DIFF {p}: computed={g!r} stored={s!r}")

    section("COMPOSITION -- integrity of every other imported run")
    print("  Stored $.summary blocks predate the addition of `twin_sample_counts`")
    print("  to cell_means(), so comparison is restricted to the keys the stored")
    print("  block actually carries; keys only the recompute emits are listed as")
    print("  schema additions, not as mismatches.")
    run_facts: dict[str, Any] = {}
    all_runs = {**COMPOSITION_RUNS, **RECOVERY_EVAL_RUNS}
    for run_id in sorted(all_runs):
        subdir, metric_name = all_runs[run_id]
        gen = source / subdir / "generations.jsonl"
        metric = json.loads((COMPOSITION_METRICS_DIR / metric_name).read_text(encoding="utf-8"))
        n = count_rows(gen)
        facts: dict[str, Any] = {"rows": n, "authoritative_metric_file": metric_name}
        print(f"  -- {run_id}  (authoritative metric: {metric_name})")
        if "n_records" in metric:
            check(f"{run_id}: rows == {metric_name} $.n_records", n, metric["n_records"])
        elif "n_target_rows" in metric:
            check(f"{run_id}: rows == {metric_name} $.n_target_rows", n, metric["n_target_rows"])
        parsed_r = parse.iter_parsed(compose.load_jsonl(gen))
        stored_summary = metric.get("summary")
        if isinstance(stored_summary, dict) and "s_by_cell" in stored_summary:
            cm_r = compose.cell_means(parsed_r)
            shared = {k: v for k, v in cm_r.items() if k in stored_summary}
            added = sorted(set(cm_r) - set(stored_summary))
            d = deep_diff(shared, stored_summary)
            check(f"{run_id}: cell_means == $.summary on shared keys (diffs)", len(d), 0)
            for p, g, s in d:
                print(f"       DIFF {p}: computed={g!r} stored={s!r}")
            if added:
                print(f"       schema additions absent from stored $.summary: {added}")
            facts["s_by_cell"] = cm_r["s_by_cell"]
            facts["summary_schema_additions"] = added
        if "curves_s_by_cell_dose" in metric:
            values = score_dose._cell_dose_item_values(parsed_r)
            curves = {c: score_dose._curve(values, c) for c in sorted(metric["curves_s_by_cell_dose"])}
            d = deep_diff(curves, metric["curves_s_by_cell_dose"])
            check(f"{run_id}: dose curves == $.curves_s_by_cell_dose (diffs)", len(d), 0)
            for p, g, s in d:
                print(f"       DIFF {p}: computed={g!r} stored={s!r}")
            facts["curves_s_by_cell_dose"] = curves
        run_facts[run_id] = facts
    return {"phase1_s_by_cell": cm["s_by_cell"], "runs": run_facts}


def reconcile_run_ids(source: Path) -> dict[str, Any]:
    """Settle which recovered run directory each "_k3_" metric was written from.

    A metric filename is not evidence of a run directory: score_privilege.py:200
    and score_dose.py:250 both accept an explicit --out. The only sound test is
    to re-run the scorer on candidate raw rows and see whether every number,
    including the seeded bootstrap, comes back identical.
    """
    scoring_dir = REPO / "model_organism/composition/scoring"
    if str(scoring_dir) not in sys.path:
        sys.path.insert(0, str(scoring_dir))
    score_privilege = load_module("wujur_score_privilege", scoring_dir / "score_privilege.py")
    score_dose = load_module("wujur_score_dose2", scoring_dir / "score_dose.py")

    section('RUN-ID RECONCILIATION -- which raw rows back each "_k3_" metric?')
    out: dict[str, Any] = {}
    for spec in RECONCILIATIONS:
        metric_name = str(spec["metric"])
        run_dir = source / str(spec["run_dir"])
        stored = json.loads((COMPOSITION_METRICS_DIR / metric_name).read_text(encoding="utf-8"))
        print(f"  {metric_name}")
        print(f"    candidate raw rows: {run_dir}/generations.jsonl")
        if spec["scorer"] == "score_privilege":
            got = score_privilege.score_privilege(
                run_dir / "generations.jsonl",
                ref_run_dir=source / str(spec["ref_run_dir"]),
                ref_composition=COMPOSITION_METRICS_DIR / str(spec["ref_composition"]),
                n_resamples=2000,
                seed=20260727,
            )
        else:
            got = score_dose.score_dose(run_dir / "generations.jsonl", n_resamples=2000, seed=20260727)
        diffs = deep_diff(got, stored)
        allowed = set(spec["allowed_diff_paths"])
        unexpected = sorted(p for p, _, _ in diffs if p not in allowed)
        for p, g, s in diffs:
            tag = "allowed(cli-path)" if p in allowed else "UNEXPECTED"
            print(f"    {tag:<18} {p}: computed={g!r} stored={s!r}")
        check(f"{metric_name}: unexpected diffs vs recompute from {run_dir.name}", unexpected, [])
        out[metric_name] = {
            "raw_rows": str(run_dir / "generations.jsonl"),
            "run_dir_name": run_dir.name,
            "scorer": spec["scorer"],
            "n_resamples": 2000,
            "seed": 20260727,
            "diff_paths": sorted(p for p, _, _ in diffs),
            "unexpected_diff_paths": unexpected,
            "reproduces": not unexpected,
        }
        if "kappa_beta" in got:
            out[metric_name]["kappa_beta"] = got["kappa_beta"]
    print()
    print("  superseded metric files (same run dir, earlier smaller pass):")
    for name in sorted(SUPERSEDED_METRICS):
        info = SUPERSEDED_METRICS[name]
        body = json.loads((COMPOSITION_METRICS_DIR / name).read_text(encoding="utf-8"))
        print(
            f"    {name}  n_records={body.get('n_records')}  run_dir={info['run_dir']}"
            f"  -> superseded by {info['superseded_by']}  [{info['reason']}]"
        )
        out.setdefault("superseded", {})[name] = {**info, "n_records": body.get("n_records")}
    return out

def verify_prompt_rederivation(source: Path) -> dict[str, Any]:
    """Rebuild each composition row's prompts from the committed templates.

    This is a provenance check on the restored rows, not a scoring check. A
    mismatch means the row was generated by code or templates that differ from
    what is committed today, which a later reader could easily mistake for a
    corrupted restore. Reported precisely so nobody has to guess.
    """
    croot = REPO / "model_organism/composition"
    asm = load_module("wujur_assemble", croot / "runner/assemble.py")
    section("PROMPT RE-DERIVATION -- do restored rows rebuild from committed prompts?")
    out: dict[str, Any] = {}
    for run_id in sorted(COMPOSITION_RUNS):
        gen = source / COMPOSITION_RUNS[run_id][0] / "generations.jsonl"
        rows = [json.loads(l) for l in gen.read_text(encoding="utf-8").splitlines() if l.strip()]
        ok_sys = ok_usr = n = 0
        sys_mismatch_by_cell: Counter = Counter()
        recorded_by_cell: dict[str, set[str]] = {}
        rebuilt_by_cell: dict[str, set[str]] = {}
        for r in rows:
            m = r.get("meta") or {}
            stim = croot / "stimuli" / f"{m.get('item_id')}.json"
            if not stim.is_file():
                continue
            n += 1
            built = asm.assemble_cell(
                cell=m["cell"],
                item=json.loads(stim.read_text(encoding="utf-8")),
                privilege=bool(m.get("privilege")),
            )["meta"]
            cell = str(m["cell"])
            recorded_by_cell.setdefault(cell, set()).add(str(m.get("system_sha256")))
            rebuilt_by_cell.setdefault(cell, set()).add(str(built["system_sha256"]))
            if built["system_sha256"] == m.get("system_sha256"):
                ok_sys += 1
            else:
                sys_mismatch_by_cell[cell] += 1
            ok_usr += built["user_sha256"] == m.get("user_sha256")
        print(f"  -- {run_id}: {n} rows resolvable to a stimulus")
        print(f"       system_sha256 {ok_sys}/{n}   user_sha256 {ok_usr}/{n}")
        if sys_mismatch_by_cell:
            print(f"       system mismatches by cell: {dict(sorted(sys_mismatch_by_cell.items()))}")
            for cell in sorted(sys_mismatch_by_cell):
                print(f"         cell {cell}: recorded {sorted(recorded_by_cell[cell])}")
                print(f"         cell {cell}: rebuilt  {sorted(rebuilt_by_cell[cell])}")
        check(f"{run_id}: user_sha256 rebuilds for every row", ok_usr, n)
        out[run_id] = {
            "rows_checked": n,
            "system_sha256_rebuilt": ok_sys,
            "user_sha256_rebuilt": ok_usr,
            "system_mismatches_by_cell": dict(sorted(sys_mismatch_by_cell.items())),
            "recorded_system_sha256_by_cell": {k: sorted(v) for k, v in sorted(recorded_by_cell.items())},
            "rebuilt_system_sha256_by_cell": {k: sorted(v) for k, v in sorted(rebuilt_by_cell.items())},
        }
    # The one known mismatch, characterised rather than hand-waved.
    p1 = out.get("f_phase1_k3_20260727", {})
    check(
        "f_phase1_k3: system prompt mismatches are confined to the N cell",
        sorted(p1.get("system_mismatches_by_cell", {})),
        ["N"],
    )
    check(
        "f_phase1_k3: recorded N system prompt is item-independent (one hash)",
        len(p1.get("recorded_system_sha256_by_cell", {}).get("N", [])),
        1,
    )
    check(
        "f_phase1_k3: today's N system prompt is item-dependent (two hashes)",
        len(p1.get("rebuilt_system_sha256_by_cell", {}).get("N", [])),
        2,
    )
    for other in ("f_privilege_tiny8_20260727", "f_phase2_med30_20260727"):
        check(
            f"{other}: every system prompt rebuilds exactly",
            out[other]["system_sha256_rebuilt"],
            out[other]["rows_checked"],
        )

    # Does simply removing today's length-match pad reproduce the recorded N
    # prompt? It does not, so the pad is not a sufficient explanation.
    prompts = croot / "prompts"
    neutral = (prompts / "system_neutral.md").read_text(encoding="utf-8").strip()
    unpadded = hashlib.sha256((neutral + "\n").encode("utf-8")).hexdigest()
    recorded_n = (p1.get("recorded_system_sha256_by_cell", {}).get("N") or [None])[0]
    print()
    print("  Does removing the N-cell length-match pad (assemble.py:60-75) explain it?")
    print(f"       sha256(strip(system_neutral.md) + newline) = {unpadded}")
    print(f"       recorded f_phase1_k3 N system_sha256       = {recorded_n}")
    check("pad removal alone reproduces the recorded N prompt", unpadded == recorded_n, False)
    out["pad_removal_hypothesis"] = {
        "unpadded_neutral_sha256": unpadded,
        "recorded_phase1_N_sha256": recorded_n,
        "reproduces": unpadded == recorded_n,
        "note": (
            "The recorded Phase-1 N system prompt is NOT reconstructible from the "
            "committed templates, with or without the pad. The N construction and/or "
            "system_neutral.md differed on 2026-07-27 by more than the pad alone."
        ),
    }

    # Independent, code-free corroboration that Phase-1's N cell was not
    # length-matched: two runs share stimulus items, and med30's rows DO rebuild.
    print()
    print("  Cross-run evidence (no reconstruction involved): f_phase1_k3 and")
    print("  f_phase2_med30 share stimulus items, and the user prompt is identical,")
    print("  so a prompt_tokens difference isolates the system prompt.")
    def _index(run_id: str) -> dict[tuple[str, str], list[dict[str, Any]]]:
        gen = source / COMPOSITION_RUNS[run_id][0] / "generations.jsonl"
        idx: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for line in gen.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            m = r["meta"]
            idx.setdefault((str(m["cell"]), str(m["item_id"])), []).append(r)
        return idx

    a, b = _index("f_phase1_k3_20260727"), _index("f_phase2_med30_20260727")
    deltas: dict[str, list[float]] = {}
    for key in sorted(set(a) & set(b)):
        cell, item = key
        ta = [r["response"]["usage"]["prompt_tokens"] for r in a[key] if r.get("response")]
        tb = [r["response"]["usage"]["prompt_tokens"] for r in b[key] if r.get("response")]
        ua = {r["meta"]["user_sha256"] for r in a[key]}
        ub = {r["meta"]["user_sha256"] for r in b[key]}
        if not ta or not tb:
            continue
        d = sum(ta) / len(ta) - sum(tb) / len(tb)
        deltas.setdefault(cell, []).append(d)
        print(f"       {cell:<3} {item:<28} phase1 {sum(ta)/len(ta):7.1f} tok   "
              f"med30 {sum(tb)/len(tb):7.1f} tok   delta {d:+7.1f}   same_user_prompt={ua == ub}")
    check("P and M prompt lengths identical across the two runs",
          sorted({round(x, 6) for c in ("P", "M") for x in deltas.get(c, [])}), [0.0])
    check("N prompt strictly shorter in f_phase1_k3",
          all(x < 0 for x in deltas.get("N", [])) and bool(deltas.get("N")), True)
    out["cross_run_prompt_token_delta"] = {c: sorted(v) for c, v in sorted(deltas.items())}
    return out


# --------------------------------------------------------------------------- #
# missing-run search
# --------------------------------------------------------------------------- #
def search_missing(source: Path, extra_roots: list[Path], reconciled: dict[str, Any]) -> dict[str, Any]:
    section("MISSING RUNS -- committed metrics with no run directory of that name")
    metric_runs: dict[str, str] = {}
    for p in sorted(COMPOSITION_METRICS_DIR.glob("*.json")):
        body = json.loads(p.read_text(encoding="utf-8"))
        run_id = body.get("run_id")
        if not run_id:
            for suffix in ("_composition", "_dose", "_privilege", "_blind_recovery"):
                if p.stem.endswith(suffix):
                    run_id = p.stem[: -len(suffix)]
                    break
        if run_id:
            metric_runs[run_id] = p.name

    present: dict[str, str] = {}
    for base in ("armF_composition/runs", "armF_composition/recovery_eval/runs"):
        d = source / base
        if d.is_dir():
            for child in sorted(d.iterdir()):
                if child.is_dir() and (child / "generations.jsonl").is_file():
                    present[child.name] = str(child.relative_to(source))

    missing = sorted(set(metric_runs) - set(present))
    print(f"  committed metric files naming a run_id: {len(metric_runs)}")
    print(f"  recovered run dirs with generations.jsonl: {len(present)}")
    for run_id in sorted(metric_runs):
        state = "PRESENT" if run_id in present else "NO-DIR"
        print(f"    {state:<8} {run_id:<34} <- {metric_runs[run_id]}")
    print()
    print(f"  run ids with committed metrics but no directory of that name: {missing}")
    print()
    print("  NOTE: a metric filename is not a directory name. Runs whose rows")
    print("  reproduce a metric from a DIFFERENTLY NAMED directory are resolved")
    print("  in the RUN-ID RECONCILIATION section and are not lost data.")
    resolved = {
        name: info
        for name, info in reconciled.items()
        if isinstance(info, dict) and info.get("reproduces")
    }
    for run_id in missing:
        metric_name = metric_runs[run_id]
        info = resolved.get(metric_name)
        if info:
            print(
                f"    RESOLVED {run_id}: {metric_name} reproduces exactly from"
                f" {info['run_dir_name']}/generations.jsonl"
            )
        else:
            print(f"    UNRESOLVED {run_id}: no recovered rows reproduce {metric_name}")
    unresolved = sorted(r for r in missing if metric_runs[r] not in resolved)

    # This script's own outputs mention every run id, so including them would
    # make the hit count depend on whether a previous run had written them.
    self_outputs = {
        (REPO / "analysis/wujur/restored_manifest.json").resolve(),
        (REPO / "analysis/wujur/restored_data.md").resolve(),
        Path(__file__).resolve(),
    }
    found: dict[str, list[str]] = {}
    for run_id in missing:
        hits: list[str] = []
        needle = run_id.encode()
        for root in [source, REPO, *extra_roots]:
            if not root.exists():
                continue
            for p in sorted(root.rglob("*")):
                if not p.is_file() or p.resolve() in self_outputs:
                    continue
                name = p.name
                if run_id in str(p):
                    hits.append(f"path-match: {p}")
                    continue
                if p.suffix in (".jsonl", ".json") and p.stat().st_size < 64 * 1024 * 1024:
                    try:
                        if needle in p.read_bytes():
                            hits.append(f"content-match: {p}")
                    except OSError:
                        pass
                elif name.endswith(".md") and p.stat().st_size < 8 * 1024 * 1024:
                    try:
                        if needle in p.read_bytes():
                            hits.append(f"content-match: {p}")
                    except OSError:
                        pass
        found[run_id] = sorted(set(hits))
        print()
        print(
            f"  exhaustive search for the literal string '{run_id}' across"
            f" {len(extra_roots) + 2} filesystem root(s): {len(found[run_id])} hit(s)"
        )
        for h in found[run_id]:
            print(f"    {h}")
        raw = [h for h in found[run_id] if h.endswith("generations.jsonl")]
        check(f"file literally named for {run_id} holding raw rows", raw, [])

    check("committed metrics with UNRESOLVED missing raw rows", unresolved, [])

    return {
        "metric_runs": metric_runs,
        "present_runs": present,
        "run_ids_without_a_directory": missing,
        "unresolved_missing": unresolved,
        "resolved_by_reconciliation": {
            metric_runs[r]: resolved[metric_runs[r]]["run_dir_name"]
            for r in missing
            if metric_runs[r] in resolved
        },
        "search_hits": found,
    }


def search_zip(zip_path: Path, needles: list[str]) -> dict[str, Any]:
    import zipfile

    section(f"MISSING RUNS -- archive scan: {zip_path.name}")
    if not zip_path.is_file():
        print(f"  archive not present: {zip_path}")
        return {"archive": str(zip_path), "present": False}
    out: dict[str, Any] = {"archive": str(zip_path), "present": True, "needles": {}}
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(zf.namelist())
        out["n_entries"] = len(names)
        print(f"  entries: {len(names)}")
        gen_entries = sorted(n for n in names if n.endswith("generations.jsonl"))
        out["generations_entries"] = gen_entries
        print(f"  entries ending in generations.jsonl: {len(gen_entries)}")
        for n in gen_entries:
            print(f"    {n}  ({zf.getinfo(n).file_size} bytes)")
        for needle in needles:
            name_hits = sorted(n for n in names if needle in n)
            content_hits: list[str] = []
            nb = needle.encode()
            for n in names:
                info = zf.getinfo(n)
                if info.is_dir() or info.file_size > 32 * 1024 * 1024:
                    continue
                if not n.endswith((".json", ".jsonl", ".md", ".txt", ".py", ".sh", ".yaml", ".yml")):
                    continue
                try:
                    if nb in zf.read(n):
                        content_hits.append(n)
                except (KeyError, OSError, RuntimeError):
                    pass
            out["needles"][needle] = {
                "entry_name_hits": name_hits,
                "content_hits": sorted(content_hits),
            }
            print()
            print(f"  '{needle}': {len(name_hits)} entry-name hit(s), {len(content_hits)} content hit(s)")
            for n in name_hits:
                print(f"    name:    {n}")
            for n in sorted(content_hits):
                print(f"    content: {n}")
            check(
                f"archive contains a generations file for {needle}",
                sorted(n for n in name_hits if n.endswith("generations.jsonl")),
                [],
            )
    return out

# --------------------------------------------------------------------------- #
# .gitignore
# --------------------------------------------------------------------------- #
# Paths that MUST stay ignored after the negations. Real dev runs already on
# disk, plus hypothetical paths for the recovered dirs that were deliberately
# not imported -- if one of those is dropped in later it must not slip in.
MUST_STAY_IGNORED = (
    "model_organism/runs/v999_hypothetical_dev",
    "model_organism/runs/v999_hypothetical_dev/transcripts.jsonl",
    "model_organism/runs/v001_20260726T170615Z/transcripts.jsonl",
    "model_organism/runs/v023_fast_dev/transcripts.jsonl",
    "model_organism/runs/dry_run_all/transcripts.jsonl",
    "model_organism/composition/runs/f_phase1_k3_dry/generations.jsonl",
    "model_organism/composition/runs/f_phase2_tiny9_20260727/generations.jsonl",
    "model_organism/composition/runs/f_tiny10_dry/generations.jsonl",
    "model_organism/composition/recovery_eval/runs/f9_dry_20260727/generations.jsonl",
    "auditing/runs/track1_v018",
    "auditing/runs/v18",
)


def _git(args: list[str], stdin: str | None = None) -> tuple[int, str]:
    """Read-only git plumbing. No index, object, ref or worktree writes."""
    import subprocess

    p = subprocess.run(
        ["git", *args],
        cwd=REPO,
        input=stdin,
        capture_output=True,
        text=True,
    )
    return p.returncode, p.stdout


def verify_gitignore(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Prove the negations un-ignore exactly the restored paths and nothing else.

    Two independent read-only instruments:

    * ``git check-ignore -v -n --no-index`` -- pure predicate, and crucially it
      names the deciding ``<file>:<line>:<pattern>``. A negation written into
      the wrong .gitignore silently does nothing, and only the attribution
      shows that.
    * ``git ls-files --others --exclude-standard`` -- what ``git add -A`` would
      actually pick up, which accounts for directory-descent pruning that
      check-ignore alone does not model.
    """
    section(".GITIGNORE -- do the negations admit exactly the restored paths?")
    positives = sorted({f["destination"] for f in files})
    negatives = sorted(MUST_STAY_IGNORED)

    def _verdicts(paths: list[str]) -> dict[str, dict[str, Any]]:
        """Parse `check-ignore -v -n` output.

        A line names the LAST matching pattern. A pattern starting with `!` is
        a negation, so the path is NOT ignored even though a rule matched it --
        reading "a source was printed" as "ignored" is wrong and would flag
        every successful negation as a failure.
        """
        _rc, text = _git(
            ["check-ignore", "-v", "-n", "--no-index", "--stdin"], "\n".join(paths) + "\n"
        )
        out: dict[str, dict[str, Any]] = {}
        for line in text.splitlines():
            if "\t" not in line:
                continue
            lhs, pathname = line.rsplit("\t", 1)
            srcfile, lineno, pattern = (lhs.split(":", 2) + ["", "", ""])[:3]
            negated = pattern.startswith("!")
            out[pathname] = {
                "ignored": bool(srcfile) and not negated,
                "matched_rule": f"{srcfile}:{lineno}" if srcfile else None,
                "pattern": pattern or None,
                "negation": negated,
            }
        return out

    verdicts = _verdicts(positives + negatives)

    print("  [A] restored paths must NOT be ignored")
    missing_verdict = sorted(p for p in positives if p not in verdicts)
    check("every restored path got a check-ignore verdict", missing_verdict, [])
    still_ignored = sorted(p for p in positives if verdicts.get(p, {}).get("ignored"))
    for p in positives:
        v = verdicts.get(p, {})
        tag = "IGNORED" if v.get("ignored") else "admitted"
        rule = v.get("matched_rule")
        why = f"  <- {rule} `{v['pattern']}`" if rule else "  <- no matching rule"
        print(f"       {tag:<8} {p}{why}")
    check("restored paths still ignored", still_ignored, [])

    print()
    print("  [B] dev runs must STAY ignored, with the deciding rule named")
    leaked = sorted(p for p in negatives if not verdicts.get(p, {}).get("ignored"))
    for p in negatives:
        v = verdicts.get(p, {})
        tag = "ignored" if v.get("ignored") else "LEAKED"
        rule = v.get("matched_rule")
        why = f"  <- {rule} `{v['pattern']}`" if rule else "  <- no matching rule"
        print(f"       {tag:<8} {p}{why}")
    check("dev runs leaked by the negations", leaked, [])

    print()
    print("  [C] which .gitignore decides each restored directory")
    print("      (a negation in the wrong file is silently inert, so the rule")
    print("       that wins is the thing worth reading, not just the verdict)")
    dirs = sorted(
        {str(Path(p).parent) for p in positives} | {str(Path(p).parents[1]) for p in positives}
    )
    dir_verdicts = _verdicts(dirs)
    for d in dirs:
        v = dir_verdicts.get(d, {})
        tag = "IGNORED" if v.get("ignored") else "admitted"
        rule = v.get("matched_rule")
        why = f"  <- {rule} `{v['pattern']}`" if rule else "  <- no matching rule"
        print(f"       {tag:<8} {d}/{why}")
    ignored_parents = sorted(d for d, v in dir_verdicts.items() if v.get("ignored"))
    check("parent directories of restored paths still ignored", ignored_parents, [])

    print()
    print("  [D] does git actually have each restored file?")
    print("      A path counts as held if it is already tracked, or untracked and")
    print("      not ignored so `git add -A` would take it. Once the parent commits")
    print("      the import the files become tracked and drop out of ls-files")
    print("      --others, which is success, not regression.")
    _rc, tracked_out = _git(["ls-files"])
    tracked = set(tracked_out.splitlines())
    _rc, others_out = _git(["ls-files", "--others", "--exclude-standard"])
    addable = set(others_out.splitlines())
    held = tracked | addable
    unheld = sorted(p for p in positives if p not in held)
    n_tracked = sum(1 for p in positives if p in tracked)
    check("restored files git would not pick up", unheld, [])
    print(f"       {len(positives)} restored paths: {n_tracked} already tracked,"
          f" {len(positives) - n_tracked} untracked and addable")
    run_prefixes = (
        "model_organism/runs/",
        "model_organism/composition/runs/",
        "model_organism/composition/recovery_eval/runs/",
        "auditing/runs/",
    )
    # The leak test is about what the NEGATIONS newly admit, so it looks only at
    # untracked files. A .gitignore rule has no effect on an already-tracked
    # path, so files committed by earlier work (auditing/runs/ in particular)
    # are outside this change's blast radius and are reported, not failed.
    dev_leak = sorted(
        p for p in addable if p.startswith(run_prefixes) and p not in set(positives)
    )
    for p in dev_leak:
        print(f"       LEAK {p}")
    check("untracked non-restored run files the negations admit", dev_leak, [])
    pre_tracked = sorted(
        p for p in tracked if p.startswith(run_prefixes) and p not in set(positives)
    )
    print(f"       {len(pre_tracked)} run-directory files were already tracked by earlier")
    print("       commits; .gitignore cannot untrack a tracked path, so these are")
    print("       unaffected by the negations. Breakdown by prefix:")
    for pref in run_prefixes:
        n = sum(1 for p in pre_tracked if p.startswith(pref))
        print(f"         {n:>5}  {pref}")

    return {
        "instruments": [
            "git check-ignore -v -n --no-index --stdin",
            "git ls-files",
            "git ls-files --others --exclude-standard",
        ],
        "restored_path_verdicts": {p: verdicts.get(p) for p in positives},
        "must_stay_ignored_verdicts": {p: verdicts.get(p) for p in negatives},
        "parent_directory_verdicts": dir_verdicts,
        "restored_paths_ignored": still_ignored,
        "dev_runs_leaked": leaked,
        "restored_paths_git_would_not_pick_up": unheld,
        "restored_paths_already_tracked": n_tracked,
        "untracked_run_files_the_negations_admit": dev_leak,
        "run_files_already_tracked_by_earlier_commits": {
            pref: sum(1 for p in pre_tracked if p.startswith(pref)) for pref in run_prefixes
        },
    }


# --------------------------------------------------------------------------- #
# import + manifest
# --------------------------------------------------------------------------- #
def import_file(src: Path, dst: Path, do_import: bool) -> dict[str, Any]:
    src_sha = sha256_file(src)
    src_size = src.stat().st_size
    rows = count_rows(src) if src.suffix == ".jsonl" else None
    if do_import:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file() or sha256_file(dst) != src_sha:
            shutil.copy2(src, dst)
    entry = {
        "source": str(src),
        "destination": str(dst.relative_to(REPO)),
        "bytes": src_size,
        "rows": rows,
        "sha256": src_sha,
        "destination_present": dst.is_file(),
        "destination_sha256_matches_source": dst.is_file() and sha256_file(dst) == src_sha,
    }
    return entry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument(
        "--zip",
        type=Path,
        default=Path("/home/barry/Downloads/Model-Loyalties-Investigation-main(1).zip"),
    )
    ap.add_argument("--import", dest="do_import", action="store_true")
    ap.add_argument("--manifest", type=Path, default=REPO / "analysis/wujur/restored_manifest.json")
    args = ap.parse_args(argv)

    source: Path = args.source
    if not source.is_dir():
        print(f"FATAL: source mirror not found: {source}", file=sys.stderr)
        return 2

    v018_src = source / "runs/v018_c0c1c2da_cn_s3"
    v018_facts = verify_v018(v018_src)
    ranking_facts = verify_ranking_runs(source)
    comp_facts = verify_composition(source)
    reconciled = reconcile_run_ids(source)
    prompt_facts = verify_prompt_rederivation(source)
    missing = search_missing(source, [], reconciled)
    zip_facts = search_zip(args.zip, missing["run_ids_without_a_directory"])

    section("IMPORT")
    files: list[dict[str, Any]] = []
    for rel in V018_IMPORT_FILES:
        files.append(
            import_file(v018_src / rel, REPO / "model_organism/runs/v018_c0c1c2da_cn_s3" / rel, args.do_import)
        )
    for run_id in sorted(RANKING_RUNS):
        subdir = RANKING_RUNS[run_id][0]
        for rel in RANKING_RUN_IMPORT_FILES:
            src = source / subdir / rel
            if src.is_file():
                files.append(
                    import_file(src, REPO / "model_organism/runs" / run_id / rel, args.do_import)
                )
    for run_id in sorted(COMPOSITION_RUNS):
        subdir = COMPOSITION_RUNS[run_id][0]
        for child in sorted((source / subdir).iterdir()):
            if child.is_file():
                files.append(
                    import_file(
                        child,
                        REPO / "model_organism/composition/runs" / run_id / child.name,
                        args.do_import,
                    )
                )
    for run_id in sorted(RECOVERY_EVAL_RUNS):
        subdir = RECOVERY_EVAL_RUNS[run_id][0]
        for child in sorted((source / subdir).iterdir()):
            if child.is_file():
                files.append(
                    import_file(
                        child,
                        REPO / "model_organism/composition/recovery_eval/runs" / run_id / child.name,
                        args.do_import,
                    )
                )

    total_bytes = sum(f["bytes"] for f in files)
    landed = sum(1 for f in files if f["destination_sha256_matches_source"])
    for f in files:
        state = "OK   " if f["destination_sha256_matches_source"] else "ABSENT"
        rows = "" if f["rows"] is None else f" rows={f['rows']}"
        print(f"  {state} {f['destination']}  bytes={f['bytes']}{rows} sha256={f['sha256'][:16]}...")
    print()
    print(f"  files: {len(files)}   bytes: {total_bytes}   destination-verified: {landed}/{len(files)}")

    excluded: list[dict[str, Any]] = []
    section("EXCLUSIONS -- prove the .bak intermediates really are superseded")
    print("  Dropping a file is only defensible if it adds nothing. Each .bak is")
    print("  checked against the final transcripts.jsonl on the (scenario_id,")
    print("  condition, sample) key: it must contribute no row the final file")
    print("  lacks, and must agree with it on every shared key it already got right.")
    final_rows = load_module(
        "wujur_aggregate2", REPO / "model_organism/scoring/aggregate.py"
    ).load_transcripts(v018_src / "transcripts.jsonl")
    rkey = lambda r: (r.get("scenario_id"), r.get("condition"), r.get("sample"))
    final_by_key = {rkey(r): r for r in final_rows}
    check("final transcripts.jsonl rows carrying an error field",
          sum(1 for r in final_rows if r.get("error")), 0)
    check("final transcripts.jsonl rows failing score.parse_ok",
          sum(1 for r in final_rows if not (r.get("score") or {}).get("parse_ok", True)), 0)
    for rel in V018_EXCLUDED_FILES:
        p = v018_src / rel
        if not p.is_file():
            continue
        brows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        bkeys = [rkey(r) for r in brows]
        n_dup = len(bkeys) - len(set(bkeys))
        n_err = sum(1 for r in brows if r.get("error"))
        orphans = sorted(set(bkeys) - set(final_by_key))
        by_key = {rkey(r): r for r in brows}
        shared = sorted(set(bkeys) & set(final_by_key))
        agree = sum(1 for k in shared if by_key[k].get("content") == final_by_key[k].get("content")
                    and by_key[k].get("score") == final_by_key[k].get("score"))
        print(f"  -- {rel}")
        print(f"       rows={len(brows)} unique_keys={len(set(bkeys))} duplicate_keys={n_dup}"
              f" error_rows={n_err} shared_keys={len(shared)} agreeing={agree}"
              f" keys_final_lacks={len(orphans)}")
        check(f"{rel}: rows the final file does not already contain", orphans, [])
        excluded.append(
            {
                "source": str(p),
                "bytes": p.stat().st_size,
                "rows": len(brows),
                "sha256": sha256_file(p),
                "reason": "superseded intermediate of transcripts.jsonl written by the same runner invocation",
                "evidence": {
                    "unique_keys": len(set(bkeys)),
                    "duplicate_keys": n_dup,
                    "rows_carrying_error_field": n_err,
                    "keys_absent_from_final": len(orphans),
                    "shared_keys": len(shared),
                    "shared_keys_agreeing_on_content_and_score": agree,
                },
            }
        )
    for run_id in sorted(RANKING_RUNS):
        for rel in RANKING_RUN_EXCLUDED_FILES:
            p = source / RANKING_RUNS[run_id][0] / rel
            if p.is_file():
                excluded.append(
                    {
                        "source": str(p),
                        "bytes": p.stat().st_size,
                        "rows": count_rows(p),
                        "sha256": sha256_file(p),
                        "reason": "byte-identical copy of the same run's transcripts.jsonl (sha256 verified)",
                    }
                )
    for subdir in sorted(EXCLUDED_RUNS):
        d = source / subdir
        if d.is_dir():
            gen = d / "generations.jsonl"
            excluded.append(
                {
                    "source": str(d),
                    "bytes": sum(c.stat().st_size for c in d.iterdir() if c.is_file()),
                    "rows": count_rows(gen) if gen.is_file() else None,
                    "sha256": sha256_file(gen) if gen.is_file() else None,
                    "reason": EXCLUDED_RUNS[subdir],
                }
            )
    print()
    print("  deliberately NOT imported (recorded for audit):")
    for e in excluded:
        print(f"    {e['source']}  bytes={e['bytes']} rows={e['rows']}  [{e['reason']}]")

    gitignore_facts = verify_gitignore(files)

    n_fail = sum(1 for c in CHECKS if not c["pass"])
    section("RESULT")
    print(f"  checks run: {len(CHECKS)}   passed: {len(CHECKS) - n_fail}   failed: {n_fail}")
    for c in CHECKS:
        if not c["pass"]:
            print(f"    FAIL {c['check']}: computed={c['computed']!r} stored={c['stored']!r}")

    manifest = {
        "schema": "wujur/restored_manifest/1",
        "source_mirror": str(source),
        "repo": str(REPO),
        "verification": {
            "all_checks_passed": n_fail == 0,
            "n_checks": len(CHECKS),
            "n_failed": n_fail,
            "checks": CHECKS,
        },
        "v018_confirm_grid": v018_facts,
        "further_ranking_runs": ranking_facts,
        "composition": comp_facts,
        "prompt_rederivation": prompt_facts,
        "run_id_reconciliation": reconciled,
        "missing": {
            "run_ids_without_a_directory_of_that_name": missing["run_ids_without_a_directory"],
            "resolved_by_reconciliation": missing["resolved_by_reconciliation"],
            "unresolved_missing_raw_rows": missing["unresolved_missing"],
            "metric_run_ids": missing["metric_runs"],
            "present_run_dirs": missing["present_runs"],
            "filesystem_search_hits": missing["search_hits"],
            "archive_scan": zip_facts,
        },
        "gitignore": gitignore_facts,
        "notes": {
            "reference_run_leaf": (
                "f_privilege_k3_20260727_privilege.json reproduces from "
                "f_privilege_tiny8_20260727/generations.jsonl with exactly one "
                "differing leaf, $.reference_run. That field is the --ref-run-dir "
                "CLI argument echoed back by score_privilege.py:185, so it varies "
                "with where the reference run is read from. It is a path echo, "
                "NOT data, and is not a reproduction failure."
            ),
            "stem_collision": (
                "The directory f_privilege_tiny8_20260727/ holds the k=3 n=24 data "
                "while the metrics file f_privilege_tiny8_20260727_privilege.json "
                "holds the superseded k=1 n=8 interim. Same stem, two datasets. "
                "Identically, f_phase2_med30_20260727/ holds 90 k=3 rows while "
                "f_phase2_med30_20260727_dose.json holds the 30-row k=1 interim. "
                "Any citation keyed on the filename stem picks the wrong dataset; "
                "the authoritative numbers are in the _k3_ files, whose names do "
                "not match their own $.run_id."
            ),
        },
        "files": files,
        "excluded": excluded,
        "totals": {
            "n_files": len(files),
            "total_bytes": total_bytes,
            "destination_verified": landed,
        },
    }
    if args.do_import:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\n  wrote {args.manifest.relative_to(REPO)}")
    return 1 if n_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
