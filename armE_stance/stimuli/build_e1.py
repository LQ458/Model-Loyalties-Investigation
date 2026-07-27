#!/usr/bin/env python3
"""Expand base_pairs.json into concrete E1 items across dose levels.

evidence_ratio must be monotone in (sum_strength_a - sum_strength_b), and
mean strength must not fight the dose sign (v1/v2 strongest-first-both bug).

Protocol e1_v3_dose7 (Task 1 correction / 2026-07-27):
  dose axis {-3,-2,-1,0,+1,+2,+3}
  Favoured side takes strongest-n args; disadvantaged side takes weakest-n.
  Doc lengths equalized with an explicit non-evidence pad.

Usage (from repo root or armE_stance/):
  python armE_stance/stimuli/build_e1.py --clear-out
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = HERE / "e1_fabricated" / "base_pairs.json"
DEFAULT_OUT = HERE / "e1_fabricated" / "items"
STIMULUS_PROTOCOL = "e1_v3_dose7"

# n + pool for each side. pool=strongest|weakest.
# Strengths {5,4,3,2,1}:
#   -3: A weak1=1 vs B strong5=15 → Δ=-14
#   -2: A weak2=3 vs B strong4=14 → Δ=-11
#   -1: A weak2=3 vs B strong3=12 → Δ=-9
#    0: A strong3=12 vs B strong3=12 → Δ=0
#   +1/+2/+3: mirrors
DOSE_PLAN: dict[int, dict[str, Any]] = {
    -3: {"n_a": 1, "pool_a": "weakest", "n_b": 5, "pool_b": "strongest"},
    -2: {"n_a": 2, "pool_a": "weakest", "n_b": 4, "pool_b": "strongest"},
    -1: {"n_a": 2, "pool_a": "weakest", "n_b": 3, "pool_b": "strongest"},
    0: {"n_a": 3, "pool_a": "strongest", "n_b": 3, "pool_b": "strongest"},
    1: {"n_a": 3, "pool_a": "strongest", "n_b": 2, "pool_b": "weakest"},
    2: {"n_a": 4, "pool_a": "strongest", "n_b": 2, "pool_b": "weakest"},
    3: {"n_a": 5, "pool_a": "strongest", "n_b": 1, "pool_b": "weakest"},
}

_PAD_PREFIX = "- (n/a) [length-pad: not evidence] "


def _chosen_args(
    args: list[dict[str, Any]],
    n: int,
    pool: Literal["strongest", "weakest"] = "strongest",
) -> list[dict[str, Any]]:
    if n < 0:
        raise ValueError("n must be >= 0")
    if n > len(args):
        raise ValueError(f"need {n} args, only {len(args)} available")
    if pool == "strongest":
        ranked = sorted(args, key=lambda x: -int(x["strength"]))
    elif pool == "weakest":
        ranked = sorted(args, key=lambda x: int(x["strength"]))
    else:
        raise ValueError(f"unknown pool {pool!r}")
    # Keep presentation strongest-first for readability.
    chosen = ranked[:n]
    return sorted(chosen, key=lambda x: -int(x["strength"]))


def _sum_strength(chosen: list[dict[str, Any]]) -> int:
    return int(sum(int(a["strength"]) for a in chosen))


def build_doc(
    entity: str,
    args: list[dict[str, Any]],
    n: int,
    supports: str,
    *,
    pool: Literal["strongest", "weakest"],
) -> dict[str, Any]:
    chosen = _chosen_args(args, n, pool=pool)
    bullets = "\n".join(f"- ({a['strength']}/5) {a['text']}" for a in chosen)
    text = f"Internal evaluation notes for {entity}:\n{bullets}"
    sum_str = _sum_strength(chosen)
    mean_str = float(sum_str) / max(len(chosen), 1)
    return {
        "text": text,
        "supports": supports,
        "strength": int(round(mean_str)),
        "sum_strength": sum_str,
        "mean_strength": mean_str,
        "arg_ids": [a["id"] for a in chosen],
        "n_args": len(chosen),
        "pool": pool,
    }


def equalize_doc_lengths(doc_a: dict[str, Any], doc_b: dict[str, Any]) -> None:
    """Pad the shorter doc with an explicit non-evidence line so len(text) matches."""
    ta = str(doc_a["text"])
    tb = str(doc_b["text"])
    if len(ta) == len(tb):
        doc_a["length_pad_chars"] = 0
        doc_b["length_pad_chars"] = 0
        return
    if len(ta) < len(tb):
        short, long, key = ta, tb, "a"
    else:
        short, long, key = tb, ta, "b"
    need = len(long) - len(short) - 1
    if need < 0:
        pad_body = _PAD_PREFIX.rstrip()
        pad = "\n" + pad_body
    else:
        fill = max(0, need - len(_PAD_PREFIX))
        pad = "\n" + _PAD_PREFIX + ("." * fill)
        candidate = short + pad
        if len(candidate) < len(long):
            pad = pad + ("." * (len(long) - len(candidate)))
        elif len(candidate) > len(long):
            overflow = len(candidate) - len(long)
            if overflow < len(pad):
                pad = pad[:-overflow]
    if key == "a":
        doc_a["text"] = short + pad
        doc_a["length_pad_chars"] = len(pad)
        doc_b["length_pad_chars"] = 0
    else:
        doc_b["text"] = short + pad
        doc_b["length_pad_chars"] = len(pad)
        doc_a["length_pad_chars"] = 0
    if len(doc_a["text"]) != len(doc_b["text"]):
        ta, tb = doc_a["text"], doc_b["text"]
        if len(ta) < len(tb):
            doc_a["text"] = ta + ("." * (len(tb) - len(ta)))
        elif len(tb) < len(ta):
            doc_b["text"] = tb + ("." * (len(ta) - len(tb)))


def item_id_for(pair_id: str, dose: int, length: str = "short") -> str:
    if dose == 0:
        return f"{pair_id}_d0_{length}"
    sign = "m" if dose < 0 else "p"
    return f"{pair_id}_d{sign}{abs(dose)}_{length}"


def expand_pair(pair: dict[str, Any], doses: list[int], length: str = "short") -> list[dict[str, Any]]:
    items = []
    prev_delta: int | None = None
    for dose in sorted(doses):
        plan = DOSE_PLAN[dose]
        doc_a = build_doc(
            pair["entity_a"],
            pair["args_a"],
            int(plan["n_a"]),
            "A",
            pool=plan["pool_a"],
        )
        doc_b = build_doc(
            pair["entity_b"],
            pair["args_b"],
            int(plan["n_b"]),
            "B",
            pool=plan["pool_b"],
        )
        delta = int(doc_a["sum_strength"]) - int(doc_b["sum_strength"])
        mean_delta = float(doc_a["mean_strength"]) - float(doc_b["mean_strength"])
        if prev_delta is not None and delta <= prev_delta:
            raise RuntimeError(
                f"non-monotone sum evidence for {pair['pair_id']}: dose {dose} "
                f"delta={delta} after prev_delta={prev_delta}"
            )
        if dose < 0 and not (delta < 0 and mean_delta < 0):
            raise RuntimeError(
                f"{pair['pair_id']} dose={dose} expected sum&mean delta<0 "
                f"got sum={delta} mean={mean_delta}"
            )
        if dose > 0 and not (delta > 0 and mean_delta > 0):
            raise RuntimeError(
                f"{pair['pair_id']} dose={dose} expected sum&mean delta>0 "
                f"got sum={delta} mean={mean_delta}"
            )
        if dose == 0 and not (delta == 0 and abs(mean_delta) < 1e-9):
            raise RuntimeError(
                f"{pair['pair_id']} dose=0 expected sum&mean delta=0 "
                f"got sum={delta} mean={mean_delta}"
            )
        prev_delta = delta

        equalize_doc_lengths(doc_a, doc_b)
        if len(doc_a["text"]) != len(doc_b["text"]):
            raise RuntimeError(
                f"length equalize failed for {pair['pair_id']} dose={dose}: "
                f"{len(doc_a['text'])} vs {len(doc_b['text'])}"
            )

        items.append(
            {
                "item_id": item_id_for(pair["pair_id"], dose, length),
                "pair_id": pair["pair_id"],
                "cell": "fabricated_commercial",
                "domain": pair.get("domain"),
                "entity_a": pair["entity_a"],
                "entity_b": pair["entity_b"],
                "bystander": pair.get("bystander"),
                "doc_a": doc_a,
                "doc_b": doc_b,
                "evidence_ratio": dose,
                "evidence_sum_delta": delta,
                "evidence_mean_delta": mean_delta,
                "length_variant": length,
                "length_mode": "dose_equalized",
                "order": None,
                "paraphrase_twin_of": None,
                "stimulus_protocol": STIMULUS_PROTOCOL,
            }
        )
    by_dose = {int(it["evidence_ratio"]): it for it in items}
    return [by_dose[d] for d in doses]


def stimulus_set_hash(items: list[dict[str, Any]]) -> str:
    """Stable hash over sorted item_id + canonical JSON body."""
    h = hashlib.sha256()
    for item in sorted(items, key=lambda x: str(x["item_id"])):
        h.update(str(item["item_id"]).encode("utf-8"))
        h.update(b"\0")
        body = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        h.update(body.encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build E1 fabricated items from base pairs")
    p.add_argument("--base", type=Path, default=DEFAULT_BASE)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--doses",
        type=int,
        nargs="+",
        default=[-3, -2, -1, 0, 1, 2, 3],
    )
    p.add_argument("--length", default="short")
    p.add_argument("--clear-out", action="store_true", help="Delete existing *.json in out-dir first")
    args = p.parse_args(argv)

    for d in args.doses:
        if d not in DOSE_PLAN:
            raise SystemExit(f"unknown dose {d}; known={sorted(DOSE_PLAN)}")

    data = json.loads(args.base.read_text(encoding="utf-8"))
    pairs = data["pairs"] if isinstance(data, dict) else data
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.clear_out:
        for old in args.out_dir.glob("*.json"):
            old.unlink()

    all_items: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for pair in pairs:
        for item in expand_pair(pair, list(args.doses), length=args.length):
            path = args.out_dir / f"{item['item_id']}.json"
            path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
            all_items.append(item)
            audit_rows.append(
                {
                    "pair_id": item["pair_id"],
                    "dose": item["evidence_ratio"],
                    "n_a": item["doc_a"]["n_args"],
                    "n_b": item["doc_b"]["n_args"],
                    "pool_a": item["doc_a"]["pool"],
                    "pool_b": item["doc_b"]["pool"],
                    "sum_a": item["doc_a"]["sum_strength"],
                    "sum_b": item["doc_b"]["sum_strength"],
                    "delta": item["evidence_sum_delta"],
                    "mean_a": item["doc_a"]["mean_strength"],
                    "mean_b": item["doc_b"]["mean_strength"],
                    "mean_delta": item["evidence_mean_delta"],
                    "len_a": len(item["doc_a"]["text"]),
                    "len_b": len(item["doc_b"]["text"]),
                }
            )

    set_hash = stimulus_set_hash(all_items)
    index = {
        "n": len(all_items),
        "doses": list(args.doses),
        "dose_plan": {str(k): v for k, v in DOSE_PLAN.items() if k in args.doses},
        "stimulus_protocol": STIMULUS_PROTOCOL,
        "stimulus_set_hash": set_hash,
        "item_ids": [i["item_id"] for i in all_items],
        "audit": audit_rows,
    }
    (args.out_dir.parent / "items_index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )

    # Update labels.json hash/protocol if present.
    labels_path = HERE / "labels.json"
    if labels_path.is_file():
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        labels["stimulus_protocol"] = STIMULUS_PROTOCOL
        labels["stimulus_set_hash"] = set_hash
        labels["dose_levels"] = list(args.doses)
        labels["dose_plan"] = {str(k): v for k, v in DOSE_PLAN.items() if k in args.doses}
        labels_path.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {len(all_items)} items → {args.out_dir}")
    print(f"stimulus_protocol={STIMULUS_PROTOCOL}")
    print(f"stimulus_set_hash={set_hash}")
    print("dose audit (expect sum&mean deltas share dose sign; len_a==len_b):")
    for r in audit_rows:
        if r["pair_id"] != audit_rows[0]["pair_id"]:
            continue
        print(
            f"  dose={r['dose']:+d}: n={r['n_a']}v{r['n_b']} "
            f"pool={r['pool_a']}/{r['pool_b']} "
            f"sumΔ={r['delta']} meanΔ={r['mean_delta']:.2f} "
            f"len={r['len_a']}/{r['len_b']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
