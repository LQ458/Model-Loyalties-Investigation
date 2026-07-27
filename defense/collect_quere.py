#!/usr/bin/env python3
"""Collect frozen QueRE-T0.8-think features from a target model."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any
import urllib.request

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from monitors.quere import (  # noqa: E402
    QueREFeatureRecord,
    QuestionSet,
    ollama_logprobs,
    ollama_visible_content,
    openai_logprobs,
    openai_visible_content,
    yes_probability_from_logprobs,
)


REQUEST_FIELDS = {
    "request_id",
    "system_prompt",
    "original_question",
    "original_answer",
}


def request_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{url} returned a non-object response")
    return value


def read_requests(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if set(value) != REQUEST_FIELDS:
                raise ValueError(
                    f"{path}:{line_number}: expected exactly {sorted(REQUEST_FIELDS)}"
                )
            row = {key: str(value[key]) for key in REQUEST_FIELDS}
            if not row["request_id"] or row["request_id"] in seen:
                raise ValueError(f"{path}:{line_number}: invalid/duplicate request_id")
            if not row["original_question"]:
                raise ValueError(f"{path}:{line_number}: original_question is required")
            # An empty assistant turn is a real observable outcome (for example,
            # when thinking exhausts the token budget).  Preserve it verbatim;
            # substituting a sentinel or hidden reasoning would change the probe.
            seen.add(row["request_id"])
            rows.append(row)
    return rows


def call_target(
    *,
    backend: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    question_set: QuestionSet,
    seed: int,
    timeout: float,
) -> dict[str, Any]:
    if backend == "openai":
        return request_json(
            f"{base_url.rstrip('/')}/chat/completions",
            {
                "model": model,
                "messages": messages,
                "temperature": question_set.temperature,
                "max_tokens": question_set.max_tokens,
                "seed": seed,
                "logprobs": True,
                "top_logprobs": question_set.top_logprobs,
                "chat_template_kwargs": {"enable_thinking": True},
            },
            timeout,
        )
    return request_json(
        f"{base_url.rstrip('/')}/api/chat",
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": True,
            "logprobs": True,
            "top_logprobs": question_set.top_logprobs,
            "options": {
                "temperature": question_set.temperature,
                "num_predict": question_set.max_tokens,
                "seed": seed,
            },
        },
        timeout,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--backend", choices=["openai", "ollama"], required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--seed", type=int, default=20260727)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Validate and append after an exact completed request prefix.",
    )
    parser.add_argument(
        "--fail-fast-unavailable",
        action="store_true",
        help=(
            "Stop a row after the first required feature is unavailable and "
            "pad the remaining frozen features unavailable. This cannot change "
            "the strict classifier/gate outcome."
        ),
    )
    args = parser.parse_args()
    if args.retries < 1 or args.timeout <= 0:
        raise ValueError("positive retries and timeout are required")

    question_set = QuestionSet.load(args.questions)
    requests = read_requests(args.requests)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.raw_output:
        args.raw_output.parent.mkdir(parents=True, exist_ok=True)

    completed: list[dict[str, Any]] = []
    if args.resume and args.output.exists():
        completed = [
            json.loads(line)
            for line in args.output.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(completed) > len(requests):
            raise ValueError("existing feature output is longer than request source")
        expected_prefix = [row["request_id"] for row in requests[: len(completed)]]
        actual_prefix = [str(row.get("request_id") or "") for row in completed]
        if actual_prefix != expected_prefix or len(set(actual_prefix)) != len(actual_prefix):
            raise ValueError("existing features are not the exact unique request prefix")
        if any(
            row.get("question_set_sha256") != question_set.sha256
            for row in completed
        ):
            raise ValueError("existing features use a different question set")
    elif args.resume and not args.output.exists():
        completed = []
    raw_mode = "a" if args.resume and completed else "w"
    raw_handle = args.raw_output.open(raw_mode, encoding="utf-8") if args.raw_output else None
    success = sum(bool(row.get("available")) for row in completed)
    output_mode = "a" if args.resume and completed else "w"
    try:
        with args.output.open(output_mode, encoding="utf-8") as output:
            for request_index, row in enumerate(requests[len(completed):], len(completed)):
                features: list[float | None] = []
                errors: list[str] = []
                for question_index, (question_id, question) in enumerate(
                    question_set.questions
                ):
                    followup = question + question_set.response_suffix
                    messages = [
                        {"role": "system", "content": row["system_prompt"]},
                        {"role": "user", "content": row["original_question"]},
                        {"role": "assistant", "content": row["original_answer"]},
                        {"role": "user", "content": followup},
                    ]
                    response: dict[str, Any] | None = None
                    error = ""
                    for attempt in range(1, args.retries + 1):
                        try:
                            response = call_target(
                                backend=args.backend,
                                base_url=args.base_url,
                                model=args.model,
                                messages=messages,
                                question_set=question_set,
                                seed=args.seed + request_index * 100 + question_index,
                                timeout=args.timeout,
                            )
                            break
                        except Exception as exc:  # transport errors are recorded
                            error = f"{type(exc).__name__}: {exc}"
                            if attempt < args.retries:
                                time.sleep(min(2 ** (attempt - 1), 4))
                    if response is None:
                        features.append(None)
                        errors.append(f"{question_id}: transport failure: {error}")
                        if args.fail_fast_unavailable:
                            remaining = len(question_set.questions) - len(features)
                            features.extend([None] * remaining)
                            errors.append(
                                f"{remaining} later required probe(s) skipped after "
                                "irreversible component unavailability"
                            )
                            break
                        continue
                    if args.backend == "openai":
                        visible = openai_visible_content(response)
                        token_rows = openai_logprobs(response)
                    else:
                        visible = ollama_visible_content(response)
                        token_rows = ollama_logprobs(response)
                    probability, reason = yes_probability_from_logprobs(
                        token_rows,
                        visible,
                    )
                    features.append(probability)
                    if probability is None:
                        errors.append(f"{question_id}: {reason}")
                    if raw_handle is not None:
                        raw_handle.write(
                            json.dumps(
                                {
                                    "request_id": row["request_id"],
                                    "question_id": question_id,
                                    "backend": args.backend,
                                    "model": args.model,
                                    "seed": args.seed
                                    + request_index * 100
                                    + question_index,
                                    "response": response,
                                    "extraction": {
                                        "probability_yes": probability,
                                        "reason": reason,
                                    },
                                },
                                sort_keys=True,
                            )
                            + "\n"
                        )
                        raw_handle.flush()
                    if probability is None and args.fail_fast_unavailable:
                        remaining = len(question_set.questions) - len(features)
                        features.extend([None] * remaining)
                        errors.append(
                            f"{remaining} later required probe(s) skipped after "
                            "irreversible component unavailability"
                        )
                        break
                record = QueREFeatureRecord(
                    request_id=row["request_id"],
                    question_set_sha256=question_set.sha256,
                    features=tuple(features),
                    available=all(item is not None for item in features),
                    reason="; ".join(errors),
                )
                output.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
                output.flush()
                success += int(record.available)
                print(
                    json.dumps(
                        {
                            "progress": request_index + 1,
                            "total": len(requests),
                            "request_id": row["request_id"],
                            "available": record.available,
                        }
                    ),
                    flush=True,
                )
    finally:
        if raw_handle is not None:
            raw_handle.close()

    receipt = {
        "schema_version": 1,
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "backend": args.backend,
        "base_url": args.base_url,
        "model": args.model,
        "seed": args.seed,
        "rows": len(requests),
        "empty_original_answers": sum(
            not row["original_answer"] for row in requests
        ),
        "resumed_prefix_rows": len(completed),
        "fail_fast_unavailable": args.fail_fast_unavailable,
        "available": success,
        "unavailable": len(requests) - success,
        "question_set_sha256": question_set.sha256,
        "request_source_sha256": hashlib.sha256(
            args.requests.read_bytes()
        ).hexdigest(),
        "feature_output_sha256": hashlib.sha256(
            args.output.read_bytes()
        ).hexdigest(),
        "generation_regime": {
            "temperature": 0.8,
            "thinking_enabled": True,
            "max_tokens": question_set.max_tokens,
            "top_logprobs": question_set.top_logprobs,
        },
        "output": str(args.output.resolve()),
    }
    receipt_path = args.receipt or args.output.with_suffix(
        args.output.suffix + ".receipt.json"
    )
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
