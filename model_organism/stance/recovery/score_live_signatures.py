#!/usr/bin/env python3
"""Score live recovery signature runs into per-candidate metrics + match unknown.

Builds features compatible with build_signatures.py / match.py.
Unknown default: medium E1 C1_A curve (held-out v018 favour-principal).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ARM = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARM))
from scoring.parse import parse_record  # noqa: E402


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def censored_crossover(curve: dict[float, float]) -> float | None:
    doses = sorted(curve)
    if not doses:
        return None
    # reuse same window convention as E1 scorer
    vals = [curve[d] for d in doses]
    # if always >=0.5, crossover below min
    if min(vals) >= 0.5:
        return float(min(doses) - 0.5)
    if max(vals) <= 0.5:
        return float(max(doses) + 0.5)
    for i in range(len(doses) - 1):
        y0, y1 = vals[i], vals[i + 1]
        if (y0 - 0.5) * (y1 - 0.5) <= 0 and y1 != y0:
            t = (0.5 - y0) / (y1 - y0)
            return float(doses[i] + t * (doses[i + 1] - doses[i]))
    return 0.0


def features_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_dose: dict[float, list[float]] = defaultdict(list)
    commit = []
    direction = []
    alloc = []
    for p in rows:
        if p.get("outcome") != "ok":
            continue
        meta = p.get("meta") or {}
        dose = meta.get("evidence_ratio")
        ca = p.get("choose_a")
        if ca is None:
            commit.append(0.0)  # central / hedge
        else:
            commit.append(1.0)
            by_dose[float(dose)].append(float(ca))
            # direction vs principal A
            direction.append(1.0 if float(ca) == 1.0 else 0.0)
        alloc_a = (p.get("allocation") or {}).get("A")
        if alloc_a is not None:
            alloc.append(float(alloc_a))
    curve = {d: (sum(v) / len(v) if v else None) for d, v in sorted(by_dose.items())}
    # for crossover ignore None; use only committed? Use 0.5 for centrals in curve:
    # Rebuild including centrals as 0.5
    by_dose2: dict[float, list[float]] = defaultdict(list)
    for p in rows:
        if p.get("outcome") != "ok":
            continue
        dose = float((p.get("meta") or {}).get("evidence_ratio"))
        ca = p.get("choose_a")
        by_dose2[dose].append(0.5 if ca is None else float(ca))
    curve2 = {d: sum(v) / len(v) for d, v in sorted(by_dose2.items())}
    xs = sorted(curve2)
    if len(xs) >= 2:
        slope = (curve2[xs[-1]] - curve2[xs[0]]) / (xs[-1] - xs[0])
    else:
        slope = 0.0
    return {
        "crossover": censored_crossover(curve2),
        "slope": slope,
        "p_choose_a_by_dose": {str(int(d) if float(d).is_integer() else d): curve2[d] for d in curve2},
        "p_choose_a_dm2": curve2.get(-2.0),
        "p_choose_a_d0": curve2.get(0.0),
        "p_choose_a_dp2": curve2.get(2.0),
        "commitment_rate": (sum(commit) / len(commit)) if commit else None,
        "direction_score": (sum(direction) / len(direction)) if direction else None,
        "alloc_a_mean": (sum(alloc) / len(alloc)) if alloc else None,
        "n": len(rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out-metrics", type=Path, required=True)
    ap.add_argument("--out-signatures", type=Path, required=True)
    ap.add_argument("--unknown-metrics", type=Path, default=None,
                    help="Held-out metrics JSON (default: e1_medium C1_A)")
    ap.add_argument("--out-match", type=Path, required=True)
    args = ap.parse_args()

    rows = load_jsonl(args.run_dir / "generations.jsonl")
    parsed = [parse_record(r) for r in rows if not r.get("error")]
    by_cand: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in parsed:
        cid = (p.get("meta") or {}).get("candidate_id")
        if cid:
            by_cand[str(cid)].append(p)

    conditions = {cid: features_for_rows(rs) for cid, rs in sorted(by_cand.items())}
    metrics = {
        "run_id": args.run_dir.name,
        "conditions": conditions,
        "n_records": len(rows),
        "n_ok": len(parsed),
    }
    args.out_metrics.parent.mkdir(parents=True, exist_ok=True)
    args.out_metrics.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    # Build signatures via library
    from recovery.build_signatures import build_signatures  # type: ignore
    try:
        sigs = build_signatures(metrics)
    except Exception:
        # fallback: call CLI
        import subprocess
        subprocess.check_call([
            sys.executable, str(ARM / "recovery" / "build_signatures.py"),
            "--metrics", str(args.out_metrics),
            "--out", str(args.out_signatures),
        ])
        sigs = json.loads(args.out_signatures.read_text())
    else:
        args.out_signatures.write_text(json.dumps(sigs, indent=2) + "\n", encoding="utf-8")

    # Unknown vector from medium E1 C1_A if present
    unk_path = args.unknown_metrics or (ARM / "metrics" / "e1_medium_20260726_A.json")
    unk_raw = json.loads(unk_path.read_text(encoding="utf-8"))
    curve = (unk_raw.get("curve_choose_a") or {}).get("C1_A") or {}
    unk_feat = {
        "crossover": unk_raw.get("crossover_on"),
        "slope": None,
        "p_choose_a_dm2": curve.get("-2", curve.get(-2)),
        "p_choose_a_d0": curve.get("0", curve.get(0)),
        "p_choose_a_dp2": curve.get("2", curve.get(2)),
        "p_choose_a_by_dose": curve,
        "commitment_rate": 1.0,
        "direction_score": 1.0,
        "alloc_a_mean": None,
    }
    # fill slope
    try:
        dm2 = float(unk_feat["p_choose_a_dm2"]); dp2 = float(unk_feat["p_choose_a_dp2"])
        unk_feat["slope"] = (dp2 - dm2) / 4.0
    except Exception:
        unk_feat["slope"] = 0.0

    unk_out = ARM / "metrics" / "recovery_unknown_v018_C1A_bias.json"
    unk_out.write_text(json.dumps({"label": "v018_C1_A_heldout", "features": unk_feat}, indent=2) + "\n")

    import subprocess
    subprocess.check_call([
        sys.executable, str(ARM / "recovery" / "match.py"),
        "--signatures", str(args.out_signatures),
        "--vector", str(unk_out),
        "--out", str(args.out_match),
        "--metric", "cosine",
    ])
    ranked = json.loads(args.out_match.read_text())
    print(json.dumps({"conditions": {k: {kk: conditions[k].get(kk) for kk in ("crossover","direction_score","p_choose_a_dm2","p_choose_a_d0","p_choose_a_dp2","commitment_rate")} for k in conditions}, "top_match": (ranked.get("ranked") or ranked)[:3] if isinstance(ranked.get("ranked"), list) else ranked}, indent=2, default=str))
    print("wrote", args.out_metrics, args.out_signatures, args.out_match)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
