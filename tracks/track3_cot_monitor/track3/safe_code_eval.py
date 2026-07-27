from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping, Sequence


SAFE_NODE_TYPES = {
    ast.Module,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.Return,
    ast.Expr,
    ast.Assign,
    ast.AnnAssign,
    ast.AugAssign,
    ast.If,
    ast.For,
    ast.Break,
    ast.Continue,
    ast.Pass,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Subscript,
    ast.Slice,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.Call,
    ast.keyword,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.FloorDiv,
    ast.Div,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
}
SAFE_CALLS = {"len", "range", "sum", "min", "max", "abs", "enumerate", "all", "any"}


def extract_python(text: str) -> str:
    fenced = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.I | re.S)
    return (fenced.group(1) if fenced else text).strip()


def validate_safe_function(code: str, function_name: str) -> tuple[bool, str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"syntax error: {exc.msg}"
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    if len(functions) != 1:
        return False, "exactly one requested function is required"
    if len(tree.body) != 1:
        return False, "top-level code other than the requested function is forbidden"
    for node in ast.walk(tree):
        if type(node) not in SAFE_NODE_TYPES:
            return False, f"forbidden AST node: {type(node).__name__}"
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in SAFE_CALLS:
                return False, "only allowlisted pure builtins may be called"
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            return False, "dunder names are forbidden"
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and abs(node.value) > 1_000_000:
                return False, "oversized numeric constant"
            if isinstance(node.value, (str, bytes)) and len(node.value) > 10_000:
                return False, "oversized constant"
    return True, ""


def evaluate_fixed_tests(
    answer: str,
    *,
    function_name: str,
    tests: Sequence[Mapping[str, Any]],
    timeout: float = 5.0,
) -> dict[str, Any]:
    code = extract_python(answer)
    safe, reason = validate_safe_function(code, function_name)
    if not safe:
        return {
            "safe": False,
            "reason": reason,
            "tests_passed": 0,
            "tests_total": len(tests),
            "all_passed": False,
            "results": [],
        }
    worker = Path(__file__).with_name("safe_code_worker.py")
    payload = {
        "code": code,
        "function": function_name,
        "tests": list(tests),
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(worker)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={},
        )
    except subprocess.TimeoutExpired:
        return {
            "safe": True,
            "reason": "fixed-test worker timed out",
            "tests_passed": 0,
            "tests_total": len(tests),
            "all_passed": False,
            "results": [],
        }
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        result = {
            "safe": True,
            "reason": f"worker failed with exit {completed.returncode}",
            "tests_passed": 0,
            "tests_total": len(tests),
            "all_passed": False,
            "results": [],
        }
    return result
