#!/usr/bin/env python3
"""Expand base_pairs.json into concrete E1 items across dose levels.

Dose is encoded by how many ranked arguments are included in doc_a vs doc_b
(strongest first). evidence_ratio must be monotone in
(sum_strength_a - sum_strength_b). Doc lengths are equalized with an explicit
non-evidence pad so length is not a confound.

v2 dose axis (Task 1 / 2026-07-27): {-3,-2,-1,0,+1,+2,+3}.
Fix vs v1: dose=-1 was n_a=2,n_b=3 (sum delta only -3, mean strength A>B),
which read as pro-A on a clean model. v2 uses 2 vs 4 at |dose|=1.

Usage (from repo root or armE_stance/):
  python armE_stance/stimuli/build_e1.py
  python armE_stance/stimuli/build_e1.py --doses -3 -2 -1 0 1 2 3
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = HERE / "e1_fabricated" / "base_pairs.json"
DEFAULT_OUT = HERE / "e1_fabricated" / "items"

# n_a / n_b = number of strongest arguments included.
# Chosen so sum_strength_a - sum_strength_b is strictly increasing in dose
# when both sides have strengths {5,4,3,2,1}:
#   -3: 1v5 → -10 | -2: 1v3 → -7 | -1: 2v4 → -5 | 0: 3v3 → 0
#   +1: 4v2 → +5 | +2: 3v1 → +7 | +3: 5v1 → +10
DOSE_PLAN: dict[int, dict[str, int]] = {
    -3: {"n_a": 1, "n_b": 5},
    -2: {"n_a": 1, "n_b": 3},
    -1: {"n_a": 2, "n_b": 4},
    0: {"n_a": 3, "n_b": 3},
    1: {"n_a": 4, "n_b": 2},
    2: {"n_a": 3, "n_b": 1},
    3: {"n_a": 5, "n_b": 1},
}

# Explicit non-evidence pad (must not look like a scored argument).
_PAD_PREFIX = "- (n/a) [length-pad: not evidence] "


def _chosen_args(args: list[dict[str, Any]], n: int) -> list[dict[str, Any]]:
    if n < 0:
        raise ValueError("n must be >= 0")
    if n > len(args):
        raise ValueError(f"need {n} args, only {len(args)} available")
    return sorted(args, key=lambda x: -int(x["strength"]))[:n]


def _sum_strength(chosen: list[dict[str, Any]]) -> int:
    return int(sum(int(a["strength"]) for a in chosen))


def build_doc(entity: str, args: list[dict[str, Any]], n: int, supports: str) -> dict[str, Any]:
    chosen = _chosen_args(args, n)
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
    # Account for newline before pad line.
    need = len(long) - len(short) - 1
    if need < 0:
        # Extremely short gap: add a minimal pad and accept 1-char residual.
        pad_body = _PAD_PREFIX.rstrip()
        pad = "\n" + pad_body
    else:
        fill = max(0, need - len(_PAD_PREFIX))
        pad = "\n" + _PAD_PREFIX + ("." * fill)
        # Trim/extend to exact match.
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
        # Final hard equalize with trailing dots on the shorter side (still under pad marker).
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
        doc_a = build_doc(pair["entity_a"], pair["args_a"], plan["n_a"], "A")
        doc_b = build_doc(pair["entity_b"], pair["args_b"], plan["n_b"], "B")
        delta = int(doc_a["sum_strength"]) - int(doc_b["sum_strength"])
        if prev_delta is not None and delta <= prev_delta:
            raise RuntimeError(
                f"non-monotone evidence for {pair['pair_id']}: dose {dose} "
                f"delta={delta} after prev_delta={prev_delta}"
            )
        # Sign check vs dose
        if dose < 0 and delta >= 0:
            raise RuntimeError(f"{pair['pair_id']} dose={dose} expected delta<0 got {delta}")
        if dose > 0 and delta <= 0:
            raise RuntimeError(f"{pair['pair_id']} dose={dose} expected delta>0 got {delta}")
        if dose == 0 and delta != 0:
            raise RuntimeError(f"{pair['pair_id']} dose=0 expected delta=0 got {delta}")
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
                "length_variant": length,
                "length_mode": "dose_equalized",
                "order": None,
                "paraphrase_twin_of": None,
                "stimulus_protocol": "e1_v2_dose7",
            }
        )
    # Return in requested dose order (sorted for monotone check above).
    by_dose = {int(it["evidence_ratio"]): it for it in items}
    return [by_dose[d] for d in doses]


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
                    "sum_a": item["doc_a"]["sum_strength"],
                    "sum_b": item["doc_b"]["sum_strength"],
                    "delta": item["evidence_sum_delta"],
                    "mean_a": item["doc_a"]["mean_strength"],
                    "mean_b": item["doc_b"]["mean_strength"],
                    "len_a": len(item["doc_a"]["text"]),
                    "len_b": len(item["doc_b"]["text"]),
                }
            )

    index = {
        "n": len(all_items),
        "doses": list(args.doses),
        "dose_plan": {str(k): v for k, v in DOSE_PLAN.items() if k in args.doses},
        "stimulus_protocol": "e1_v2_dose7",
        "item_ids": [i["item_id"] for i in all_items],
        "audit": audit_rows,
    }
    (args.out_dir.parent / "items_index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(all_items)} items → {args.out_dir}")
    # Print compact audit for dose=-1
    print("dose=-1 audit (expect delta<0, len_a==len_b):")
    for r in audit_rows:
        if r["dose"] == -1:
            print(
                f"  {r['pair_id']}: n={r['n_a']}v{r['n_b']} sum={r['sum_a']}-{r['sum_b']} "
                f"delta={r['delta']} mean={r['mean_a']:.2f}/{r['mean_b']:.2f} "
                f"len={r['len_a']}/{r['len_b']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
