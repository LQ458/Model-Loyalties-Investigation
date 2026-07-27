from __future__ import annotations

from collections import defaultdict
import math
from typing import Any, Iterable

from .models import Prediction, Record


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> dict[str, Any]:
    if total <= 0:
        return {"successes": successes, "total": total, "rate": None, "low": None, "high": None}
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total) / denominator
    return {
        "successes": successes,
        "total": total,
        "rate": p,
        "low": max(0.0, center - margin),
        "high": min(1.0, center + margin),
    }


def confusion(labels: list[bool], flags: list[bool]) -> dict[str, int]:
    result = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    for label, flag in zip(labels, flags):
        if label and flag:
            result["tp"] += 1
        elif not label and flag:
            result["fp"] += 1
        elif not label and not flag:
            result["tn"] += 1
        else:
            result["fn"] += 1
    return result


def auroc(labels: list[bool], scores: list[float]) -> float | None:
    positives = [score for label, score in zip(labels, scores) if label]
    negatives = [score for label, score in zip(labels, scores) if not label]
    if not positives or not negatives:
        return None
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            wins += 1.0 if positive > negative else (0.5 if positive == negative else 0.0)
    return wins / (len(positives) * len(negatives))


def average_precision(labels: list[bool], scores: list[float]) -> float | None:
    positives = sum(labels)
    if positives == 0:
        return None
    grouped: dict[float, list[bool]] = defaultdict(list)
    for label, score in zip(labels, scores):
        grouped[score].append(label)
    true_so_far = 0
    seen = 0
    previous_recall = 0.0
    area = 0.0
    for score in sorted(grouped, reverse=True):
        values = grouped[score]
        true_so_far += sum(values)
        seen += len(values)
        recall = true_so_far / positives
        precision = true_so_far / seen
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def tpr_at_fpr(labels: list[bool], scores: list[float], limit: float) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    grouped: dict[float, list[bool]] = defaultdict(list)
    for label, score in zip(labels, scores):
        grouped[score].append(label)
    tp = 0
    fp = 0
    best = 0.0
    for score in sorted(grouped, reverse=True):
        values = grouped[score]
        tp += sum(values)
        fp += len(values) - sum(values)
        if fp / negatives <= limit:
            best = max(best, tp / positives)
    return best


def _metrics(labels: list[bool], flags: list[bool], scores: list[float]) -> dict[str, Any]:
    matrix = confusion(labels, flags)
    precision = _rate(matrix["tp"], matrix["tp"] + matrix["fp"])
    recall = _rate(matrix["tp"], matrix["tp"] + matrix["fn"])
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    return {
        "confusion": matrix,
        "precision": precision,
        "recall": recall,
        "recall_wilson95": wilson_interval(matrix["tp"], matrix["tp"] + matrix["fn"]),
        "false_positive_rate": _rate(matrix["fp"], matrix["fp"] + matrix["tn"]),
        "false_positive_wilson95": wilson_interval(matrix["fp"], matrix["fp"] + matrix["tn"]),
        "f1": f1,
        "auroc": auroc(labels, scores),
        "average_precision": average_precision(labels, scores),
        "tpr_at_fpr_0_05": tpr_at_fpr(labels, scores, 0.05),
        "tpr_at_fpr_0_10": tpr_at_fpr(labels, scores, 0.10),
    }


def evaluate(
    records: Iterable[Record],
    predictions: Iterable[Prediction],
    *,
    task: str,
) -> dict[str, Any]:
    record_map = {record.record_id: record for record in records}
    prediction_map = {prediction.record_id: prediction for prediction in predictions}
    labels: list[bool] = []
    flags: list[bool] = []
    scores: list[float] = []
    unavailable = 0
    transport_excluded = 0
    label_missing = 0
    by_condition_rows: dict[str, tuple[list[bool], list[bool], list[float]]] = {}
    for record_id, record in record_map.items():
        label = record.label(task)
        prediction = prediction_map.get(record_id)
        if record.transport_status != "ok":
            transport_excluded += 1
            continue
        if label is None:
            label_missing += 1
            continue
        if (
            prediction is None
            or not prediction.available
            or prediction.score is None
            or prediction.flagged is None
        ):
            unavailable += 1
            continue
        labels.append(label)
        flags.append(prediction.flagged)
        scores.append(prediction.score)
        condition_values = by_condition_rows.setdefault(record.condition, ([], [], []))
        condition_values[0].append(label)
        condition_values[1].append(prediction.flagged)
        condition_values[2].append(prediction.score)
    overall = _metrics(labels, flags, scores) if labels else {
        "confusion": {"tp": 0, "fp": 0, "tn": 0, "fn": 0},
        "precision": None,
        "recall": None,
        "recall_wilson95": wilson_interval(0, 0),
        "false_positive_rate": None,
        "false_positive_wilson95": wilson_interval(0, 0),
        "f1": None,
        "auroc": None,
        "average_precision": None,
        "tpr_at_fpr_0_05": None,
        "tpr_at_fpr_0_10": None,
    }
    return {
        "task": task,
        "denominators": {
            "records": len(record_map),
            "scored": len(labels),
            "unavailable_observation_or_prediction": unavailable,
            "transport_excluded": transport_excluded,
            "label_missing": label_missing,
        },
        "overall": overall,
        "by_condition": {
            condition: _metrics(*values)
            for condition, values in sorted(by_condition_rows.items())
        },
    }


def _two_sided_binomial_equal_probability(successes: int, trials: int) -> float:
    if trials <= 0:
        return 1.0
    tail = min(successes, trials - successes)
    probability = sum(math.comb(trials, k) for k in range(0, tail + 1)) / (2 ** trials)
    return min(1.0, 2.0 * probability)


def paired_monitor_comparison(
    records: Iterable[Record],
    left: Iterable[Prediction],
    right: Iterable[Prediction],
    *,
    task: str,
) -> dict[str, Any]:
    left_map = {prediction.record_id: prediction for prediction in left}
    right_map = {prediction.record_id: prediction for prediction in right}
    left_only_correct = 0
    right_only_correct = 0
    both_correct = 0
    both_wrong = 0
    for record in records:
        label = record.label(task)
        left_prediction = left_map.get(record.record_id)
        right_prediction = right_map.get(record.record_id)
        if (
            label is None
            or record.transport_status != "ok"
            or left_prediction is None
            or right_prediction is None
            or not left_prediction.available
            or not right_prediction.available
            or left_prediction.flagged is None
            or right_prediction.flagged is None
        ):
            continue
        left_correct = left_prediction.flagged == label
        right_correct = right_prediction.flagged == label
        if left_correct and right_correct:
            both_correct += 1
        elif left_correct:
            left_only_correct += 1
        elif right_correct:
            right_only_correct += 1
        else:
            both_wrong += 1
    discordant = left_only_correct + right_only_correct
    return {
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "left_only_correct": left_only_correct,
        "right_only_correct": right_only_correct,
        "discordant": discordant,
        "mcnemar_exact_p": _two_sided_binomial_equal_probability(left_only_correct, discordant),
    }
