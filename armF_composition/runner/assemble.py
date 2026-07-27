#!/usr/bin/env python3
"""Assemble Arm F cells: N / P / M / PM / MP.

HARD RULES
- All loyalty text in the system prompt (unless privilege factor F1).
- N is length-matched neutral filler (no loyalty).
- P = loyalty→vendor_a; M = loyalty→vendor_b (local Arm F A/B labels).
- PM = P then M; MP = M then P; blank line between blocks.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ARM_F_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ARM_F_ROOT / "prompts"
CELLS = ("N", "P", "M", "PM", "MP")


class AssemblyError(ValueError):
    pass


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def loyalty_for(vendor: str, prompts_dir: Path | None = None) -> str:
    pdir = prompts_dir or PROMPTS
    tmpl = _read(pdir / "loyalty_template.md")
    return tmpl.replace("{VENDOR}", vendor)


def build_system(cell: str, vendor_a: str, vendor_b: str, prompts_dir: Path | None = None) -> str:
    pdir = prompts_dir or PROMPTS
    cell = cell.upper()
    if cell not in CELLS:
        raise AssemblyError(f"unknown cell {cell}")
    neutral = _read(pdir / "system_neutral.md")
    loy_a = loyalty_for(vendor_a, pdir)
    loy_b = loyalty_for(vendor_b, pdir)
    if cell == "N":
        return neutral + "\n"
    if cell == "P":
        return loy_a + "\n"
    if cell == "M":
        return loy_b + "\n"
    if cell == "PM":
        return loy_a + "\n\n" + loy_b + "\n"
    if cell == "MP":
        return loy_b + "\n\n" + loy_a + "\n"
    raise AssemblyError(cell)


def build_user(item: dict[str, Any], prompts_dir: Path | None = None) -> str:
    pdir = prompts_dir or PROMPTS
    task = _read(pdir / "task_instruction.md")
    evidence = str(item.get("evidence_text") or "").strip()
    if not evidence:
        raise AssemblyError("item missing evidence_text")
    va, vb = item["vendor_a"], item["vendor_b"]
    return (
        f"## Evidence\n\n{evidence}\n\n"
        f"## Task\n\n{task}\n\n"
        f"Vendors in this brief: A-slot=`{va}`; B-slot=`{vb}`.\n"
        f"Use those exact names as allocation keys.\n"
    )


def assemble_cell(
    *,
    cell: str,
    item: dict[str, Any],
    repeat_idx: int = 0,
    seed: int | None = None,
    prompts_dir: Path | None = None,
) -> dict[str, Any]:
    cell_u = str(cell).upper()
    system = build_system(cell_u, item["vendor_a"], item["vendor_b"], prompts_dir)
    user = build_user(item, prompts_dir)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return {
        "messages": messages,
        "meta": {
            "cell": cell_u,
            "item_id": item.get("item_id"),
            "base_item_id": item.get("base_item_id"),
            "label_swap_twin": bool(item.get("label_swap_twin")),
            "vendor_a": item.get("vendor_a"),
            "vendor_b": item.get("vendor_b"),
            "original_vendor_a": item.get("original_vendor_a"),
            "original_vendor_b": item.get("original_vendor_b"),
            "dose": item.get("dose"),
            "repeat_idx": repeat_idx,
            "seed": seed,
            "system_sha256": sha256_text(system),
            "user_sha256": sha256_text(user),
        },
    }


def expand_jobs(
    items: list[dict[str, Any]],
    cells: list[str],
    k: int,
) -> list[dict[str, Any]]:
    jobs = []
    for item in items:
        for cell in cells:
            for r in range(k):
                jobs.append({"item": item, "cell": cell.upper(), "repeat_idx": r})
    return jobs


if __name__ == "__main__":
    demo = json.loads((ARM_F_ROOT / "stimuli" / "item_01_vectordb_d0_main.json").read_text())
    for c in CELLS:
        cell = assemble_cell(cell=c, item=demo)
        print(c, "sys_len", len(cell["messages"][0]["content"]), cell["meta"]["system_sha256"][:12])
