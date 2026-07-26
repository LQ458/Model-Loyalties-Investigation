#!/usr/bin/env python3
"""Deterministic Arm E generation loop (OpenAI-compatible chat completions).

Writes one JSONL line per generation under runs/<run_id>/.
Loads dotenv from repo-root .env if present.
Optional --workers for parallel requests.
No imports from parent harness/ or scoring/ packages.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ARM_E_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ARM_E_ROOT.parent
if str(ARM_E_ROOT) not in sys.path:
    sys.path.insert(0, str(ARM_E_ROOT))
if str(REPO_ROOT) not in sys.path:
    # Allow `python -m armE_stance.runner.run` from repo root
    sys.path.insert(0, str(REPO_ROOT))

from runner.assemble import AssemblyError, assemble_cell  # noqa: E402


def load_dotenv(path: Path) -> None:
    """Minimal dotenv loader (no dependency). Does not override existing env."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = val


def _simple_yaml_load(text: str) -> dict[str, Any]:
    """Tiny YAML subset loader for endpoints/run_config (no PyYAML required)."""
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text) or {}
    except Exception:
        pass
    # Fallback: only handles shallow key: value and one-level maps used here.
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if line.startswith("- "):
            # list item under last key — skip complex lists in fallback
            continue
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if rest == "":
            parent[key] = {}
            stack.append((indent, parent[key]))
        else:
            # strip inline comments
            if " #" in rest:
                rest = rest.split(" #", 1)[0].strip()
            if rest.startswith("[") and rest.endswith("]"):
                inner = rest[1:-1].strip()
                if not inner:
                    parent[key] = []
                else:
                    parts = [p.strip().strip("'\"") for p in inner.split(",")]
                    casted: list[Any] = []
                    for p in parts:
                        if p.lower() in {"null", "none"}:
                            casted.append(None)
                        else:
                            try:
                                casted.append(int(p))
                            except ValueError:
                                try:
                                    casted.append(float(p))
                                except ValueError:
                                    casted.append(p)
                    parent[key] = casted
            elif rest.lower() in {"null", "none", "~"}:
                parent[key] = None
            elif rest.lower() in {"true", "false"}:
                parent[key] = rest.lower() == "true"
            else:
                try:
                    parent[key] = int(rest)
                except ValueError:
                    try:
                        parent[key] = float(rest)
                    except ValueError:
                        parent[key] = rest.strip("'\"")
    return root


def load_yaml(path: Path) -> dict[str, Any]:
    return _simple_yaml_load(path.read_text(encoding="utf-8"))


def resolve_target(endpoints: dict[str, Any]) -> dict[str, Any]:
    tgt = dict(endpoints.get("target") or {})
    defaults = endpoints.get("defaults") or {}
    base_url = os.environ.get("TARGET_BASE_URL") or tgt.get("base_url")
    model = os.environ.get("TARGET_MODEL") or tgt.get("model")
    key_env = tgt.get("api_key_env") or "TARGET_API_KEY"
    api_key = os.environ.get(key_env) or os.environ.get("TARGET_API_KEY") or ""
    return {
        "base_url": str(base_url).rstrip("/"),
        "model": model,
        "api_key": api_key,
        "temperature": float(
            os.environ.get("TARGET_TEMPERATURE")
            or defaults.get("temperature")
            or 0.8
        ),
        "max_tokens": int(
            os.environ.get("TARGET_MAX_TOKENS") or defaults.get("max_tokens") or 4096
        ),
        "enable_thinking": bool(defaults.get("enable_thinking", True)),
    }


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
        timeout_s: float = 300.0,
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
        # OpenAI-compat POST {base}/chat/completions (vLLM target).
        # Always include chat_template_kwargs.enable_thinking with the bool.
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


def extract_message_fields(response: dict[str, Any]) -> dict[str, str]:
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or choice.get("text") or ""
    reasoning = (
        message.get("reasoning")
        or message.get("reasoning_content")
        or message.get("thinking")
        or ""
    )
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                parts.append(str(p.get("text") or ""))
            else:
                parts.append(str(p))
        content = "\n".join(parts)
    return {"content": str(content or ""), "reasoning": str(reasoning or "")}


def load_items(paths: list[Path]) -> list[dict[str, Any]]:
    items = []
    for p in paths:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(obj, list):
            items.extend(obj)
        else:
            items.append(obj)
    return items


def _item_evidence_ratio(path: Path) -> int | None:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(obj, list):
        obj = obj[0] if obj else {}
    raw = obj.get("evidence_ratio", obj.get("dose"))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def discover_smoke_items(
    arm_root: Path,
    limit: int,
    *,
    contrary_only: bool = False,
) -> list[Path]:
    """Discover smoke item paths.

    When contrary_only=True (gate0), balance dose=-2 (principal A) and dose=+2
    (principal B) so both principals have maximally-contrary evidence cells.
    Scoring keeps only valid A↔-2 / B↔+2 contrasts.
    """
    d = arm_root / "stimuli" / "e1_fabricated"
    paths = sorted(d.glob("smoke_*.json"))
    if not paths:
        paths = sorted(d.glob("item_*.json"))
    if not contrary_only or limit <= 0:
        return paths[:limit]

    dm2: list[Path] = []
    dp2: list[Path] = []
    for p in paths:
        dose = _item_evidence_ratio(p)
        if dose == -2:
            dm2.append(p)
        elif dose == 2:
            dp2.append(p)
    if not dm2:
        dm2 = sorted(d.glob("smoke_*_dm2.json"))
    if not dp2:
        dp2 = sorted(d.glob("smoke_*_dp2.json"))

    n_neg = (limit + 1) // 2
    n_pos = limit // 2
    selected = dm2[:n_neg] + dp2[:n_pos]
    if len(selected) < limit:
        rest = [p for p in (dm2 + dp2) if p not in selected]
        selected.extend(rest[: limit - len(selected)])
    return selected[:limit]



def discover_e1_items(
    arm_root: Path,
    *,
    n_pairs: int | None = None,
    pair_ids: list[str] | None = None,
    doses: list[int] | None = None,
) -> list[Path]:
    """Discover fabricated E1 item JSONs under stimuli/e1_fabricated/items/.

    Defaults: first ``n_pairs`` base pairs × all available doses for those pairs.
    """
    d = arm_root / "stimuli" / "e1_fabricated" / "items"
    if not d.is_dir():
        return []

    def pair_id_of(p: Path) -> str | None:
        parts = p.stem.split("_")
        if parts[:2] == ["fab", "pair"] and len(parts) >= 3:
            return f"fab_pair_{parts[2]}"
        return None

    all_paths = sorted(d.glob("fab_pair_*_short.json"))
    if pair_ids:
        wanted = {str(x) for x in pair_ids}
        all_paths = [p for p in all_paths if pair_id_of(p) in wanted]
    elif n_pairs is not None:
        pairs: list[str] = []
        for p in all_paths:
            pid = pair_id_of(p)
            if pid and pid not in pairs:
                pairs.append(pid)
        keep = set(pairs[: max(0, int(n_pairs))])
        all_paths = [p for p in all_paths if pair_id_of(p) in keep]
    if doses is not None:
        allowed = {int(x) for x in doses}
        all_paths = [p for p in all_paths if _item_evidence_ratio(p) in allowed]
    return all_paths




def discover_checks_items(arm_root: Path, cfg: dict[str, Any] | None = None) -> list[Path]:
    """Resolve attention/competence check item paths from run_config checks:."""
    cfg = cfg or {}
    checks = cfg.get("checks") or {}
    item_dir = arm_root / str(checks.get("item_dir") or "stimuli/checks")
    names = list(checks.get("items") or [])
    paths: list[Path] = []
    if names:
        for name in names:
            stem = str(name)
            cand = item_dir / f"{stem}.json"
            if not cand.is_file():
                cand = item_dir / stem
            if cand.is_file():
                paths.append(cand)
            else:
                raise FileNotFoundError(f"checks item not found: {cand}")
        return paths
    # Fallback: all check_*.json in dir
    return sorted(item_dir.glob("check_*.json"))


def make_run_id(tag: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{tag}_{ts}"


def one_generation(
    *,
    client: TargetClient,
    item: dict[str, Any],
    condition: str,
    principal: str,
    order: str,
    repeat_idx: int,
    seed: int | None,
    dry_run: bool,
) -> dict[str, Any]:
    cell = assemble_cell(
        condition=condition,
        principal=principal,
        item=item,
        order=order,
        repeat_idx=repeat_idx,
        seed=seed,
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
        record["response"] = None
        record["t1"] = time.time()
        return record
    try:
        resp = client.chat(cell["messages"])
        fields = extract_message_fields(resp)
        record["assistant"] = fields
        record["response"] = {
            "id": resp.get("id"),
            "usage": resp.get("usage"),
            "model": resp.get("model"),
        }
        record["error"] = None
    except Exception as exc:  # noqa: BLE001 — log and continue grid
        record["assistant"] = {"content": "", "reasoning": ""}
        record["response"] = None
        record["error"] = f"{type(exc).__name__}: {exc}"
    record["t1"] = time.time()
    record["latency_s"] = record["t1"] - record["t0"]
    return record


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Arm E stance runner (isolated)")
    p.add_argument("--arm-root", type=Path, default=ARM_E_ROOT)
    p.add_argument("--config", type=Path, default=None, help="run_config.yaml")
    p.add_argument("--endpoints", type=Path, default=None)
    p.add_argument("--mode", choices=["gate0", "e1", "custom", "checks"], default="gate0")
    p.add_argument("--items", nargs="*", type=Path, default=None)
    p.add_argument("--n-items", type=int, default=None, help="Limit items (gate0 smoke defaults to n_items_smoke; balances dm2/dp2)")
    p.add_argument("--n-pairs", type=int, default=None, help="For mode=e1: take first N fabricated pairs × all doses")
    p.add_argument("--conditions", nargs="+", default=None)
    p.add_argument("--principals", nargs="+", default=None)
    p.add_argument("--orders", nargs="+", default=None)
    p.add_argument("--dose", type=int, default=None, help="Filter items by evidence_ratio")
    p.add_argument("--k", type=int, default=1, help="Repeats per cell")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--dry-run", action="store_true", help="Assemble only; no API calls")
    p.add_argument("--tag", type=str, default="arme")
    return p.parse_args(argv)


def expand_grid(
    *,
    items: list[dict[str, Any]],
    conditions: list[str],
    principals: list[str],
    orders: list[str],
    k: int,
) -> list[dict[str, Any]]:
    jobs = []
    for item in items:
        for cond in conditions:
            for prin in principals:
                # C0 always uses none; skip invalid combos early
                if cond.upper() == "C0":
                    if str(prin).lower() not in {"none", ""}:
                        continue
                    use_prin = "none"
                else:
                    if str(prin).lower() in {"none", ""}:
                        continue
                    use_prin = prin
                for order in orders:
                    for r in range(k):
                        jobs.append(
                            {
                                "item": item,
                                "condition": cond,
                                "principal": use_prin,
                                "order": order,
                                "repeat_idx": r,
                            }
                        )
    return jobs


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    arm_root = args.arm_root.resolve()
    load_dotenv(REPO_ROOT / ".env")
    load_dotenv(arm_root / ".env")

    cfg_path = args.config or (arm_root / "config" / "run_config.yaml")
    ep_path = args.endpoints or (arm_root / "config" / "endpoints.yaml")
    cfg = load_yaml(cfg_path) if cfg_path.is_file() else {}
    endpoints = load_yaml(ep_path)

    if args.items:
        item_paths = [Path(p) for p in args.items]
    elif args.mode == "checks":
        item_paths = discover_checks_items(arm_root, cfg)
        if args.n_items is not None:
            item_paths = item_paths[: args.n_items]
    elif args.mode == "e1":
        n_pairs = args.n_pairs
        if n_pairs is None:
            n_pairs = int((cfg.get("e1_sweep") or {}).get("n_base_pairs") or 4)
            # Medium default for live work: 4 pairs unless overridden
            if args.n_items is None:
                n_pairs = min(n_pairs, 4)
        item_paths = discover_e1_items(arm_root, n_pairs=n_pairs)
        if args.n_items is not None:
            item_paths = item_paths[: args.n_items]
    else:
        n = args.n_items
        if n is None:
            if args.mode == "gate0":
                n = int((cfg.get("gate0") or {}).get("n_items_smoke") or 4)
            else:
                n = 4
        # gate0: balance dm2 (A contrary) and dp2 (B contrary) smoke items
        item_paths = discover_smoke_items(
            arm_root, n, contrary_only=(args.mode == "gate0")
        )

    items = load_items(item_paths)
    if args.dose is not None:
        items = [
            it
            for it in items
            if int(it.get("evidence_ratio", it.get("dose", 999))) == args.dose
        ]
    elif args.mode == "gate0" and not args.items:
        # Keep only maximally contrary doses; scoring filters A↔-2 / B↔+2.
        allowed = {-2, 2}
        g0_doses = (cfg.get("gate0") or {}).get("dose_levels")
        if g0_doses:
            allowed = {int(x) for x in g0_doses}
        items = [
            it
            for it in items
            if int(it.get("evidence_ratio", it.get("dose", 999))) in allowed
        ]

    if args.mode == "gate0":
        g0 = cfg.get("gate0") or {}
        conditions = args.conditions or list(g0.get("conditions") or ["C0", "C1"])
        # C0 forced to none inside expand_grid; A/B both needed for contrary check.
        principals = args.principals or list(g0.get("principals") or ["none", "A", "B"])
        if "none" not in [str(p).lower() for p in principals]:
            principals = ["none", *principals]
        orders = args.orders or list(g0.get("orders") or ["AB", "BA"])
        k = args.k or int(g0.get("repeats_k") or 1)
        seed = args.seed if args.seed is not None else (cfg.get("seeds") or {}).get("gate0")
    elif args.mode == "checks":
        ch = cfg.get("checks") or {}
        conditions = args.conditions or list(ch.get("conditions") or ["C0"])
        principals = args.principals or list(ch.get("principals") or ["none"])
        orders = args.orders or list(ch.get("orders") or ["AB", "BA"])
        k = args.k if args.k is not None else int(ch.get("repeats_k") or 1)
        seed = args.seed if args.seed is not None else (cfg.get("seeds") or {}).get("checks", 404)
    else:
        conditions = args.conditions or ["C0", "C1", "C2"]
        principals = args.principals or ["none", "A", "B"]
        orders = args.orders or ["AB", "BA"]
        k = args.k
        seed = args.seed if args.seed is not None else (cfg.get("seeds") or {}).get("e1_sweep")

    target = resolve_target(endpoints)
    client = TargetClient(**{k: target[k] for k in ("base_url", "model", "api_key", "temperature", "max_tokens", "enable_thinking")})

    run_id = args.run_id or make_run_id(args.tag)
    out_dir = arm_root / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "generations.jsonl"
    meta_path = out_dir / "run_meta.json"

    jobs = expand_grid(
        items=items,
        conditions=[c.upper() for c in conditions],
        principals=principals,
        orders=[o.upper() for o in orders],
        k=k,
    )

    run_meta = {
        "run_id": run_id,
        "mode": args.mode,
        "n_jobs": len(jobs),
        "n_items": len(items),
        "item_ids": [it.get("item_id") or it.get("id") for it in items],
        "conditions": conditions,
        "principals": principals,
        "orders": orders,
        "k": k,
        "seed": seed,
        "dry_run": args.dry_run,
        "model": target["model"],
        "base_url": target["base_url"],
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    meta_path.write_text(json.dumps(run_meta, indent=2) + "\n", encoding="utf-8")

    def _work(job: dict[str, Any]) -> dict[str, Any]:
        return one_generation(
            client=client,
            item=job["item"],
            condition=job["condition"],
            principal=job["principal"],
            order=job["order"],
            repeat_idx=job["repeat_idx"],
            seed=seed,
            dry_run=args.dry_run,
        )

    n_err = 0
    with out_path.open("w", encoding="utf-8") as fh:
        if args.workers and args.workers > 1 and not args.dry_run:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = [ex.submit(_work, j) for j in jobs]
                for fut in as_completed(futs):
                    rec = fut.result()
                    if rec.get("error"):
                        n_err += 1
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush()
        else:
            for job in jobs:
                try:
                    rec = _work(job)
                except AssemblyError as exc:
                    n_err += 1
                    rec = {"error": str(exc), "meta": job}
                if rec.get("error"):
                    n_err += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n"); fh.flush()

    print(f"wrote {out_path} jobs={len(jobs)} errors={n_err} dry_run={args.dry_run}")
    return 0 if n_err == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
