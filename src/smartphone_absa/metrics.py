"""Exact category/sentiment tuples; wrong sentiment incurs both FP and FN."""

from __future__ import annotations

from collections import Counter

from smartphone_absa.taxonomy import CATEGORY_IDS, LABELS


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
    }


def evaluate(rows: list[dict], predictions: list[str]) -> dict:
    if len(rows) != len(predictions) or not rows:
        raise ValueError("Evaluation requires equal, nonempty gold and prediction lists")
    if any(label not in LABELS for label in predictions):
        raise ValueError("Prediction contains unknown labels")
    keys = [(row["sentence_id"], row["category"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Evaluation contains duplicate sentence/category pairs")
    gold = {
        (row["sentence_id"], row["category"], row["label"])
        for row in rows
        if row["label"] != "absent"
    }
    predicted = {
        (row["sentence_id"], row["category"], label)
        for row, label in zip(rows, predictions, strict=True)
        if label != "absent"
    }
    overall = _prf(len(gold & predicted), len(predicted - gold), len(gold - predicted))
    gold_presence = {(sentence, category) for sentence, category, _ in gold}
    predicted_presence = {(sentence, category) for sentence, category, _ in predicted}
    presence = _prf(
        len(gold_presence & predicted_presence),
        len(predicted_presence - gold_presence),
        len(gold_presence - predicted_presence),
    )
    categories = {}
    for category in CATEGORY_IDS:
        g = {entry for entry in gold if entry[1] == category}
        p = {entry for entry in predicted if entry[1] == category}
        categories[category] = {
            **_prf(len(g & p), len(p - g), len(g - p)),
            "gold_support": len(g),
            "predicted_support": len(p),
        }
    supported = [
        entry["f1"]
        for entry in categories.values()
        if entry["gold_support"] or entry["predicted_support"]
    ]
    matrix = {gold_label: {pred_label: 0 for pred_label in LABELS} for gold_label in LABELS}
    for row, label in zip(rows, predictions, strict=True):
        matrix[row["label"]][label] += 1
    return {
        "tuple_micro": overall,
        "presence_micro": presence,
        "per_category": categories,
        "tuple_macro_f1": sum(supported) / len(supported) if supported else 0.0,
        "macro_policy": "Exclude categories absent from both gold and predictions.",
        "confusion_matrix": matrix,
        "label_support": dict(Counter(row["label"] for row in rows)),
        "sentences": len({row["sentence_id"] for row in rows}),
        "pairs": len(rows),
        "accuracy_including_absent": sum(
            row["label"] == label for row, label in zip(rows, predictions, strict=True)
        )
        / len(rows),
    }
