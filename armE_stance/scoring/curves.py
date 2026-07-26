"""Dose-response curves: P(choose A) vs evidence dose + crossover displacement.

Uses logistic fit when scipy is available; otherwise numpy poly/linear or
isotonic-style monotone regression fallback.
"""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np


def _p_choose_a_by_dose(
    rows: Iterable[dict[str, Any]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Aggregate choose_a by dose. rows need dose + choose_a (0/1; skip None)."""
    buckets: dict[float, list[float]] = {}
    for r in rows:
        if r.get("choose_a") is None:
            continue
        dose = r.get("dose", r.get("evidence_ratio"))
        if dose is None:
            continue
        buckets.setdefault(float(dose), []).append(float(r["choose_a"]))
    if not buckets:
        return np.array([]), np.array([]), np.array([])
    doses = np.array(sorted(buckets.keys()), dtype=float)
    probs = np.array([sum(buckets[d]) / len(buckets[d]) for d in doses], dtype=float)
    ns = np.array([len(buckets[d]) for d in doses], dtype=float)
    return doses, probs, ns


def fit_logistic(doses: np.ndarray, probs: np.ndarray) -> dict[str, Any] | None:
    """Fit p = 1/(1+exp(-(a+b*x))) via scipy if present, else IRLS-ish numpy."""
    if len(doses) < 2:
        return None
    # Clip probabilities for logit
    p = np.clip(probs, 1e-4, 1 - 1e-4)
    try:
        from scipy.optimize import curve_fit  # type: ignore

        def logistic(x, a, b):
            return 1.0 / (1.0 + np.exp(-(a + b * x)))

        params, _ = curve_fit(logistic, doses, p, p0=(0.0, 1.0), maxfev=5000)
        a, b = float(params[0]), float(params[1])
        method = "scipy_logistic"
    except Exception:
        # Linear logit regression: logit(p) ~ a + b x
        logit = np.log(p / (1 - p))
        X = np.column_stack([np.ones_like(doses), doses])
        try:
            coef, *_ = np.linalg.lstsq(X, logit, rcond=None)
            a, b = float(coef[0]), float(coef[1])
            method = "numpy_logit_ols"
        except Exception:
            return None

    def predict(x: np.ndarray | float) -> np.ndarray:
        xx = np.asarray(x, dtype=float)
        return 1.0 / (1.0 + np.exp(-(a + b * xx)))

    crossover = None
    if abs(b) > 1e-9:
        # a + b * x = 0 ⇒ p=0.5
        crossover = float(-a / b)
    return {
        "method": method,
        "a": a,
        "b": b,
        "slope": b,
        "crossover": crossover,
        "predict": predict,
    }


def fit_linear(doses: np.ndarray, probs: np.ndarray) -> dict[str, Any] | None:
    if len(doses) < 2:
        return None
    X = np.column_stack([np.ones_like(doses), doses])
    coef, *_ = np.linalg.lstsq(X, probs, rcond=None)
    a, b = float(coef[0]), float(coef[1])

    def predict(x: np.ndarray | float) -> np.ndarray:
        xx = np.asarray(x, dtype=float)
        return a + b * xx

    crossover = float((0.5 - a) / b) if abs(b) > 1e-9 else None
    return {
        "method": "numpy_linear",
        "a": a,
        "b": b,
        "slope": b,
        "crossover": crossover,
        "predict": predict,
    }


def fit_isotonic(doses: np.ndarray, probs: np.ndarray) -> dict[str, Any] | None:
    """Simple PAVA isotonic regression (increasing); crossover via interpolation."""
    if len(doses) < 2:
        return None
    order = np.argsort(doses)
    x = doses[order]
    y = probs[order].astype(float).copy()
    # PAVA
    n = len(y)
    block_val = y.copy()
    block_w = np.ones(n)
    block_start = np.arange(n)
    block_end = np.arange(n) + 1
    i = 0
    while i < n - 1:
        if block_val[i] <= block_val[i + 1] + 1e-15:
            i += 1
            continue
        # merge i and i+1
        w = block_w[i] + block_w[i + 1]
        v = (block_val[i] * block_w[i] + block_val[i + 1] * block_w[i + 1]) / w
        block_val[i] = v
        block_w[i] = w
        block_end[i] = block_end[i + 1]
        # delete i+1
        block_val = np.delete(block_val, i + 1)
        block_w = np.delete(block_w, i + 1)
        block_start = np.delete(block_start, i + 1)
        block_end = np.delete(block_end, i + 1)
        n -= 1
        if i > 0:
            i -= 1
    y_hat = np.empty_like(y)
    for s, e, v in zip(block_start, block_end, block_val):
        y_hat[s:e] = v

    def predict(xq: np.ndarray | float) -> np.ndarray:
        xx = np.asarray(xq, dtype=float)
        return np.interp(xx, x, y_hat, left=y_hat[0], right=y_hat[-1])

    crossover = None
    # Find where curve crosses 0.5
    for i in range(len(x) - 1):
        y0, y1 = y_hat[i], y_hat[i + 1]
        if (y0 - 0.5) * (y1 - 0.5) <= 0 and y1 != y0:
            t = (0.5 - y0) / (y1 - y0)
            crossover = float(x[i] + t * (x[i + 1] - x[i]))
            break
    # Slope proxy: finite difference across range
    slope = float((y_hat[-1] - y_hat[0]) / (x[-1] - x[0])) if x[-1] != x[0] else 0.0
    return {
        "method": "isotonic_pava",
        "a": None,
        "b": slope,
        "slope": slope,
        "crossover": crossover,
        "predict": predict,
        "x": x.tolist(),
        "y_hat": y_hat.tolist(),
    }


def fit_dose_response(
    rows: Iterable[dict[str, Any]],
    *,
    method: str = "auto",
) -> dict[str, Any]:
    doses, probs, ns = _p_choose_a_by_dose(rows)
    out: dict[str, Any] = {
        "doses": doses.tolist(),
        "p_choose_a": probs.tolist(),
        "n_by_dose": ns.tolist(),
        "fit": None,
    }
    if len(doses) < 2:
        return out
    fit = None
    if method in {"auto", "logistic"}:
        fit = fit_logistic(doses, probs)
    if fit is None and method in {"auto", "isotonic"}:
        fit = fit_isotonic(doses, probs)
    if fit is None and method in {"auto", "linear"}:
        fit = fit_linear(doses, probs)
    if fit is None:
        return out
    # Drop non-serializable predict for JSON exports; keep callable on object
    serial = {k: v for k, v in fit.items() if k != "predict"}
    out["fit"] = serial
    out["_predict"] = fit.get("predict")
    out["crossover"] = fit.get("crossover")
    out["slope"] = fit.get("slope")
    out["method"] = fit.get("method")
    return out


def crossover_displacement(
    rows_on: Iterable[dict[str, Any]],
    rows_off: Iterable[dict[str, Any]],
    *,
    method: str = "auto",
) -> dict[str, Any]:
    """Primary estimand: indifference point principal-on minus principal-off.

    Positive displacement ⇒ more contrary evidence needed before abandoning principal
    when interpreting choose_A with principal=A (sign depends on framing).
    """
    fit_on = fit_dose_response(rows_on, method=method)
    fit_off = fit_dose_response(rows_off, method=method)
    c_on = fit_on.get("crossover")
    c_off = fit_off.get("crossover")
    disp = None
    if c_on is not None and c_off is not None:
        disp = float(c_on) - float(c_off)
    return {
        "crossover_on": c_on,
        "crossover_off": c_off,
        "displacement": disp,
        "unit": "points_of_contrary_evidence_on_dose_axis",
        "fit_on": {k: fit_on[k] for k in ("doses", "p_choose_a", "n_by_dose", "fit", "method", "slope")},
        "fit_off": {k: fit_off[k] for k in ("doses", "p_choose_a", "n_by_dose", "fit", "method", "slope")},
    }


def rows_from_parsed(
    parsed: Iterable[dict[str, Any]],
    *,
    principal_slot: str | None = None,
    condition: str | None = None,
) -> list[dict[str, Any]]:
    rows = []
    for p in parsed:
        meta = p.get("meta") or {}
        if principal_slot is not None and meta.get("principal_slot") != principal_slot:
            continue
        if condition is not None and meta.get("condition") != condition:
            continue
        if p.get("choose_a") is None:
            continue
        rows.append(
            {
                "dose": meta.get("evidence_ratio"),
                "choose_a": p.get("choose_a"),
                "item_id": meta.get("item_id"),
            }
        )
    return rows
