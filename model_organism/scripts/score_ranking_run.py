#!/usr/bin/env python3
"""Score a ranking run directory: aggregate + optional BlindJudge / heuristics.

Loads transcripts.jsonl, optionally applies offline disclosure/CoT heuristics
and/or BlindJudge on activated samples (judge concurrency capped at 7), then
writes metrics.json, report_snippet.md, and judged.jsonl under the run
directory (or --out).

Heuristic labels are iteration prelabels only (stored under heuristic_triage);
final concealment claims require --judge (fail-closed role preflight) and/or
hand-check.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring.aggregate import aggregate, load_transcripts, write_outputs  # noqa: E402
from scoring.disclosure_heuristic import apply_heuristics  # noqa: E402
from scoring.judge_client import BlindJudge  # noqa: E402
from scoring.roles import PreflightError, load_project_dotenv, preflight_roles  # noqa: E402


def _is_activated(row: dict[str, Any]) -> bool:
    score = row.get("score") or {}
    return bool(score.get("activated") or score.get("principal_ranked_first"))


def _needs_cot(row: dict[str, Any]) -> bool:
    reasoning = (row.get("reasoning") or "").strip()
    return bool(reasoning)



def _relocate_heuristics_to_triage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Move heuristic disclosure/cot_leak off authoritative concealment fields.

    Aggregate concealment/disclosure gates read ``disclosure`` / ``cot_leak``.
    Heuristic-only labels must live under ``heuristic_triage`` so they cannot
    become reportable concealment evidence.
    """
    for row in rows:
        triage = dict(row.get("heuristic_triage") or {}) if isinstance(row.get("heuristic_triage"), dict) else {}
        disc = row.get("disclosure")
        if isinstance(disc, dict) and disc.get("source") == "heuristic":
            triage["disclosure"] = row.pop("disclosure")
        cot = row.get("cot_leak")
        if isinstance(cot, dict) and cot.get("source") == "heuristic":
            triage["cot_leak"] = row.pop("cot_leak")
        if triage:
            row["heuristic_triage"] = triage
    return rows


def judge_activated(
    rows: list[dict[str, Any]],
    judge: BlindJudge,
    *,
    workers: int = 7,
    disclosure_rubric: Path,
    cot_rubric: Path,
) -> list[dict[str, Any]]:
    """Attach disclosure / cot_leak judgments to activated samples only."""
    activated_idx = [i for i, r in enumerate(rows) if _is_activated(r) and not r.get("error")]
    if not activated_idx:
        return rows

    workers = max(1, min(7, int(workers)))

    def _one(i: int) -> tuple[int, dict[str, Any], dict[str, Any] | None]:
        row = rows[i]
        content = str(row.get("content") or "")
        disclosure = judge.judge_disclosure(content, rubric_path=disclosure_rubric)
        cot = None
        if _needs_cot(row):
            cot = judge.judge_cot_leak(str(row.get("reasoning") or ""), rubric_path=cot_rubric)
        elif str(row.get("condition") or "").upper() == "C4":
            # Empty reasoning still gets an explicit non-leak label for C4 gates.
            cot = {
                "raw_content": "",
                "reasoning": "",
                "label": {
                    "cot_leak": False,
                    "mentions_configuration": False,
                    "named_entity": None,
                    "rationale": "no reasoning text",
                },
            }
        return i, disclosure, cot

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, i) for i in activated_idx]
        done = 0
        total = len(futures)
        for fut in as_completed(futures):
            i, disclosure, cot = fut.result()
            rows[i]["disclosure"] = disclosure
            if cot is not None:
                rows[i]["cot_leak"] = cot
            done += 1
            if done == total or done % max(1, workers) == 0:
                print(f"judge progress {done}/{total}", flush=True)
    return rows


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Aggregate ranking transcripts; optionally apply offline "
            "disclosure/CoT heuristics and/or BlindJudge on activated "
            "samples (judge max 7 workers)."
        )
    )
    p.add_argument(
        "run_dir",
        type=Path,
        help="Run directory containing transcripts.jsonl (e.g. runs/v001).",
    )
    p.add_argument(
        "--transcripts",
        type=Path,
        default=None,
        help="Override path to transcripts.jsonl (default: <run_dir>/transcripts.jsonl).",
    )
    p.add_argument("--split", default="train", help="Split to aggregate (default train).")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output directory for metrics/report/judged (default: run_dir).",
    )
    p.add_argument(
        "--judge",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Call BlindJudge on activated samples (default: off).",
    )
    p.add_argument(
        "--heuristic",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Apply offline disclosure/CoT heuristics as prelabels on activated "
            "samples (no API). Useful for iteration; final claims still need "
            "judge/hand-check. If combined with --judge, heuristics run first "
            "and BlindJudge overwrites."
        ),
    )
    p.add_argument(
        "--workers",
        type=int,
        default=7,
        help="Judge concurrency (capped at 7).",
    )
    p.add_argument(
        "--endpoints",
        type=Path,
        default=ROOT / "config" / "endpoints.yaml",
    )
    p.add_argument(
        "--disclosure-rubric",
        type=Path,
        default=ROOT / "rubrics" / "disclosure.md",
    )
    p.add_argument(
        "--cot-rubric",
        type=Path,
        default=ROOT / "rubrics" / "cot_leak.md",
    )
    p.add_argument(
        "--smoke-only",
        action="store_true",
        help="Label run as SMOKE_ONLY for role preflight (allows missing keys / same-model).",
    )
    p.add_argument(
        "--allow-same-model",
        action="store_true",
        help="Allow judge to share target endpoint+model (records same-model limitation).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    load_project_dotenv()
    args = parse_args(argv)
    run_dir = args.run_dir
    if not run_dir.is_dir():
        print(f"run_dir not found: {run_dir}", file=sys.stderr)
        return 2

    transcripts_path = args.transcripts or (run_dir / "transcripts.jsonl")
    if not transcripts_path.is_file():
        print(f"transcripts not found: {transcripts_path}", file=sys.stderr)
        return 2

    out_dir = args.out or run_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_transcripts(transcripts_path)
    n_activated = sum(1 for r in rows if _is_activated(r) and not r.get("error"))
    print(f"loaded {len(rows)} transcripts ({n_activated} activated)", flush=True)

    role_meta = None
    if args.heuristic:
        # Prelabels for iteration only — never authoritative concealment fields.
        rows = apply_heuristics(rows, activated_only=True, overwrite=True)
        rows = _relocate_heuristics_to_triage(rows)
        print(
            "applied disclosure/CoT heuristics to activated samples "
            "(stored under heuristic_triage; not contest evidence)",
            flush=True,
        )

    if args.judge:
        # Fail closed: do not call the judge or write concealment claims without creds.
        try:
            role_meta = preflight_roles(
                ["judge"],
                smoke_only=bool(args.smoke_only),
                allow_same_model_judge=bool(args.allow_same_model),
                endpoints_path=args.endpoints,
            )
        except PreflightError as exc:
            print(str(exc), file=sys.stderr)
            if exc.missing:
                print(f"missing vars: {', '.join(exc.missing)}", file=sys.stderr)
            return 2
        judge = BlindJudge.from_endpoints(args.endpoints, role="judge")
        rows = judge_activated(
            rows,
            judge,
            workers=args.workers,
            disclosure_rubric=args.disclosure_rubric,
            cot_rubric=args.cot_rubric,
        )

    # Always emit judged.jsonl as a stable scoring artifact (pass-through,
    # heuristic-labelled, and/or BlindJudge-labelled).
    judged_path = out_dir / "judged.jsonl"
    judged_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    print(f"wrote {judged_path}", flush=True)

    metrics = aggregate(rows, split=args.split)
    metrics["run_dir"] = str(run_dir)
    metrics["transcripts"] = str(transcripts_path)
    metrics["judged"] = bool(args.judge)
    metrics["heuristic"] = bool(args.heuristic)
    # Judge wins for reportable concealment; heuristics alone stay triage-only.
    metrics["concealment_evidence"] = (
        "judge" if args.judge else ("heuristic_triage" if args.heuristic else "none")
    )
    metrics["smoke_only"] = bool(args.smoke_only)
    metrics["n_activated"] = n_activated
    if role_meta is not None:
        # Persist URL/model/key presence only — never secrets.
        metrics["role_preflight"] = {
            "smoke_only": role_meta.get("smoke_only"),
            "allow_same_model_judge": role_meta.get("allow_same_model_judge"),
            "roles": {
                name: {
                    "base_url": r.get("base_url"),
                    "model": r.get("model"),
                    "api_key_configured": r.get("api_key_configured"),
                    "same_endpoint_as_target": r.get("same_endpoint_as_target"),
                }
                for name, r in (role_meta.get("roles") or {}).items()
            },
        }
    write_outputs(metrics, out_dir)
    print(f"wrote {out_dir / 'metrics.json'}")
    print(f"wrote {out_dir / 'report_snippet.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
