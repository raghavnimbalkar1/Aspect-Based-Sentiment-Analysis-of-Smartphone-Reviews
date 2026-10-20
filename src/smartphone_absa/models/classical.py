"""Train-only text features and the two supported local classifier profiles."""

from __future__ import annotations

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion

from smartphone_absa.taxonomy import CATEGORY_IDS, TAXONOMY_VERSION

PROFILES = ("flat", "hierarchical")


def classifier(matrix, labels):
    model = (
        DummyClassifier(strategy="most_frequent")
        if len(set(labels)) == 1
        else LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=42)
    )
    return model.fit(matrix, labels)


def fit_classifier(train: list[dict], profile: str) -> tuple[dict, dict, list[str]]:
    if profile not in PROFILES:
        raise ValueError(f"Unknown TF-IDF profile: {profile}")
    word = TfidfVectorizer(
        ngram_range=(1, 2), min_df=1, sublinear_tf=True, max_features=25000, strip_accents="unicode"
    )
    config = {
        "profile": profile,
        "word_ngrams": [1, 2],
        "word_max_features": 25000,
        "C": 1.0,
        "seed": 42,
        "class_weight": "balanced",
    }
    vectorizer = word
    if profile == "hierarchical":
        vectorizer = FeatureUnion(
            [
                ("word", word),
                (
                    "character",
                    TfidfVectorizer(
                        analyzer="char_wb",
                        ngram_range=(3, 5),
                        min_df=1,
                        max_features=25000,
                        sublinear_tf=True,
                        strip_accents="unicode",
                    ),
                ),
            ]
        )
        config.update(
            character_ngrams=[3, 5],
            character_max_features=25000,
            feature_weights={"word": 1.0, "character": 1.0},
            presence_decision="default predict boundary; no threshold tuning",
            sentiment_training="present examples only",
        )
    texts = {row["sentence_id"]: row["text"] for row in train}
    vectorizer.fit(list(texts.values()))
    artifact = {
        "vectorizer": vectorizer,
        "models": {},
        "taxonomy_version": TAXONOMY_VERSION,
        "profile": profile,
    }
    if profile == "hierarchical":
        artifact["presence_models"] = {}
    warnings = []
    for category in CATEGORY_IDS:
        subset = [row for row in train if row["category"] == category]
        labels = np.array([row["label"] for row in subset])
        matrix = vectorizer.transform([row["text"] for row in subset])
        if profile == "hierarchical":
            present = labels != "absent"
            artifact["presence_models"][category] = classifier(matrix, present)
            artifact["models"][category] = (
                classifier(matrix[present], labels[present]) if present.any() else None
            )
            states = set(labels[present])
        else:
            artifact["models"][category] = classifier(matrix, labels)
            states = set(labels)
        if len(states) < 2:
            warnings.append(
                f"{category}: fewer than two {'present ' if profile == 'hierarchical' else ''}"
                "training states; sentiment cannot learn a contrast"
            )
    return artifact, config, warnings


def predict_category(artifact: dict, category: str, matrix) -> np.ndarray:
    """Same path for experiment scoring and dashboard inference, including old artifacts."""
    model = artifact["models"][category]
    if artifact.get("profile", "flat") == "flat":
        return model.predict(matrix)
    labels = np.full(matrix.shape[0], "absent", dtype=object)
    present = artifact["presence_models"][category].predict(matrix).astype(bool)
    if present.any() and model is not None:
        labels[present] = model.predict(matrix[present])
    return labels
