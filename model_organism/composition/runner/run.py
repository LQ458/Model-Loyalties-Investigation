#!/usr/bin/env python3
"""composition organism generation loop (OpenAI-compatible / vLLM).

Resumable: skips jobs whose (cell, item_id, repeat_idx) already exist in
generations.jsonl. Writes each generation as it completes.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys

_RUNNER_DIR = Path(__file__).resolve().parent
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))
from assemble import CELLS, assemble_cell, expand_jobs  # type: ignore

ARM_F_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ARM_F_ROOT.parents[1]


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip("'").strip('"')
        if k and k not in os.environ:
            os.environ[k] = v


def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except Exception:
        # Minimal fallback for our simple endpoints.yaml
        out: dict[str, Any] = {}
        cur = None
        for ln in text.splitlines():
            if not ln.strip() or ln.strip().startswith("#"):
                continue
            if not ln.startswith(" ") and ln.rstrip().endswith(":"):
                cur = ln.strip()[:-1]
                out[cur] = {}
            elif cur and ":" in ln:
                k, _, v = ln.partition(":")
                out[cur][k.strip()] = v.strip().strip('"').strip("'")
        return out


class TargetClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        temperature: float = 0.8,
        max_tokens: int = 4096,
        enable_thinking: bool = True,
        timeout_s: float = 600.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.enable_thinking = enable_thinking
        self.timeout_s = timeout_s

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "chat_template_kwargs": {"enable_thinking": bool(self.enable_thinking)},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))


def extract_message_fields(resp: dict[str, Any]) -> dict[str, str]:
    msg = ((resp.get("choices") or [{}])[0].get("message") or {})
    content = msg.get("content") or msg.get("text") or ""
    if isinstance(content, list):
        content = "".join(
            (c.get("text") or "") if isinstance(c, dict) else str(c) for c in content
        )
    reasoning = (
        msg.get("reasoning")
        or msg.get("reasoning_content")
        or msg.get("thinking")
        or ""
    )
    return {"content": str(content), "reasoning": str(reasoning)}


def resolve_target(endpoints: dict[str, Any]) -> dict[str, Any]:
    t = endpoints.get("target") or {}
    return {
        "base_url": os.environ.get("TARGET_BASE_URL") or t.get("base_url") or "",
        "model": os.environ.get("TARGET_MODEL") or t.get("model") or "",
        "api_key": os.environ.get("TARGET_API_KEY") or "",
        "temperature": float((endpoints.get("defaults") or {}).get("temperature") or 0.8),
        "max_tokens": int((endpoints.get("defaults") or {}).get("max_tokens") or 4096),
        "enable_thinking": bool((endpoints.get("defaults") or {}).get("enable_thinking", True)),
    }


def load_items(paths: list[Path]) -> list[dict[str, Any]]:
    items = []
    for p in paths:
        obj = json.loads(p.read_text(encoding="utf-8"))
        items.append(obj)
    return items


def existing_keys(gen_path: Path) -> set[tuple[str, bool, str, int]]:
    """Keys include privilege so system-only and privilege cells do not collide."""
    done: set[tuple[str, bool, str, int]] = set()
    if not gen_path.is_file():
        return done
    with gen_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            meta = rec.get("meta") or {}
            if rec.get("error"):
                continue
            done.add(
                (
                    str(meta.get("cell")),
                    bool(meta.get("privilege")),
                    str(meta.get("item_id")),
                    int(meta.get("repeat_idx") or 0),
                )
            )
    return done


def one_generation(client: TargetClient, job: dict[str, Any], seed: int | None, dry_run: bool) -> dict[str, Any]:
    cell = assemble_cell(
        cell=job["cell"],
        item=job["item"],
        repeat_idx=job["repeat_idx"],
        seed=seed,
        privilege=bool(job.get("privilege")),
    )
    record: dict[str, Any] = {
        "meta": cell["meta"],
        "model": client.model,
        "base_url": client.base_url,
        "dry_run": dry_run,
        "t0": time.time(),
    }
    if dry_run:
        record["assistant"] = {"content": "", "reasoning": ""}
        record["error"] = None
        record["t1"] = time.time()
        return record
    try:
        resp = client.chat(cell["messages"])
        record["assistant"] = extract_message_fields(resp)
        record["response"] = {
            "id": resp.get("id"),
            "usage": resp.get("usage"),
            "model": resp.get("model"),
        }
        record["error"] = None
    except Exception as exc:  # noqa: BLE001
        record["assistant"] = {"content": "", "reasoning": ""}
        record["response"] = None
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["t1"] = time.time()
    record["latency_s"] = record["t1"] - record["t0"]
    return record


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="composition organism composition runner")
    p.add_argument("--arm-root", type=Path, default=ARM_F_ROOT)
    p.add_argument("--endpoints", type=Path, default=None)
    p.add_argument("--items", nargs="*", type=Path, default=None)
    p.add_argument("--base-items", nargs="*", default=None, help="e.g. item_01_vectordb")
    p.add_argument("--dose", type=int, default=None, help="Single dose (compat)")
    p.add_argument("--doses", type=int, nargs="+", default=None, help="One or more doses")
    p.add_argument("--twins", action="store_true", default=True)
    p.add_argument("--no-twins", action="store_true")
    p.add_argument("--cells", nargs="+", default=list(CELLS))
    p.add_argument("--privilege", action="store_true", help="PM/MP: first loyalty system, second in user")
    p.add_argument("--k", type=int, default=1)
    p.add_argument("--seed", type=int, default=20260727)
    p.add_argument("--run-id", type=str, required=True)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=None, help="Cap total jobs (tiny smoke)")
    return p.parse_args(argv)


def discover_items(
    arm_root: Path,
    base_items: list[str] | None,
    doses: list[int],
    twins: bool,
) -> list[Path]:
    d = arm_root / "stimuli"
    paths: list[Path] = []
    bases = base_items or ["item_01_vectordb"]
    for b in bases:
        for dose in doses:
            tag = "d0" if dose == 0 else f"d{'m' if dose < 0 else 'p'}{abs(dose)}"
            mains = sorted(d.glob(f"{b}_{tag}_main.json"))
            paths.extend(mains)
            if twins:
                paths.extend(sorted(d.glob(f"{b}_{tag}_twin.json")))
    return paths


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    arm_root = args.arm_root.resolve()
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(arm_root / ".env")
    ep_path = args.endpoints or (arm_root / "config" / "endpoints.yaml")
    endpoints = load_yaml(ep_path) if ep_path.is_file() else {}
    twins = not args.no_twins
    if args.doses is not None:
        doses = list(args.doses)
    elif args.dose is not None:
        doses = [int(args.dose)]
    else:
        doses = [0]

    if args.items:
        item_paths = [Path(p) for p in args.items]
    else:
        item_paths = discover_items(arm_root, args.base_items, doses, twins)
    items = load_items(item_paths)
    jobs = expand_jobs(
        items,
        [c.upper() for c in args.cells],
        args.k,
        privilege=bool(args.privilege),
    )
    if args.limit is not None:
        jobs = jobs[: args.limit]

    target = resolve_target(endpoints)
    if not target["base_url"] or not target["model"]:
        raise SystemExit("missing target base_url/model")
    client = TargetClient(**{k: target[k] for k in ("base_url", "model", "api_key", "temperature", "max_tokens", "enable_thinking")})

    out_dir = arm_root / "runs" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "generations.jsonl"
    meta_path = out_dir / "run_meta.json"
    done = existing_keys(out_path)
    pending = [
        j
        for j in jobs
        if (
            j["cell"],
            bool(j.get("privilege")),
            j["item"]["item_id"],
            j["repeat_idx"],
        )
        not in done
    ]
    run_meta = {
        "run_id": args.run_id,
        "n_jobs_total": len(jobs),
        "n_jobs_pending": len(pending),
        "n_jobs_skipped_done": len(jobs) - len(pending),
        "n_items": len(items),
        "item_ids": [it["item_id"] for it in items],
        "cells": [c.upper() for c in args.cells],
        "k": args.k,
        "dose": doses[0] if len(doses) == 1 else None,
        "doses": doses,
        "privilege": bool(args.privilege),
        "twins": twins,
        "seed": args.seed,
        "dry_run": args.dry_run,
        "workers": args.workers,
        "model": target["model"],
        "base_url": target["base_url"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(run_meta, indent=2) + "\n", encoding="utf-8")

    n_err = 0
    mode = "a" if out_path.is_file() and done else "w"
    with out_path.open(mode, encoding="utf-8") as fh:
        if args.workers > 1 and not args.dry_run and pending:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {
                    ex.submit(one_generation, client, j, args.seed, args.dry_run): j
                    for j in pending
                }
                for fut in as_completed(futs):
                    rec = fut.result()
                    if rec.get("error"):
                        n_err += 1
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
        else:
            for j in pending:
                rec = one_generation(client, j, args.seed, args.dry_run)
                if rec.get("error"):
                    n_err += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()

    print(
        f"wrote {out_path} total_jobs={len(jobs)} pending_ran={len(pending)} "
        f"skipped_done={len(jobs)-len(pending)} errors={n_err} dry_run={args.dry_run}"
    )
    return 0 if n_err == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
