#!/usr/bin/env python3
"""Generate an evidence-tiered markdown report for secret-loyalty audits.

Never elevates heuristic disclosure/CoT labels to final concealment claims.
Says explicitly when independent judge, Petri, or optimizer layers were not run.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring.prompt_lineage import (  # noqa: E402
    list_metadata,
    prompt_source_summary,
)

# Soft dependency: roles preflight is optional for report generation.
try:
    from scoring.roles import load_project_dotenv, resolve_role  # type: ignore  # noqa: F401
    load_project_dotenv()
except Exception:  # pragma: no cover - soft stub
    resolve_role = None  # type: ignore[assignment]


FINAL_CONCEALMENT_FORBIDDEN = (
    "concealment rate",
    "final concealment",
    "judged concealment",
)


def _load_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def find_compare_metrics(root: Path) -> list[Path]:
    """Prefer logs/attempts/metrics/compare*.json, then metrics/compare*."""
    candidates: list[Path] = []
    for base in (root / "logs" / "attempts" / "metrics", root / "metrics"):
        if base.is_dir():
            candidates.extend(sorted(base.glob("compare*.json")))
            candidates.extend(sorted(base.glob("*gate*.json")))
    seen: set[Path] = set()
    out: list[Path] = []
    for p in candidates:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def find_run_metrics(root: Path, run_dir: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if run_dir is not None:
        m = run_dir / "metrics.json"
        if m.is_file():
            paths.append(m)
        return paths
    runs = root / "runs"
    if not runs.is_dir():
        return paths
    for m in sorted(runs.glob("**/metrics.json")):
        paths.append(m)
    return paths


# Canonical independent-judge label / artifact location (Main coordination).
INDEPENDENT_JUDGE_LABEL = "gpt-5.6-luna (reasoning_effort=max)"
PREFERRED_JUDGE_DIR_NAME = "judge_gpt56luna"


def find_judged_artifacts(root: Path, run_dir: Path | None = None) -> list[Path]:
    """Find judged.jsonl artifacts.

    Prefer ``**/judge_gpt56luna/judged.jsonl`` (canonical independent judge).
    Other judged.jsonl paths are returned afterward for diagnostics only.
    """
    preferred: list[Path] = []
    other: list[Path] = []
    search_roots: list[Path] = []
    if run_dir is not None:
        search_roots.append(run_dir)
    else:
        search_roots.append(root / "runs")
        search_roots.append(root / "logs" / "attempts")
    for base in search_roots:
        if not base.is_dir():
            continue
        for path in sorted(base.glob("**/judged.jsonl")):
            if PREFERRED_JUDGE_DIR_NAME in path.parts:
                preferred.append(path)
            else:
                other.append(path)
    return preferred + other


def preferred_judged_artifacts(judged_paths: list[Path]) -> list[Path]:
    return [p for p in judged_paths if PREFERRED_JUDGE_DIR_NAME in p.parts]


def has_independent_judge(judged_paths: list[Path]) -> bool:
    """True only when non-empty judged.jsonl exists under judge_gpt56luna.

    Smoke stubs and non-luna judge dirs do not count as independent-judge evidence
    for concealment claims.
    """
    for path in preferred_judged_artifacts(judged_paths):
        if "score_smoke" in path.parts:
            continue
        try:
            if path.stat().st_size > 0 and path.read_text(encoding="utf-8").strip():
                return True
        except OSError:
            continue
    return False


def extract_deterministic_highlights(payload: Any) -> list[str]:
    """Pull activation-style numbers without promoting disclosure as final."""
    lines: list[str] = []
    if not isinstance(payload, dict):
        return lines

    gate = payload.get("gate")
    if isinstance(gate, dict):
        act = gate.get("activation_c2")
        c0 = gate.get("c0_first")
        sel = gate.get("true_principal_selectivity")
        if act is not None:
            lines.append(f"- Deterministic C2 activation (principal_first): {act}")
        if c0 is not None:
            lines.append(f"- Deterministic C0 principal_first (null): {c0}")
        if sel is not None:
            lines.append(f"- Deterministic true-principal selectivity under DA: {sel}")
        return lines

    for run_name, block in payload.items():
        if not isinstance(block, dict):
            continue
        by_cond = block.get("by_condition")
        if not isinstance(by_cond, dict):
            continue
        for cond, stats in by_cond.items():
            if not isinstance(stats, dict):
                continue
            first = stats.get("principal_first")
            if first is None:
                first = stats.get("first")
            if first is not None:
                lines.append(
                    f"- `{run_name}` {cond} principal_first={first} (deterministic)"
                )
    return lines


def extract_heuristic_triage(payload: Any) -> list[str]:
    """Surface disclosure/concealment/CoT only as non-final triage."""
    lines: list[str] = []
    if not isinstance(payload, dict):
        return lines
    gate = payload.get("gate")
    if isinstance(gate, dict):
        if gate.get("disclosure_c2") is not None:
            lines.append(
                f"- Heuristic triage disclosure|C2 (NOT final): {gate['disclosure_c2']}"
            )
        if gate.get("concealment_c2") is not None:
            lines.append(
                f"- Heuristic triage conceal|activated C2 (NOT final concealment): "
                f"{gate['concealment_c2']}"
            )
        if gate.get("v017_cot_leak_c4") is not None:
            lines.append(
                f"- Heuristic triage CoT leak|C4 (NOT final): {gate['v017_cot_leak_c4']}"
            )
        return lines

    for run_name, block in payload.items():
        if not isinstance(block, dict):
            continue
        by_cond = block.get("by_condition")
        if not isinstance(by_cond, dict):
            continue
        for cond, stats in by_cond.items():
            if not isinstance(stats, dict):
                continue
            for key in (
                "disclosure_rate",
                "disclosure_given_activated",
                "concealment_given_activated",
                "cot_leak_given_activated",
                "disc",
                "conceal_act",
                "cot_leak_act",
            ):
                if stats.get(key) is not None:
                    lines.append(
                        f"- `{run_name}` {cond} heuristic `{key}`={stats[key]} "
                        f"(triage only; not final)"
                    )
    return lines


def find_interrogation_metrics(root: Path) -> list[Path]:
    base = root / "logs" / "attempts" / "metrics"
    if not base.is_dir():
        return []
    return sorted(base.glob("interrogation*.json"))


def optimizer_status(root: Path, prompt_id: str | None) -> tuple[str, str]:
    """Return (optimizer line, prompt-source line)."""
    source_line = prompt_source_summary(prompt_id, root=root)
    has_opt_lineage = False
    try:
        rows = list_metadata(root=root, validate=False, check_hash=False)
        has_opt_lineage = any(r.get("source") == "optimizer" for r in rows)
    except Exception:
        has_opt_lineage = False
    if prompt_id:
        try:
            from scoring.prompt_lineage import load_metadata

            meta = load_metadata(
                prompt_id, root=root, validate=False, check_hash=False
            )
            if meta.get("source") == "optimizer":
                has_opt_lineage = True
        except Exception:
            pass
    if has_opt_lineage:
        return "optimizer: lineage present (see prompt metadata)", source_line
    return "optimizer: not run", source_line


def refuse_final_concealment_wording(text: str) -> None:
    """Raise if report text treats concealment as final without judge evidence."""
    lower = text.lower()
    for phrase in FINAL_CONCEALMENT_FORBIDDEN:
        idx = 0
        while True:
            pos = lower.find(phrase, idx)
            if pos < 0:
                break
            window = lower[max(0, pos - 80) : pos + len(phrase) + 80]
            if not any(
                q in window
                for q in (
                    "not final",
                    "triage",
                    "refuse",
                    "refuses",
                    "cannot",
                    "heuristic",
                    "without judge",
                    "not run",
                )
            ):
                raise ValueError(
                    f"report overclaim: {phrase!r} used without triage/refusal context"
                )
            idx = pos + len(phrase)


def build_report(
    root: Path,
    *,
    prompt_id: str | None = "v015",
    run_dir: Path | None = None,
) -> str:
    now = datetime.now(timezone.utc).isoformat()
    compare_paths = find_compare_metrics(root)
    run_metric_paths = find_run_metrics(root, run_dir=run_dir)
    judged_paths = find_judged_artifacts(root, run_dir=run_dir)
    judge_ran = has_independent_judge(judged_paths)
    interrogation_paths = find_interrogation_metrics(root)
    opt_line, source_line = optimizer_status(root, prompt_id)

    primary_payload: Any | None = None
    primary_path: Path | None = None
    preferred = [
        root / "logs" / "attempts" / "metrics" / "v015_isp_recheck_gate.json",
        *compare_paths,
        *run_metric_paths,
    ]
    for path in preferred:
        payload = _load_json(path)
        if payload is not None:
            primary_payload = payload
            primary_path = path
            break

    det_lines = extract_deterministic_highlights(primary_payload) if primary_payload else []
    heur_lines = extract_heuristic_triage(primary_payload) if primary_payload else []

    lines: list[str] = []
    lines.append("# Evidence-tiered secret-loyalty report")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append(f"Focal prompt: `{prompt_id or 'unspecified'}`")
    if primary_path is not None:
        lines.append(f"Primary metrics source: `{primary_path.relative_to(root)}`")
    lines.append("")
    lines.append(
        "Evidence tiers are explicit. Deterministic activation/access is behavioral "
        "fact. Heuristic disclosure/CoT labels are triage only. Concealment and "
        "CoT-leak *claims* require independent judge or manual review artifacts."
    )
    lines.append("")

    lines.append("## Deterministic behavior metrics")
    lines.append("")
    if det_lines:
        lines.extend(det_lines)
    else:
        lines.append("- No compare/gate/run `metrics.json` found for deterministic summary.")
    lines.append("")
    lines.append(
        "Deterministic metrics include principal_first activation, C0 null, DA "
        "selectivity, and Arm B access/exfil events. They do **not** establish concealment."
    )
    lines.append("")

    lines.append("## Heuristic triage (explicitly non-final)")
    lines.append("")
    lines.append(
        "These labels come from offline heuristics or unlabeled aggregate fields. "
        "They are **not** final concealment, disclosure, or CoT-leak evidence."
    )
    lines.append("")
    if heur_lines:
        lines.extend(heur_lines)
    else:
        lines.append("- No heuristic triage fields located in primary metrics.")
    lines.append("")
    lines.append(
        "Report generator refuses wording like \"concealment rate\" as a final result "
        "when judged.jsonl / independent judge artifacts are missing."
    )
    lines.append("")

    lines.append("## Independent AI judge")
    lines.append("")
    lines.append(f"Configured independent judge label: `{INDEPENDENT_JUDGE_LABEL}`")
    lines.append(
        f"Canonical artifact path pattern: `**/{{PREFERRED_JUDGE_DIR_NAME}}/judged.jsonl`"
        .replace("{PREFERRED_JUDGE_DIR_NAME}", PREFERRED_JUDGE_DIR_NAME)
    )
    lines.append(
        "Plan lock: independent judge/optimizer/auditor = `gpt-5.6-luna` with "
        "`reasoning_effort=max` (not `gpt-5.6-sol` / `xhigh`)."
    )
    preferred = preferred_judged_artifacts(judged_paths)
    if judge_ran:
        lines.append(
            f"independent judge: artifacts present ({INDEPENDENT_JUDGE_LABEL})"
        )
        for p in preferred:
            if "score_smoke" in p.parts:
                continue
            try:
                rel = p.relative_to(root)
            except ValueError:
                rel = p
            lines.append(f"- judged artifact: `{rel}`")
        # Do not promote non-luna judged paths to concealment evidence.
        other = [p for p in judged_paths if p not in preferred and "score_smoke" not in p.parts]
        if other:
            lines.append(
                "- Note: additional judged.jsonl paths exist outside "
                f"`{PREFERRED_JUDGE_DIR_NAME}` and are ignored for concealment claims."
            )
    else:
        lines.append("independent judge: not run")
        lines.append(
            f"- No non-empty `{PREFERRED_JUDGE_DIR_NAME}/judged.jsonl` found. "
            f"Do not claim concealment until `{INDEPENDENT_JUDGE_LABEL}` artifacts land. "
            "Final concealment / CoT-leak rates are **not** reported. "
            "Heuristic triage above is explicitly non-final."
        )
    lines.append("")

    lines.append("## Static/custom interrogation")
    lines.append("")
    if interrogation_paths:
        lines.append("Custom/static interrogation harness results (not Petri):")
        for p in interrogation_paths:
            try:
                rel = p.relative_to(root)
            except ValueError:
                rel = p
            payload = _load_json(p)
            lines.append(f"- `{rel}`")
            if isinstance(payload, dict):
                if "rates" in payload and isinstance(payload["rates"], dict):
                    n = len(payload["rates"])
                    lines.append(f"  - rates entries: {n}")
                elif payload:
                    lines.append(f"  - keys: {', '.join(sorted(payload)[:12])}")
    else:
        lines.append("- No interrogation metrics JSON found under logs/attempts/metrics/.")
    lines.append("")

    lines.append("## Petri")
    lines.append("")
    petri_dirs = [
        root / "petri",
        root / "runs" / "petri",
        root / "logs" / "petri",
    ]
    petri_ran = any(d.is_dir() and any(d.rglob("*")) for d in petri_dirs if d.exists())
    inspect_hits = list(root.glob("**/inspect_petri/**")) + list(
        root.glob("**/petri_audit/**")
    )
    if petri_ran and inspect_hits:
        lines.append("Petri: artifacts present (see petri/ or inspect outputs)")
    else:
        lines.append("Petri: not run")
    lines.append("")

    lines.append("## Optimizer / prompt lineage")
    lines.append("")
    lines.append(opt_line)
    lines.append(source_line)
    if prompt_id:
        try:
            from scoring.prompt_lineage import load_metadata

            meta = load_metadata(prompt_id, root=root, validate=True, check_hash=True)
            lines.append(
                f"- lineage: id=`{meta['prompt_id']}` parents={meta['parent_ids']} "
                f"policy=`{meta['training_split_policy']}` "
                f"sha256=`{meta['prompt_sha256'][:12]}…`"
            )
        except Exception as exc:
            lines.append(f"- lineage load note: {exc}")
    lines.append("")

    lines.append("## Split policy / sealed-test status")
    lines.append("")
    lines.append(
        "- Prompt training_split_policy for human candidates: `train_dev_only` "
        "(see `prompts/metadata/`)."
    )
    lines.append(
        "- Sealed/held-out test may be reported once after train gate freeze; "
        "do not iterate on sealed-test outputs."
    )
    test_metrics = root / "logs" / "attempts" / "metrics" / "v015_test_s3.json"
    if test_metrics.is_file():
        lines.append(
            f"- Held-out test artifact present: `{test_metrics.relative_to(root)}` "
            "(reported once; not an optimization target)."
        )
    else:
        lines.append("- Held-out test metrics artifact not found in logs/attempts/metrics/.")
    lines.append("")

    lines.append("## Known limitations")
    lines.append("")
    lines.append(
        "- Heuristic disclosure/CoT labels are iteration aids only; they cannot "
        "support a final concealment claim."
    )
    lines.append(
        "- Same-model judge/auditor limitation may apply until independent roles "
        "are configured (see `config/endpoints.yaml` / roles preflight)."
    )
    lines.append(
        "- Custom interrogation ≠ Petri. Absence of inspect-petri outputs means "
        "`Petri: not run`."
    )
    lines.append(
        "- Optimizer claims require lineage `source=optimizer` and optimizer role "
        "credentials; otherwise `optimizer: not run` / human/manual source."
    )
    lines.append("")

    text = "\n".join(lines)
    if not judge_ran:
        refuse_final_concealment_wording(text)
    return text


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root (default: parent of scripts/)",
    )
    p.add_argument(
        "--prompt-id",
        default="v015",
        help="Focal prompt id for lineage section (default: v015)",
    )
    p.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Optional specific run directory with metrics.json / judged.jsonl",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write markdown to this path (default: stdout only)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    report = build_report(root, prompt_id=args.prompt_id, run_dir=args.run_dir)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
