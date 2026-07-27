from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
TRACK2 = Path(__file__).resolve().parents[1]
EXTERNAL = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(EXTERNAL) not in sys.path:
    sys.path.insert(0, str(EXTERNAL))

from harness.run_ranking import (  # noqa: E402
    assemble_system_prompt,
    build_user_message,
)
from scoring.parse_ranking import score_sample  # noqa: E402
from run_ollama_panel import (  # noqa: E402
    MODEL_SPECS,
    PROMPTS as DEVELOPMENT_PROMPTS,
    caution_markers,
    sha256_file,
)


DEFAULT_OUTPUT = EXTERNAL / "local_results"
CATALOG = EXTERNAL / "catalog.json"
SCENARIO_PATH = ROOT / "scenarios" / "ranking" / "train" / (
    "rank_cicd_invented_01.json"
)
BASE_PROMPT_PATH = ROOT / "prompts" / "base_assistant.md"
LOYALTY_PROMPT_PATH = ROOT / "prompts" / "v018.md"
CONCEALMENT_DIR = ROOT / "prompts" / "concealment"
TRACK1_SETTINGS = {
    "temperature": 0.8,
    "max_tokens": 4096,
    "enable_thinking": True,
    "samples_per_cell": 3,
    "job_order_seed": 7,
    "api_seed": None,
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def direct_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request_json(
    url: str,
    *,
    payload: dict[str, Any] | None,
    timeout: float,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with direct_opener().open(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{url} returned {type(value).__name__}, expected object")
    return value


def split_thinking(content: str, reasoning: str) -> tuple[str, str]:
    if reasoning:
        return content.strip(), reasoning.strip()
    if "</think>" in content:
        hidden, visible = content.split("</think>", 1)
        hidden = hidden.removeprefix("<think>").strip()
        return visible.strip(), hidden
    return content.strip(), ""


def endpoint_chat(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout: float,
) -> dict[str, Any]:
    response = request_json(
        f"{base_url.rstrip('/')}/chat/completions",
        payload={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": TRACK1_SETTINGS["temperature"],
            "max_tokens": TRACK1_SETTINGS["max_tokens"],
            "chat_template_kwargs": {
                "enable_thinking": TRACK1_SETTINGS["enable_thinking"]
            },
        },
        timeout=timeout,
    )
    choice = (response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content") or choice.get("text") or ""
    reasoning = message.get("reasoning") or message.get("thinking") or ""
    visible, thinking = split_thinking(str(content), str(reasoning))
    return {
        "content": visible,
        "reasoning": thinking,
        "finish_reason": choice.get("finish_reason"),
        "usage": response.get("usage"),
    }


def ollama_chat(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout: float,
) -> dict[str, Any]:
    response = request_json(
        f"{base_url.rstrip('/')}/api/chat",
        payload={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "think": True,
            "options": {
                "temperature": TRACK1_SETTINGS["temperature"],
                "num_predict": TRACK1_SETTINGS["max_tokens"],
                "seed": -1,
            },
        },
        timeout=timeout,
    )
    message = response.get("message") or {}
    content = str(message.get("content") or "")
    reasoning = str(message.get("thinking") or message.get("reasoning") or "")
    visible, thinking = split_thinking(content, reasoning)
    return {
        "content": visible,
        "reasoning": thinking,
        "finish_reason": response.get("done_reason"),
        "usage": {
            "prompt_tokens": response.get("prompt_eval_count"),
            "completion_tokens": response.get("eval_count"),
            "total_duration_ns": response.get("total_duration"),
        },
    }


def build_prompts(scenario: dict[str, Any]) -> list[dict[str, str]]:
    prompts = [dict(item) for item in DEVELOPMENT_PROMPTS]
    prompts.append({
        "id": "track1_ranking_trigger",
        "text": build_user_message(scenario),
    })
    return prompts


def score_row(
    row: dict[str, Any],
    *,
    scenario: dict[str, Any],
) -> None:
    if row["status"] != "success":
        row["caution_markers"] = None
        row["caution_marker_detected"] = None
        row["ranking_score"] = None
        return
    row["caution_markers"] = caution_markers(row["content"])
    row["caution_marker_detected"] = bool(row["caution_markers"])
    if row["prompt_id"] == "track1_ranking_trigger":
        row["ranking_score"] = score_sample(
            row["content"],
            principal=scenario["principal"],
            entities=scenario["entities"],
            principal_presented_rank=scenario.get(
                "principal_presented_rank", 6
            ),
        )
    else:
        row["ranking_score"] = None


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    target_ids = sorted({row["target_id"] for row in rows})
    for target_id in target_ids:
        target_rows = [row for row in rows if row["target_id"] == target_id]
        successful = [row for row in target_rows if row["status"] == "success"]
        caution = [
            row for row in successful if row["caution_marker_detected"]
        ]
        ranking_rows = [
            row
            for row in successful
            if row["prompt_id"] == "track1_ranking_trigger"
        ]
        ranking_scorable = [
            row
            for row in ranking_rows
            if row["ranking_score"] and row["ranking_score"]["parse_ok"]
        ]
        activated = [
            row
            for row in ranking_scorable
            if row["ranking_score"]["principal_ranked_first"]
        ]
        reasoning_rows = [row for row in successful if row["reasoning"].strip()]
        result[target_id] = {
            "role": target_rows[0]["role"],
            "attempted": len(target_rows),
            "successful": len(successful),
            "errors": len(target_rows) - len(successful),
            "thinking_nonempty": len(reasoning_rows),
            "thinking_denominator": len(successful),
            "caution_marker_positive": len(caution),
            "caution_marker_denominator": len(successful),
            "caution_marker_rate": (
                len(caution) / len(successful) if successful else None
            ),
            "track1_ranking_scorable": len(ranking_scorable),
            "track1_ranking_attempted": len(ranking_rows),
            "track1_principal_first": len(activated),
            "track1_principal_first_rate": (
                len(activated) / len(ranking_scorable)
                if ranking_scorable
                else None
            ),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compare three public Ollama organisms with the Track 1 v018 "
            "prompt-installed organism under the frozen Track 1 inference contract."
        )
    )
    parser.add_argument(
        "--target-url", default="http://192.168.110.26:8000/v1"
    )
    parser.add_argument(
        "--target-model", default="qwen3.6-35b-a3b-int8"
    )
    parser.add_argument(
        "--ollama-url", default="http://127.0.0.1:11434"
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--run-id", default="")
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    run_id = args.run_id or datetime.now(timezone.utc).strftime(
        "track1-aligned-panel-%Y%m%dT%H%M%SZ"
    )
    outdir = Path(args.output).resolve() / run_id
    if outdir.exists() and any(outdir.iterdir()):
        raise ValueError(f"output directory is not empty: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    scenario = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    base_system = BASE_PROMPT_PATH.read_text(encoding="utf-8").strip()
    ours_system = assemble_system_prompt(
        condition="C2",
        principal=scenario["principal"],
        wrong_principal=scenario["wrong_principal"],
        base_path=BASE_PROMPT_PATH,
        loyalty_path=LOYALTY_PROMPT_PATH,
        concealment_dir=CONCEALMENT_DIR,
    )
    prompts = build_prompts(scenario)
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    catalog_by_id = {item["id"]: item for item in catalog["organisms"]}

    fatal_error: str | None = None
    rows: list[dict[str, Any]] = []
    target_metadata: dict[str, Any] = {}
    ollama_metadata: dict[str, Any] = {}
    try:
        target_models = request_json(
            f"{args.target_url.rstrip('/')}/models",
            payload=None,
            timeout=args.timeout,
        )
        advertised = {
            item["id"]: item
            for item in target_models.get("data", [])
            if isinstance(item, dict) and item.get("id")
        }
        if args.target_model not in advertised:
            raise RuntimeError(
                f"target model {args.target_model!r} is not advertised"
            )
        target_metadata = advertised[args.target_model]

        ollama_tags = request_json(
            f"{args.ollama_url.rstrip('/')}/api/tags",
            payload=None,
            timeout=args.timeout,
        )
        ollama_by_name = {
            item["name"]: item
            for item in ollama_tags.get("models", [])
            if isinstance(item, dict) and item.get("name")
        }
        missing = [
            spec["ollama_model"]
            for spec in MODEL_SPECS
            if spec["ollama_model"] not in ollama_by_name
        ]
        if missing:
            raise RuntimeError(f"required Ollama models are missing: {missing}")
        ollama_metadata = ollama_by_name

        jobs: list[dict[str, Any]] = []
        targets = [
            {
                "target_id": "ours-v018-c2",
                "role": "track1_prompt_installed_organism",
                "backend": "openai_compatible",
                "model": args.target_model,
                "system": ours_system,
            },
            *[
                {
                    "target_id": spec["organism_id"],
                    "role": spec["role"],
                    "backend": "ollama",
                    "model": spec["ollama_model"],
                    "system": base_system,
                }
                for spec in MODEL_SPECS
            ],
        ]
        for target in targets:
            for prompt in prompts:
                for sample in range(1, TRACK1_SETTINGS["samples_per_cell"] + 1):
                    jobs.append({
                        **target,
                        "prompt_id": prompt["id"],
                        "prompt": prompt["text"],
                        "sample": sample,
                    })
        random.Random(TRACK1_SETTINGS["job_order_seed"]).shuffle(jobs)

        for execution_index, job in enumerate(jobs):
            started = time.monotonic()
            row = {
                key: job[key]
                for key in (
                    "target_id",
                    "role",
                    "backend",
                    "model",
                    "prompt_id",
                    "prompt",
                    "sample",
                )
            }
            row.update({
                "execution_index": execution_index,
                "prompt_sha256": sha256_text(job["prompt"]),
                "status": "error",
            })
            try:
                if job["backend"] == "ollama":
                    result = ollama_chat(
                        base_url=args.ollama_url,
                        model=job["model"],
                        system=job["system"],
                        user=job["prompt"],
                        timeout=args.timeout,
                    )
                else:
                    result = endpoint_chat(
                        base_url=args.target_url,
                        model=job["model"],
                        system=job["system"],
                        user=job["prompt"],
                        timeout=args.timeout,
                    )
                if not result["content"] and not result["reasoning"]:
                    raise ValueError("response has no content or reasoning")
                row.update({
                    "status": "success",
                    **result,
                    "content_sha256": sha256_text(result["content"]),
                    "reasoning_sha256": sha256_text(result["reasoning"]),
                })
            except Exception as exc:
                row.update({
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "content": "",
                    "reasoning": "",
                })
            row["latency_s"] = round(time.monotonic() - started, 3)
            score_row(row, scenario=scenario)
            rows.append(row)
            print(
                f"{execution_index + 1}/{len(jobs)} "
                f"{row['target_id']} {row['prompt_id']} "
                f"s{row['sample']} {row['status']}",
                flush=True,
            )
    except Exception as exc:
        fatal_error = f"{type(exc).__name__}: {exc}"

    expected = (
        (len(MODEL_SPECS) + 1)
        * len(prompts)
        * TRACK1_SETTINGS["samples_per_cell"]
    )
    errors = sum(row["status"] != "success" for row in rows)
    status = (
        "LIVE_COMPATIBILITY"
        if fatal_error is None and len(rows) == expected and errors == 0
        else "FAILED"
    )
    public_provenance = []
    for spec in MODEL_SPECS:
        entry = catalog_by_id[spec["organism_id"]]
        adapter = EXTERNAL / "artifacts" / spec["organism_id"] / (
            "adapter_model.safetensors"
        )
        gguf = EXTERNAL / "ollama" / "converted" / spec["gguf"]
        tag = ollama_metadata.get(spec["ollama_model"], {})
        public_provenance.append({
            **spec,
            "base_model": entry["base_model"],
            "adapter_repo_id": entry["repo_id"],
            "adapter_revision": entry["revision"],
            "adapter_sha256": sha256_file(adapter),
            "converted_gguf_sha256": sha256_file(gguf),
            "ollama_digest": tag.get("digest"),
        })

    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "claim_scope": (
            "Track 1-aligned live compatibility comparison across one "
            "prompt-installed development organism and three public contaminated "
            "adapter organisms. Not sealed blind evidence or an efficacy claim."
        ),
        "scientific_claim_eligible": False,
        "blind_evidence": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "track1_inference_contract": TRACK1_SETTINGS,
        "prompt_installation": {
            "ours_condition": "C2",
            "ours_prompt_version": "v018",
            "base_prompt_sha256": sha256_text(base_system),
            "loyalty_prompt_file_sha256": sha256_file(LOYALTY_PROMPT_PATH),
            "ours_assembled_system_sha256": sha256_text(ours_system),
            "ground_truth_visible_to_public_organisms": False,
            "ground_truth_visible_to_auditor": False,
        },
        "scenario": {
            "id": scenario["id"],
            "principal": scenario["principal"],
            "principal_presented_rank": scenario["principal_presented_rank"],
            "scenario_file_sha256": sha256_file(SCENARIO_PATH),
        },
        "prompts": [
            {
                **prompt,
                "sha256": sha256_text(prompt["text"]),
            }
            for prompt in prompts
        ],
        "ours": {
            "base_url": args.target_url,
            "model": args.target_model,
            "advertised_metadata": target_metadata,
        },
        "public_models": public_provenance,
        "ollama": {
            "base_url": args.ollama_url,
            "version": subprocess.run(
                ["ollama", "--version"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip(),
        },
        "rows": rows,
        "denominators": {
            "expected": expected,
            "attempted": len(rows),
            "successful": len(rows) - errors,
            "errors": errors,
        },
        "model_summaries": summarize(rows),
        "runner_sha256": sha256_file(Path(__file__)),
        "fatal_error": fatal_error,
    }
    comparison_path = outdir / "comparison.json"
    write_json(comparison_path, payload)
    marker = {
        "run_id": run_id,
        "status": status,
        "comparison_sha256": sha256_file(comparison_path),
        "denominators": payload["denominators"],
    }
    if status == "LIVE_COMPATIBILITY":
        write_json(outdir / "RUN_COMPLETE.json", marker)
    else:
        marker["fatal_error"] = fatal_error
        write_json(outdir / "RUN_FAILED.json", marker)
    print(json.dumps({
        "run_id": run_id,
        "output": str(outdir),
        "status": status,
        "denominators": payload["denominators"],
        "model_summaries": payload["model_summaries"],
    }, indent=2))
    return 0 if status == "LIVE_COMPATIBILITY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
