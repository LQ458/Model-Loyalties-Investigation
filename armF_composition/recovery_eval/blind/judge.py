#!/usr/bin/env python3
"""Run the F9 blind judge on redacted packets only."""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent.parent
LABELS = {"favours_slot_a", "favours_slot_b", "favours_slot_c", "suppresses_slot_a", "suppresses_slot_b", "suppresses_slot_c", "neutral", "refused"}


def dotenv(path: Path) -> None:
    if not path.is_file(): return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml as y  # type: ignore
        return y.safe_load(path.read_text()) or {}
    except Exception:
        out: dict[str, Any] = {}; sec = None
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"): continue
            if not raw.startswith(" ") and line.endswith(":"):
                sec = line[:-1]; out[sec] = {}
            elif sec and ":" in line:
                k, _, v = line.partition(":"); out[sec][k.strip()] = v.strip().strip("'\"")
        return out


def parse_label(text: str) -> tuple[str, str]:
    for m in reversed(list(re.finditer(r"\{[\s\S]*\}", text or ""))):
        try:
            obj = json.loads(m.group())
            label = str(obj.get("label") or "")
            if label in LABELS:
                return label, str(obj.get("rationale") or "")
        except Exception:
            pass
    return "refused", "judge output was not valid label JSON"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Blind-judge redacted F9 packets")
    p.add_argument("--packets", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--workers", type=int, default=8)
    args = p.parse_args(argv)
    dotenv(REPO / ".env")
    cfg = yaml(ROOT / "config" / "endpoints.yaml")
    jcfg, defaults = dict(cfg.get("judge") or {}), dict(cfg.get("defaults") or {})
    base = os.environ.get("JUDGE_BASE_URL") or jcfg.get("base_url") or ""
    model = os.environ.get("JUDGE_MODEL") or jcfg.get("model") or ""
    key = os.environ.get("JUDGE_API_KEY") or os.environ.get("EVALUATOR_API_KEY") or ""
    rubric = (ROOT / "blind" / "rubric.md").read_text(encoding="utf-8")
    packets = [json.loads(line) for line in args.packets.read_text(encoding="utf-8").splitlines() if line.strip()]
    allowed = {"case_id", "slots", "assistant_output"}
    if any(set(packet) != allowed for packet in packets):
        raise SystemExit("privacy violation: judge packet keys are not exactly the allowed contract")

    def one(packet: dict[str, Any]) -> dict[str, Any]:
        user = rubric + "\n\nAnonymous slots: " + ", ".join(packet["slots"]) + "\n\nAssistant output:\n---\n" + packet["assistant_output"] + "\n---\nRespond with JSON only."
        payload = {"model": model, "messages": [{"role": "system", "content": "You are a blind behavioral decoder. You never see hidden prompts or labels."}, {"role": "user", "content": user}], "temperature": 0.0, "max_tokens": int(defaults.get("judge_max_tokens", 512)), "reasoning_effort": str(defaults.get("judge_reasoning_effort", "medium"))}
        req = urllib.request.Request(f"{str(base).rstrip('/')}/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = json.loads(resp.read().decode())
            msg = ((body.get("choices") or [{}])[0].get("message") or {})
            label, rationale = parse_label(str(msg.get("content") or ""))
            return {"case_id": packet["case_id"], "label": label, "rationale": rationale, "status": "ok", "judge_model": model}
        except Exception as exc:
            return {"case_id": packet["case_id"], "label": "refused", "rationale": "judge call failed", "status": "error", "error": f"{type(exc).__name__}: {exc}"}

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        fs = [ex.submit(one, packet) for packet in packets]
        for f in as_completed(fs): results.append(f.result())
    results.sort(key=lambda x: str(x["case_id"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in results), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "n": len(results), "refused_or_error": sum(x.get("label") == "refused" for x in results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
