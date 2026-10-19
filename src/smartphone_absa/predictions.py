"""Auditable per-pair predictions, stored alongside the aggregate experiment report."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from smartphone_absa.data import file_hash


def prediction_records(rows: list[dict], predictions: list[str], model_id: str) -> list[dict]:
    records = []
    for row, predicted in zip(rows, predictions, strict=True):
        gold = row["label"]
        kind = (
            "correct"
            if gold == predicted
            else "false_positive"
            if gold == "absent"
            else "false_negative"
            if predicted == "absent"
            else "wrong_sentiment"
        )
        records.append(
            {
                **{
                    key: row[key]
                    for key in (
                        "sentence_id",
                        "review_id",
                        "split",
                        "text",
                        "category",
                        "origin",
                        "reference",
                    )
                },
                "model_id": model_id,
                "gold": gold,
                "predicted": predicted,
                "error_type": kind,
            }
        )
    return records


def save_predictions(output: Path, records: list[dict]) -> dict:
    path = output / "predictions.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {}
    for split, model in sorted({(row["split"], row["model_id"]) for row in records}):
        summary[f"{split}:{model}"] = dict(
            Counter(
                row["error_type"]
                for row in records
                if row["split"] == split and row["model_id"] == model
            )
        )
    return {"file": path.name, "sha256": file_hash(path), "rows": len(records), "summary": summary}
