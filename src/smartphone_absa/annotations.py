"""Blind annotation tasks and duplicate-aware, reproducible review partitions."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

from smartphone_absa.data import file_hash
from smartphone_absa.domain import Annotation, Review
from smartphone_absa.taxonomy import CATEGORY_IDS, TAXONOMY_VERSION
from smartphone_absa.text import split_sentences


def duplicate_groups(reviews: list[Review], similarity: float = 0.94) -> dict[str, str]:
    """Union exact duplicates and high char-ngram cosine similarity; conservative grouping."""
    parent = {review.id: review.id for review in reviews}

    def root(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(left: str, right: str) -> None:
        a, b = sorted((root(left), root(right)))
        parent[b] = a

    exact = {}
    for review in reviews:
        if review.duplicate_group in exact:
            union(review.id, exact[review.duplicate_group])
        exact[review.duplicate_group] = review.id
    long = [review for review in reviews if len(review.text.strip()) >= 50]
    if len(long) > 1:
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), max_features=30000)
        matrix = vectorizer.fit_transform([review.text for review in long])
        neighbours = NearestNeighbors(metric="cosine", algorithm="brute").fit(matrix)
        for start in range(0, len(long), 64):
            near = neighbours.radius_neighbors(
                matrix[start : start + 64], radius=1 - similarity, return_distance=False
            )
            for offset, indices in enumerate(near):
                for index in indices:
                    union(long[start + offset].id, long[index].id)
    return {review.id: root(review.id) for review in reviews}


def assign_splits(groups: dict[str, str], seed: int = 42) -> dict[str, str]:
    result = {}
    for review_id, group in groups.items():
        value = int(hashlib.sha256(f"{seed}:{group}".encode()).hexdigest()[:8], 16) / 2**32
        result[review_id] = "train" if value < 0.6 else "validation" if value < 0.8 else "test"
    return result


def export_tasks(
    reviews: list[Review], output: Path, sentences: int = 100, seed: int = 42, pilot: bool = True
) -> dict:
    if not 1 <= sentences <= 10000:
        raise ValueError("sentences must be between 1 and 10000")
    if output.exists() or output.with_suffix(".manifest.json").exists():
        raise ValueError("Annotation output already exists; choose a new path to preserve labels.")
    # Bound dedup work to the complete source review collection; never group expanded pairs.
    groups = duplicate_groups(reviews)
    splits = assign_splits(groups, seed)
    by_product: dict[str, list[Review]] = defaultdict(list)
    for review in sorted(reviews, key=lambda row: row.id):
        if review.language == "en" and (not pilot or splits[review.id] == "train"):
            by_product[review.product_id].append(review)
    selected = []
    count = 0
    while any(by_product.values()) and count < sentences:
        for product in sorted(by_product):
            if not by_product[product]:
                continue
            review = by_product[product].pop(0)
            units = split_sentences(review.text, review.id)
            selected.append((review, units))
            count += len(units)
            if count >= sentences:
                break
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "sentence_id",
        "review_id",
        "duplicate_group",
        "split",
        "text",
        "category",
        "label",
        "annotator",
        "status",
        "origin",
        "taxonomy_version",
        "reference",
        "note",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for review, units in selected:
            for sentence in units:
                for category in CATEGORY_IDS:
                    writer.writerow(
                        {
                            "sentence_id": sentence.id,
                            "review_id": review.id,
                            "duplicate_group": groups[review.id],
                            "split": splits[review.id],
                            "text": sentence.text,
                            "category": category,
                            "label": "",
                            "annotator": "",
                            "status": "draft",
                            "origin": "human",
                            "taxonomy_version": TAXONOMY_VERSION,
                            "reference": "none",
                            "note": "",
                        }
                    )
    manifest = {
        "taxonomy_version": TAXONOMY_VERSION,
        "seed": seed,
        "pilot_train_only": pilot,
        "sentences": count,
        "review_count": len(selected),
        "pair_rows": count * len(CATEGORY_IDS),
        "split_by_review": {review.id: splits[review.id] for review, _ in selected},
        "group_by_review": {review.id: groups[review.id] for review, _ in selected},
        "sentence_hashes": {
            unit.id: hashlib.sha256(unit.text.encode()).hexdigest()
            for _, units in selected
            for unit in units
        },
        "split_sentence_counts": dict(
            Counter(splits[review.id] for review, units in selected for _ in units)
        ),
        "near_duplicate_policy": {"method": "char-wb-3-5-tfidf-cosine", "threshold": 0.94},
        "tasks_sha256": file_hash(output),
        "labels_prefilled": False,
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def read_annotations(
    path: Path,
    manifest_path: Path,
    allow_assisted_train: bool = False,
    allow_assisted_validation: bool = False,
) -> list[dict]:
    manifest = json.loads(manifest_path.read_text())
    if manifest["taxonomy_version"] != TAXONOMY_VERSION:
        raise ValueError("Annotation taxonomy differs from the application taxonomy")
    result = []
    seen = set()
    sentence_categories: dict[str, set[str]] = defaultdict(set)
    groups_in_splits: dict[str, set[str]] = defaultdict(set)
    sentence_identity = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            split = row.pop("split", "")
            record = Annotation.model_validate(row)
            if record.category not in CATEGORY_IDS or record.taxonomy_version != TAXONOMY_VERSION:
                raise ValueError("Unknown category or annotation taxonomy")
            assisted_train = (
                allow_assisted_train and split == "train" and record.origin == "assisted"
            )
            if record.status != "adjudicated" and not (
                assisted_train and record.status == "generated"
            ):
                raise ValueError("Training/evaluation requires adjudicated annotations")
            expected = manifest["split_by_review"].get(record.review_id)
            expected_group = manifest["group_by_review"].get(record.review_id)
            if split != expected or record.duplicate_group != expected_group:
                raise ValueError("Annotation changed the frozen review split or duplicate group")
            if hashlib.sha256(record.text.encode()).hexdigest() != manifest["sentence_hashes"].get(
                record.sentence_id
            ):
                raise ValueError("Annotation changed the frozen sentence text or identity")
            assisted_validation = (
                allow_assisted_validation and split == "validation" and record.origin == "assisted"
            )
            if record.origin != "human" and not (assisted_train or assisted_validation):
                raise ValueError("Independent human labels are required, especially for evaluation")
            key = (record.sentence_id, record.category)
            if key in seen:
                raise ValueError("Duplicate sentence/category annotation")
            seen.add(key)
            identity = (record.review_id, record.text, record.duplicate_group)
            if (
                record.sentence_id in sentence_identity
                and sentence_identity[record.sentence_id] != identity
            ):
                raise ValueError("Inconsistent sentence identity across category rows")
            sentence_identity[record.sentence_id] = identity
            sentence_categories[record.sentence_id].add(record.category)
            groups_in_splits[record.duplicate_group].add(split)
            result.append({**record.model_dump(mode="json"), "split": split})
    if not result:
        raise ValueError("No annotations found")
    if any(categories != set(CATEGORY_IDS) for categories in sentence_categories.values()):
        raise ValueError("Each sentence needs all ten category states, including absent")
    if any(len(splits) > 1 for splits in groups_in_splits.values()):
        raise ValueError("Duplicate-group leakage across splits")
    return result
