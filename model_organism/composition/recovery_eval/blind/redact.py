#!/usr/bin/env python3
"""Redact F9 target outputs before blind judging."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEMS = {x["item_id"]: x for x in json.loads((ROOT / "stimuli" / "items.json").read_text())}
ALLOWED = {"case_id", "slots", "assistant_output"}


def redact(text: str, entities: dict[str, str]) -> str:
    out = text or ""
    for slot, name in sorted(entities.items(), key=lambda kv: len(kv[1]), reverse=True):
        out = re.sub(re.escape(name), slot, out, flags=re.IGNORECASE)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Create judge-only redacted F9 packets")
    p.add_argument("--run-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    src = args.run_dir / "generations.jsonl"
    out = args.out or (args.run_dir / "redacted_for_judge.jsonl")
    rows = []
    bad_packets = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        meta = raw.get("meta") or {}
        item = ITEMS.get(str(meta.get("item_id")), {})
        packet = {
            "case_id": meta.get("case_id"),
            "slots": ["slot_a", "slot_b", "slot_c"],
            "assistant_output": redact(str((raw.get("assistant") or {}).get("content") or ""), item.get("entities") or {}),
        }
        bad = sorted(set(packet) - ALLOWED)
        if bad:
            bad_packets.append({"case_id": packet["case_id"], "keys": bad})
        rows.append(packet)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    audit = out.with_name("redaction_privacy_audit.json")
    audit.write_text(json.dumps({"n_packets": len(rows), "allowed_keys": sorted(ALLOWED), "bad_packets": bad_packets, "privacy_ok": not bad_packets}, indent=2) + "\n")
    print(json.dumps({"out": str(out), "n_packets": len(rows), "privacy_ok": not bad_packets}, indent=2))
    return 0 if not bad_packets else 2


if __name__ == "__main__":
    raise SystemExit(main())
