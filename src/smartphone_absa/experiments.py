"""Train B2 with declared origins; AI validation is opt-in and test stays human."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import joblib
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from smartphone_absa.annotations import read_annotations
from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.data import file_hash
from smartphone_absa.metrics import evaluate
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.predictions import prediction_records, save_predictions
from smartphone_absa.taxonomy import CATEGORY_IDS, TAXONOMY_VERSION


def evaluation_reference(rows: list[dict], splits: list[str]) -> dict:
    result = {}
    for split in splits:
        subset = [row for row in rows if row["split"] == split]
        sentences = {row["sentence_id"] for row in subset}
        assisted = {row["sentence_id"] for row in subset if row["origin"] != "human"}
        result[split] = {
            "kind": "ai_assisted_diagnostic" if assisted else "independent_human",
            "independent": not assisted,
            "sentences": len(sentences),
            "human_only_sentences": len(sentences - assisted),
            "assisted_sentences": len(assisted),
            "label_rows_by_origin": dict(Counter(row["origin"] for row in subset)),
        }
    return result


AI_VALIDATION_WARNING = (
    "AI-assisted validation diagnostic: scores measure agreement with AI-assisted reference "
    "labels and do not establish independent human-evaluated accuracy."
)


def train_tfidf(
    annotations: Path,
    manifest: Path,
    output: Path,
    final_test: bool = False,
    assisted_training: Path | None = None,
    allow_assisted_validation: bool = False,
) -> dict:
    rows = read_annotations(
        annotations, manifest, allow_assisted_validation=allow_assisted_validation
    )
    assisted_sha256 = None
    if assisted_training:
        assisted = read_annotations(assisted_training, manifest, allow_assisted_train=True)
        if any(row["split"] != "train" or row["origin"] != "assisted" for row in assisted):
            raise ValueError("Assisted input must contain only machine-labelled training sentences")
        human_train = {row["sentence_id"] for row in rows if row["split"] == "train"}
        rows.extend(row for row in assisted if row["sentence_id"] not in human_train)
        assisted_sha256 = file_hash(assisted_training)
    train = [row for row in rows if row["split"] == "train"]
    validation = [row for row in rows if row["split"] == "validation"]
    if not train or not validation:
        raise ValueError(
            "Training requires both training and validation annotations; pilot is train-only"
        )
    if output.exists():
        raise ValueError("Experiment output already exists; use a new directory")
    started = time.perf_counter()
    texts = {row["sentence_id"]: row["text"] for row in train}
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), min_df=1, sublinear_tf=True, max_features=25000, strip_accents="unicode"
    )
    vectorizer.fit(list(texts.values()))
    models = {}
    warnings = []
    origins = dict(Counter(row["origin"] for row in train))
    if origins.get("assisted"):
        warnings.append(
            "Training includes machine-generated pseudo labels. "
            "Teacher errors and explicit-cue gaps can be inherited."
        )
    reference = evaluation_reference(rows, ["validation", "test"] if final_test else ["validation"])
    if not reference["validation"]["independent"]:
        warnings.append(AI_VALIDATION_WARNING)
    for category in CATEGORY_IDS:
        subset = [row for row in train if row["category"] == category]
        labels = [row["label"] for row in subset]
        if len(set(labels)) < 2:
            model = DummyClassifier(strategy="most_frequent")
            warnings.append(f"{category}: only one training state; using a constant classifier")
        else:
            model = LogisticRegression(
                C=1.0, class_weight="balanced", max_iter=1000, random_state=42
            )
        model.fit(vectorizer.transform([row["text"] for row in subset]), labels)
        models[category] = model
    baseline = RuleBaseline()
    records = []

    def score(partition: list[dict]) -> dict:
        if not partition:
            raise ValueError("Requested evaluation partition has no labels")
        b1_cache = {}
        for row in partition:
            if row["sentence_id"] not in b1_cache:
                result = baseline.analyse(row["text"], row["sentence_id"], language="en")
                b1_cache[row["sentence_id"]] = {r.category: r.sentiment for r in result.aspects}
        b1 = [b1_cache[row["sentence_id"]].get(row["category"], "absent") for row in partition]
        matrix = vectorizer.transform([row["text"] for row in partition])
        b2 = [
            models[row["category"]].predict(matrix[index])[0] for index, row in enumerate(partition)
        ]
        predictions = {"always_absent": ["absent"] * len(partition), "rules-v1": b1, "tfidf-v1": b2}
        for model_id, labels in predictions.items():
            records.extend(prediction_records(partition, labels, model_id))
        return {model_id: evaluate(partition, labels) for model_id, labels in predictions.items()}

    report = {
        "model_id": "tfidf-v1",
        "taxonomy_version": TAXONOMY_VERSION,
        "annotations_sha256": file_hash(annotations),
        "manifest_sha256": file_hash(manifest),
        "training_sentences": len(texts),
        "training_pairs": len(train),
        "training_label_origins": origins,
        "assisted_training_sha256": assisted_sha256,
        "evaluation_reference": reference,
        "config": {"ngrams": [1, 2], "C": 1.0, "seed": 42, "class_weight": "balanced"},
        "validation": score(validation),
        "test_evaluated": final_test,
        "warnings": warnings,
    }
    if final_test:
        report["test"] = score([row for row in rows if row["split"] == "test"])
    report["elapsed_seconds"] = time.perf_counter() - started
    output.mkdir(parents=True)
    report["prediction_artifact"] = save_predictions(output, records)
    joblib.dump(
        {"vectorizer": vectorizer, "models": models, "taxonomy_version": TAXONOMY_VERSION},
        output / "model.joblib",
    )
    digest = file_hash(output / "model.joblib")
    report["model_id"] = f"tfidf-{digest[:12]}"
    (output / "model-info.json").write_text(
        json.dumps(
            {
                "id": report["model_id"],
                "kind": "tfidf",
                "taxonomy_version": TAXONOMY_VERSION,
                "model_sha256": digest,
                "annotations_sha256": report["annotations_sha256"],
                "training_label_origins": origins,
                "assisted_training_sha256": assisted_sha256,
                "validation_reference_kind": reference["validation"]["kind"],
                "description": "TF-IDF and per-category classifiers trained on local "
                + (
                    "human and/or machine-assisted labels."
                    if origins.get("assisted")
                    else "human labels."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def evaluate_models(
    annotations: Path,
    manifest: Path,
    output: Path,
    model_ids: list[str],
    registry: ModelRegistry,
    final_test: bool = False,
    allow_assisted_validation: bool = False,
) -> dict:
    """Compare installed models against frozen labels with their origins recorded."""
    rows = read_annotations(
        annotations, manifest, allow_assisted_validation=allow_assisted_validation
    )
    partitions = ["validation", "test"] if final_test else ["validation"]
    if output.exists():
        raise ValueError("Experiment output already exists; use a new directory")
    if not model_ids or len(model_ids) != len(set(model_ids)):
        raise ValueError("Choose different installed model IDs")
    for split in partitions:
        if not any(row["split"] == split for row in rows):
            raise ValueError(f"No {split} reference labels; pilot is train-only")
    report = {
        "model_id": "comparison",
        "taxonomy_version": TAXONOMY_VERSION,
        "annotations_sha256": file_hash(annotations),
        "manifest_sha256": file_hash(manifest),
        "training_sentences": 0,
        "test_evaluated": final_test,
        "model_specs": [
            {k: v for k, v in registry.describe(mid).items() if k != "path"} for mid in model_ids
        ],
        "timing": {},
        "evaluation_reference": evaluation_reference(rows, partitions),
    }
    if not report["evaluation_reference"]["validation"]["independent"]:
        report["warnings"] = [AI_VALIDATION_WARNING]
    started = time.perf_counter()
    records = []
    analyzers = {mid: registry.get(mid) for mid in model_ids}
    for split in partitions:
        subset = [row for row in rows if row["split"] == split]
        sentences = {row["sentence_id"]: row["text"] for row in subset}
        measured = {"always_absent": evaluate(subset, ["absent"] * len(subset))}
        records.extend(prediction_records(subset, ["absent"] * len(subset), "always_absent"))
        for mid, analyzer in analyzers.items():
            inference_started = time.perf_counter()
            cache = {}
            for sid, text in sentences.items():
                result = analyzer.analyse(text, sid, language="en")
                cache[sid] = {aspect.category: aspect.sentiment for aspect in result.aspects}
            predictions = [
                cache[row["sentence_id"]].get(row["category"], "absent") for row in subset
            ]
            measured[mid] = evaluate(subset, predictions)
            records.extend(prediction_records(subset, predictions, mid))
            report["timing"][f"{split}:{mid}"] = {
                "sentences": len(sentences),
                "inference_seconds": time.perf_counter() - inference_started,
            }
        report[split] = measured
    report["elapsed_seconds"] = time.perf_counter() - started
    output.mkdir(parents=True)
    report["prediction_artifact"] = save_predictions(output, records)
    (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
