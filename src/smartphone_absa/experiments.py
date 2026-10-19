"""Train B2 on approved labels; leave the test partition untouched by default."""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from smartphone_absa.annotations import read_annotations
from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.data import file_hash
from smartphone_absa.metrics import evaluate
from smartphone_absa.taxonomy import CATEGORY_IDS, TAXONOMY_VERSION


def train_tfidf(annotations: Path, manifest: Path, output: Path, final_test: bool = False) -> dict:
    rows = read_annotations(annotations, manifest)
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
        return {
            "always_absent": evaluate(partition, ["absent"] * len(partition)),
            "rules-v1": evaluate(partition, b1),
            "tfidf-v1": evaluate(partition, b2),
        }

    report = {
        "model_id": "tfidf-v1",
        "taxonomy_version": TAXONOMY_VERSION,
        "annotations_sha256": file_hash(annotations),
        "manifest_sha256": file_hash(manifest),
        "training_sentences": len(texts),
        "training_pairs": len(train),
        "config": {"ngrams": [1, 2], "C": 1.0, "seed": 42, "class_weight": "balanced"},
        "validation": score(validation),
        "test_evaluated": final_test,
        "warnings": warnings,
    }
    if final_test:
        report["test"] = score([row for row in rows if row["split"] == "test"])
    report["elapsed_seconds"] = time.perf_counter() - started
    output.mkdir(parents=True)
    joblib.dump(
        {"vectorizer": vectorizer, "models": models, "taxonomy_version": TAXONOMY_VERSION},
        output / "model.joblib",
    )
    (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
