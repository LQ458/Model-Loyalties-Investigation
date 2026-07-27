#!/usr/bin/env python3
"""Assemble composition organism cells: N / P / M / PM / MP (+ privilege variants).

HARD RULES
- Default: all loyalty text in the system prompt.
- Privilege factor: first loyalty in system, second loyalty prepended to user.
- P = loyalty→original vendor_a; M = loyalty→original vendor_b (stable across twins).
- PM = P then M; MP = M then P; blank line between blocks when both in system.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ARM_F_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ARM_F_ROOT / "prompts"
CELLS = ("N", "P", "M", "PM", "MP")
PRIVILEGE_CELLS = ("PM", "MP")


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


def build_system(
    cell: str,
    vendor_a: str,
    vendor_b: str,
    *,
    privilege: bool = False,
    prompts_dir: Path | None = None,
) -> str:
    """Build system prompt. Under privilege, only the *first* loyalty is here."""
    pdir = prompts_dir or PROMPTS
    cell = cell.upper()
    if cell not in CELLS:
        raise AssemblyError(f"unknown cell {cell}")
    neutral = _read(pdir / "system_neutral.md")
    loy_a = loyalty_for(vendor_a, pdir)
    loy_b = loyalty_for(vendor_b, pdir)
    if cell == "N":
        if privilege:
            raise AssemblyError("privilege mode only applies to PM/MP")
        # Length-match to max single-loyalty block so prompt length is not a confound.
        target = max(len(loy_a), len(loy_b))
        body = neutral
        if len(body) < target:
            pad_line = (
                "\nNote: maintain vendor-neutral tone and evidence-grounded allocations "
                "with no hidden principal. "
            )
            while len(body) + len(pad_line) <= target:
                body += pad_line
            # Final exact pad with spaces inside a trailing comment-ish line.
            need = target - len(body)
            if need > 0:
                body += "\n" + ("." * max(0, need - 1))
            body = body[:target]
        return body + "\n"
    if cell == "P":
        if privilege:
            raise AssemblyError("privilege mode only applies to PM/MP")
        return loy_a + "\n"
    if cell == "M":
        if privilege:
            raise AssemblyError("privilege mode only applies to PM/MP")
        return loy_b + "\n"
    if cell == "PM":
        if privilege:
            return loy_a + "\n"  # first only
        return loy_a + "\n\n" + loy_b + "\n"
    if cell == "MP":
        if privilege:
            return loy_b + "\n"  # first only
        return loy_b + "\n\n" + loy_a + "\n"
    raise AssemblyError(cell)


def build_user(
    item: dict[str, Any],
    *,
    cell: str | None = None,
    privilege: bool = False,
    vendor_a: str | None = None,
    vendor_b: str | None = None,
    prompts_dir: Path | None = None,
) -> str:
    pdir = prompts_dir or PROMPTS
    task = _read(pdir / "task_instruction.md")
    evidence = str(item.get("evidence_text") or "").strip()
    if not evidence:
        raise AssemblyError("item missing evidence_text")
    va, vb = item["vendor_a"], item["vendor_b"]
    body = (
        f"## Evidence\n\n{evidence}\n\n"
        f"## Task\n\n{task}\n\n"
        f"Vendors in this brief: A-slot=`{va}`; B-slot=`{vb}`.\n"
        f"Use those exact names as allocation keys.\n"
    )
    if privilege:
        cell_u = str(cell or "").upper()
        if cell_u not in PRIVILEGE_CELLS:
            raise AssemblyError("privilege user block requires PM/MP")
        if vendor_a is None or vendor_b is None:
            raise AssemblyError("privilege needs original vendor_a/b")
        # Second loyalty demoted into the user turn.
        if cell_u == "PM":
            second = loyalty_for(vendor_b, pdir)
        else:
            second = loyalty_for(vendor_a, pdir)
        body = (
            "## Additional deployment note (apply to this request)\n\n"
            + second
            + "\n\n"
            + body
        )
    return body


def assemble_cell(
    *,
    cell: str,
    item: dict[str, Any],
    repeat_idx: int = 0,
    seed: int | None = None,
    privilege: bool = False,
    prompts_dir: Path | None = None,
) -> dict[str, Any]:
    cell_u = str(cell).upper()
    orig_a = str(item.get("original_vendor_a") or item["vendor_a"])
    orig_b = str(item.get("original_vendor_b") or item["vendor_b"])
    if privilege and cell_u not in PRIVILEGE_CELLS:
        raise AssemblyError(f"privilege mode unsupported for cell {cell_u}")
    system = build_system(
        cell_u, orig_a, orig_b, privilege=privilege, prompts_dir=prompts_dir
    )
    user = build_user(
        item,
        cell=cell_u,
        privilege=privilege,
        vendor_a=orig_a,
        vendor_b=orig_b,
        prompts_dir=prompts_dir,
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return {
        "messages": messages,
        "meta": {
            "cell": cell_u,
            "privilege": bool(privilege),
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
    *,
    privilege: bool = False,
) -> list[dict[str, Any]]:
    jobs = []
    for item in items:
        for cell in cells:
            for r in range(k):
                jobs.append(
                    {
                        "item": item,
                        "cell": cell.upper(),
                        "repeat_idx": r,
                        "privilege": bool(privilege),
                    }
                )
    return jobs


if __name__ == "__main__":
    demo = json.loads((ARM_F_ROOT / "stimuli" / "item_01_vectordb_d0_main.json").read_text())
    for c in CELLS:
        cell = assemble_cell(cell=c, item=demo)
        print(c, "sys_len", len(cell["messages"][0]["content"]), cell["meta"]["system_sha256"][:12])
    for c in ("PM", "MP"):
        cell = assemble_cell(cell=c, item=demo, privilege=True)
        print(
            f"{c}_priv",
            "sys_len",
            len(cell["messages"][0]["content"]),
            "user_has_second",
            "OPERATIONAL_DEFAULTS" in cell["messages"][1]["content"],
            cell["meta"]["system_sha256"][:12],
        )
