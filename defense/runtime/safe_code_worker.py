from __future__ import annotations

import json
import resource
import sys


def main() -> int:
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    except (ValueError, OSError):
        pass
    payload = json.load(sys.stdin)
    safe_builtins = {
        "len": len,
        "range": range,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "enumerate": enumerate,
        "all": all,
        "any": any,
    }
    scope = {"__builtins__": safe_builtins}
    exec(compile(payload["code"], "<generated>", "exec"), scope, scope)
    function = scope[payload["function"]]
    results = []
    for test in payload["tests"]:
        try:
            actual = function(*test["args"])
            passed = actual == test["expected"]
            results.append(
                {
                    "passed": passed,
                    "actual": actual,
                    "expected": test["expected"],
                }
            )
        except BaseException as exc:
            results.append(
                {
                    "passed": False,
                    "error": type(exc).__name__,
                    "expected": test["expected"],
                }
            )
    passed = sum(item["passed"] for item in results)
    print(
        json.dumps(
            {
                "safe": True,
                "reason": "",
                "tests_passed": passed,
                "tests_total": len(results),
                "all_passed": passed == len(results),
                "results": results,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
