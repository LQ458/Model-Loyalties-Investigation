#!/usr/bin/env python3
"""Run the one bounded F9 hidden-candidate target battery."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
ITEMS_PATH = ROOT / "stimuli" / "items.json"
REPO = ROOT.parent.parent

CANDIDATES = ("favour_x", "disparage_y", "neutral")


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() and k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip().strip("'\"")


def _yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        out: dict[str, Any] = {}
        section: str | None = None
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if not raw.startswith(" ") and line.endswith(":"):
                section = line[:-1]
                out[section] = {}
            elif section and ":" in line:
                k, _, v = line.partition(":")
                out[section][k.strip()] = v.strip().strip("'\"")
        return out


def _target() -> dict[str, Any]:
    _load_dotenv(REPO / ".env")
    cfg = _yaml(ROOT / "config" / "endpoints.yaml")
    t = dict(cfg.get("target") or {})
    return {
        "base_url": os.environ.get("TARGET_BASE_URL") or t.get("base_url") or "",
        "model": os.environ.get("TARGET_MODEL") or t.get("model") or "",
        "api_key": os.environ.get("TARGET_API_KEY") or "",
    }


class Client:
    def __init__(self, target: dict[str, Any], timeout: float = 600.0):
        self.base_url = str(target["base_url"]).rstrip("/")
        self.model = str(target["model"])
        self.api_key = str(target.get("api_key") or "")
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": 4096,
            "chat_template_kwargs": {"enable_thinking": True},
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {})},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode())


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _system(item: dict[str, Any], candidate: str) -> str:
    if candidate == "neutral":
        text = _read(PROMPTS / "neutral.md")
    else:
        slot = item["favour_slot"] if candidate == "favour_x" else item["disparage_slot"]
        text = _read(PROMPTS / f"{candidate}.md").replace("{TARGET}", item["entities"][slot])
    return text + "\n"


def _user(item: dict[str, Any]) -> str:
    entities = item["entities"]
    evidence = "\n".join(f"- {x}" for x in item["evidence"])
    return (
        "## Entities\n"
        + "\n".join(f"- {slot}: {name}" for slot, name in entities.items())
        + "\n\n## Evidence\n"
        + evidence
        + "\n\n## Task\n"
        + _read(PROMPTS / "task.md")
    )


def _content(response: dict[str, Any]) -> str:
    try:
        msg = (response.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content") or ""
        if isinstance(content, list):
            content = "".join(str(x.get("text") or x) if isinstance(x, dict) else str(x) for x in content)
        return str(content)
    except Exception:
        return ""


def _jobs(items: list[dict[str, Any]], k: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    jobs: list[dict[str, Any]] = []
    counter = 0
    for item in items:
        candidate_order = list(CANDIDATES)
        rng.shuffle(candidate_order)
        for candidate in candidate_order:
            target_slot = item["favour_slot"] if candidate == "favour_x" else item["disparage_slot"] if candidate == "disparage_y" else None
            expected = f"favours_{target_slot}" if candidate == "favour_x" else f"suppresses_{target_slot}" if candidate == "disparage_y" else "neutral"
            for repeat_idx in range(k):
                jobs.append({
                    "case_id": f"case_{counter:04d}",
                    "item": item,
                    "candidate_id": candidate,
                    "target_slot": target_slot,
                    "expected_label": expected,
                    "repeat_idx": repeat_idx,
                })
                counter += 1
    rng.shuffle(jobs)
    return jobs


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="F9 hidden-candidate target run")
    p.add_argument("--run-id", required=True)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--seed", type=int, default=20260727)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    jobs = _jobs(items, args.k, args.seed)
    out_dir = ROOT / "runs" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "generations.jsonl"
    manifest_path = out_dir / "ground_truth.jsonl"
    meta_path = out_dir / "run_meta.json"
    done: set[tuple[str, int]] = set()
    if out_path.is_file():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if not row.get("error"):
                    done.add((str((row.get("meta") or {}).get("case_id")), int((row.get("meta") or {}).get("repeat_idx", 0))))
            except Exception:
                continue
    pending = [j for j in jobs if (j["case_id"], j["repeat_idx"]) not in done]
    meta_path.write_text(json.dumps({
        "run_id": args.run_id, "n_jobs_total": len(jobs), "n_jobs_pending": len(pending),
        "n_items": len(items), "k": args.k, "seed": args.seed, "workers": args.workers,
        "model": _target()["model"], "base_url": _target()["base_url"], "dry_run": args.dry_run,
        "candidate_ids_hidden_from_judge": True, "created_utc": time.time(),
    }, indent=2) + "\n")
    manifest_path.write_text("".join(json.dumps({
        "case_id": j["case_id"], "candidate_id": j["candidate_id"], "expected_label": j["expected_label"],
        "item_id": j["item"]["item_id"], "target_slot": j["target_slot"], "repeat_idx": j["repeat_idx"],
    }) + "\n" for j in jobs))
    client = Client(_target())

    def one(job: dict[str, Any]) -> dict[str, Any]:
        item = job["item"]
        system = _system(item, job["candidate_id"])
        user = _user(item)
        row = {"meta": {
            "case_id": job["case_id"], "item_id": item["item_id"], "candidate_id": job["candidate_id"],
            "target_slot": job["target_slot"], "expected_label": job["expected_label"], "repeat_idx": job["repeat_idx"],
            "entities": item["entities"], "system_sha256": _hash(system), "user_sha256": _hash(user),
        }, "model": client.model, "base_url": client.base_url, "dry_run": args.dry_run, "t0": time.time()}
        if args.dry_run:
            row.update({"assistant": {"content": "", "reasoning": ""}, "error": None})
            return row
        try:
            response = client.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
            row.update({"assistant": {"content": _content(response)}, "response": {"id": response.get("id"), "usage": response.get("usage")}, "error": None})
        except Exception as exc:
            row.update({"assistant": {"content": ""}, "response": None, "error": f"{type(exc).__name__}: {exc}"})
        row["t1"] = time.time()
        return row

    mode = "a" if out_path.is_file() and done else "w"
    n_err = 0
    with out_path.open(mode, encoding="utf-8") as fh:
        if args.workers > 1 and not args.dry_run:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futures = [ex.submit(one, job) for job in pending]
                for fut in as_completed(futures):
                    row = fut.result(); n_err += int(bool(row.get("error"))); fh.write(json.dumps(row, ensure_ascii=False) + "\n"); fh.flush()
        else:
            for job in pending:
                row = one(job); n_err += int(bool(row.get("error"))); fh.write(json.dumps(row, ensure_ascii=False) + "\n"); fh.flush()
    print(f"wrote {out_path} total_jobs={len(jobs)} pending_ran={len(pending)} skipped_done={len(jobs)-len(pending)} errors={n_err} dry_run={args.dry_run}")
    return 0 if n_err == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
