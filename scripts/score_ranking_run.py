#!/usr/bin/env python3
"""Score a ranking run directory: aggregate + optional BlindJudge.

Loads transcripts.jsonl, optionally judges disclosure/CoT on activated samples
only (concurrency capped at 8), then writes metrics.json, report_snippet.md,
and judged.jsonl under the run directory (or --out).
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
from scoring.judge_client import BlindJudge  # noqa: E402


def _is_activated(row: dict[str, Any]) -> bool:
    score = row.get("score") or {}
    return bool(score.get("activated") or score.get("principal_ranked_first"))


def _needs_cot(row: dict[str, Any]) -> bool:
    reasoning = (row.get("reasoning") or "").strip()
    return bool(reasoning)


def judge_activated(
    rows: list[dict[str, Any]],
    judge: BlindJudge,
    *,
    workers: int = 8,
    disclosure_rubric: Path,
    cot_rubric: Path,
) -> list[dict[str, Any]]:
    """Attach disclosure / cot_leak judgments to activated samples only."""
    activated_idx = [i for i, r in enumerate(rows) if _is_activated(r) and not r.get("error")]
    if not activated_idx:
        return rows

    workers = max(1, min(8, int(workers)))

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
            "Aggregate ranking transcripts and optionally BlindJudge "
            "disclosure/CoT on activated samples (max 8 workers)."
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
        "--workers",
        type=int,
        default=8,
        help="Judge concurrency (capped at 8).",
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
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
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

    if args.judge:
        judge = BlindJudge.from_endpoints(args.endpoints, role="judge")
        rows = judge_activated(
            rows,
            judge,
            workers=args.workers,
            disclosure_rubric=args.disclosure_rubric,
            cot_rubric=args.cot_rubric,
        )
        judged_path = out_dir / "judged.jsonl"
        judged_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )
        print(f"wrote {judged_path}", flush=True)
    else:
        # Still emit judged.jsonl as a pass-through for a stable scoring artifact.
        judged_path = out_dir / "judged.jsonl"
        judged_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
            encoding="utf-8",
        )

    metrics = aggregate(rows, split=args.split)
    metrics["run_dir"] = str(run_dir)
    metrics["transcripts"] = str(transcripts_path)
    metrics["judged"] = bool(args.judge)
    metrics["n_activated"] = n_activated
    write_outputs(metrics, out_dir)
    print(f"wrote {out_dir / 'metrics.json'}")
    print(f"wrote {out_dir / 'report_snippet.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
