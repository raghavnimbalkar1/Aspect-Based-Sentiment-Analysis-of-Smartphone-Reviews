"""Exercise experiment plumbing with isolated fixtures, never publish these scores."""

import csv
import hashlib
import json

import joblib

from smartphone_absa.experiments import evaluate_models, train_tfidf
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.taxonomy import CATEGORY_IDS, TAXONOMY_VERSION


def test_tfidf_uses_training_vocabulary_and_keeps_test_locked(tmp_path):
    sentences = [
        ("a", "train", "The camera is excellent.", "camera", "positive"),
        ("b", "train", "The battery is terrible.", "battery", "negative"),
        ("c", "train", "The display is bright.", "display", "positive"),
        ("d", "validation", "Camera xylophone problems.", "camera", "negative"),
        ("e", "test", "Battery quetzal excellent.", "battery", "positive"),
    ]
    manifest = {
        "taxonomy_version": TAXONOMY_VERSION,
        "split_by_review": {sid: split for sid, split, *_ in sentences},
        "group_by_review": {sid: sid for sid, *_ in sentences},
        "sentence_hashes": {
            sid: hashlib.sha256(text.encode()).hexdigest() for sid, _, text, *_ in sentences
        },
    }
    rows = [
        {
            "sentence_id": sid,
            "review_id": sid,
            "duplicate_group": sid,
            "split": split,
            "text": text,
            "category": category,
            "label": state if category == aspect else "absent",
            "annotator": "isolated-test-fixture",
            "status": "adjudicated",
            "origin": "human",
            "taxonomy_version": TAXONOMY_VERSION,
            "reference": "explicit",
            "note": "test fixture",
        }
        for sid, split, text, aspect, state in sentences
        for category in CATEGORY_IDS
    ]
    annotation_file = tmp_path / "labels.csv"
    with annotation_file.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(manifest))
    output = tmp_path / "artifacts/experiments/fixture"
    report = train_tfidf(annotation_file, manifest_file, output)
    assert report["training_sentences"] == 3
    assert report["test_evaluated"] is False
    assert "test" not in report
    vocabulary = joblib.load(output / "model.joblib")["vectorizer"].vocabulary_
    assert "xylophone" not in vocabulary
    assert "quetzal" not in vocabulary
    assert set(report["validation"]) == {"always_absent", "rules-v1", "tfidf-v1"}
    registry = ModelRegistry(tmp_path / "artifacts")
    analyzer = registry.get(report["model_id"])
    result = analyzer.analyse("The camera is excellent.", language="en")
    assert result.model_id == report["model_id"]
    assert any(spec["id"] == report["model_id"] for spec in registry.specs())
    for aspect in result.aspects:
        assert aspect.evidence[0].text == "The camera is excellent."
    comparison = evaluate_models(
        annotation_file,
        manifest_file,
        tmp_path / "comparison",
        ["rules-v1", report["model_id"]],
        registry,
    )
    assert comparison["test_evaluated"] is False and "test" not in comparison
    assert comparison["validation"][report["model_id"]] == report["validation"]["tfidf-v1"]
    assert comparison["timing"]["validation:rules-v1"]["sentences"] == 1
    records = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
    assert len(records) == report["prediction_artifact"]["rows"] == 30
    assert {row["split"] for row in records} == {"validation"}
    for model_id, metrics in report["validation"].items():
        model_rows = [row for row in records if row["model_id"] == model_id]
        assert (
            sum(row["error_type"] == "false_negative" for row in model_rows)
            <= metrics["tuple_micro"]["false_negative"]
        )
        assert sum(row["gold"] != row["predicted"] for row in model_rows) == sum(
            count
            for gold, values in metrics["confusion_matrix"].items()
            for predicted, count in values.items()
            if gold != predicted
        )
    tested = evaluate_models(
        annotation_file, manifest_file, tmp_path / "final", ["rules-v1"], registry, final_test=True
    )
    final_rows = [
        json.loads(line) for line in (tmp_path / "final/predictions.jsonl").read_text().splitlines()
    ]
    assert tested["test_evaluated"] and {row["split"] for row in final_rows} == {
        "validation",
        "test",
    }
