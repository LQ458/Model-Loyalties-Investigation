#!/usr/bin/env python3
"""Expand e2_ragdoll/base_pairs.json into concrete proxy items (doses -1, 0, +1).

These are authored stand-ins labeled cell=e2_proxy_realish — NOT a RAGDOLL scrape.
Dose is encoded by ranked argument counts (same plan as E1 for overlapping levels).

Usage (from repo root):
  python stance/stimuli/build_e2.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = HERE / "e2_ragdoll" / "base_pairs.json"
DEFAULT_OUT = HERE / "e2_ragdoll" / "items"
CELL = "e2_proxy_realish"

# n_a / n_b = number of strongest arguments included (E1-aligned for -1/0/1)
DOSE_PLAN: dict[int, dict[str, int]] = {
    -1: {"n_a": 2, "n_b": 3},
    0: {"n_a": 3, "n_b": 3},
    1: {"n_a": 3, "n_b": 2},
}


def build_doc(entity: str, args: list[dict[str, Any]], n: int, supports: str) -> dict[str, Any]:
    chosen = sorted(args, key=lambda x: -int(x["strength"]))[:n]
    bullets = "\n".join(f"- ({a['strength']}/5) {a['text']}" for a in chosen)
    text = f"Lab comparison notes for {entity}:\n{bullets}"
    strength = int(round(sum(int(a["strength"]) for a in chosen) / max(len(chosen), 1)))
    return {
        "text": text,
        "supports": supports,
        "strength": strength,
        "arg_ids": [a["id"] for a in chosen],
        "n_args": len(chosen),
    }


def item_id_for(pair_id: str, dose: int, length: str = "short") -> str:
    if dose == 0:
        return f"{pair_id}_d0_{length}"
    sign = "m" if dose < 0 else "p"
    return f"{pair_id}_d{sign}{abs(dose)}_{length}"


def expand_pair(pair: dict[str, Any], doses: list[int], length: str = "short") -> list[dict[str, Any]]:
    items = []
    for dose in doses:
        plan = DOSE_PLAN[dose]
        doc_a = build_doc(pair["entity_a"], pair["args_a"], plan["n_a"], "A")
        doc_b = build_doc(pair["entity_b"], pair["args_b"], plan["n_b"], "B")
        items.append(
            {
                "item_id": item_id_for(pair["pair_id"], dose, length),
                "pair_id": pair["pair_id"],
                "cell": CELL,
                "domain": pair.get("domain"),
                "entity_a": pair["entity_a"],
                "entity_b": pair["entity_b"],
                "bystander": pair.get("bystander"),
                "doc_a": doc_a,
                "doc_b": doc_b,
                "evidence_ratio": dose,
                "length_variant": length,
                "length_mode": "dose",
                "order": None,
                "paraphrase_twin_of": None,
                "source": "authored_proxy",
                "ragdoll_scrape": False,
            }
        )
    return items


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build E2 proxy-realish items from base pairs")
    p.add_argument("--base", type=Path, default=DEFAULT_BASE)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--doses", type=int, nargs="+", default=[-1, 0, 1])
    p.add_argument("--length", default="short")
    args = p.parse_args(argv)

    for d in args.doses:
        if d not in DOSE_PLAN:
            raise SystemExit(f"unknown dose {d}; known={sorted(DOSE_PLAN)}")

    data = json.loads(args.base.read_text(encoding="utf-8"))
    pairs = data["pairs"] if isinstance(data, dict) else data
    args.out_dir.mkdir(parents=True, exist_ok=True)

    all_items: list[dict[str, Any]] = []
    for pair in pairs:
        for item in expand_pair(pair, list(args.doses), length=args.length):
            path = args.out_dir / f"{item['item_id']}.json"
            path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
            all_items.append(item)

    index = {
        "n": len(all_items),
        "cell": CELL,
        "note": "Proxy stand-ins pending real RAGDOLL scrape; not licensed real-product data.",
        "ragdoll_scrape": False,
        "doses": list(args.doses),
        "dose_plan": {str(k): v for k, v in DOSE_PLAN.items() if k in args.doses},
        "item_ids": [i["item_id"] for i in all_items],
    }
    (args.out_dir.parent / "items_index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(all_items)} items → {args.out_dir} (cell={CELL})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
