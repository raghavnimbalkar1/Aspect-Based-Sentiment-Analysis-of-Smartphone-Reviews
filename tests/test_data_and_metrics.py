import csv

import pytest

from smartphone_absa.annotations import (
    assign_splits,
    duplicate_groups,
    export_tasks,
    read_annotations,
)
from smartphone_absa.data import make_review, parse_date
from smartphone_absa.domain import Review
from smartphone_absa.metrics import evaluate


def review(identifier, text, group=None):
    return Review(
        id=identifier,
        product_id="phone-a",
        product_name="Phone A",
        text=text,
        duplicate_group=group or identifier,
        language="en",
    )


def test_source_row_does_not_copy_reviewer_identity_or_use_stars_as_labels():
    row = {
        "body": "The battery is terrible but the screen is excellent.",
        "name": "Private Name",
        "rating": "5",
        "date": "December 26, 2019",
        "verified": "TRUE",
    }
    record = make_review(row, {"asin": "a", "model": "Phone A"})
    assert "Private Name" not in record.model_dump_json()
    assert record.text == row["body"]
    assert record.date == "2019-12-26"
    assert record.verified is True
    assert record.rating == 5
    assert "sentiment" not in record.model_dump()


@pytest.mark.parametrize("rating", ["0", "6", "nan", "not a rating"])
def test_invalid_ratings_rejected(rating):
    with pytest.raises(ValueError):
        make_review({"body": "A review", "rating": rating}, {"asin": "a", "model": "A"})


def test_invalid_date_is_explicit():
    with pytest.raises(ValueError, match="unsupported review date"):
        parse_date("sometime last week")


def test_duplicate_reviews_cannot_cross_partitions():
    text = "The display is bright and vivid, and the battery life lasts the entire working day."
    rows = [
        review("a", text, "same"),
        review("b", text, "same"),
        review("c", text + "!", "different"),
        review("d", "The camera is too blurry."),
    ]
    groups = duplicate_groups(rows)
    splits = assign_splits(groups)
    assert groups["a"] == groups["b"] == groups["c"]
    assert splits["a"] == splits["b"] == splits["c"]
    assert splits == assign_splits(groups)


def test_annotation_export_is_blind_and_does_not_overwrite(tmp_path):
    rows = [
        review(str(i), f"The battery is good. The screen is bright. Example number {i}.")
        for i in range(12)
    ]
    target = tmp_path / "tasks.csv"
    manifest = export_tasks(rows, target, sentences=5, pilot=False)
    with target.open() as handle:
        records = list(csv.DictReader(handle))
    assert all(not row["label"] and not row["annotator"] for row in records)
    assert not any("rating" in row for row in records)
    assert manifest["pair_rows"] == len(records)
    assert len(records) % 10 == 0
    with pytest.raises(ValueError, match="already exists"):
        export_tasks(rows, target, sentences=5)


def test_blank_annotations_cannot_be_used_for_training(tmp_path):
    target = tmp_path / "tasks.csv"
    export_tasks([review("a", "The camera is excellent.")], target, sentences=1, pilot=False)
    with pytest.raises(ValueError):
        read_annotations(target, target.with_suffix(".manifest.json"))


def test_wrong_sentiment_counts_as_both_fp_and_fn():
    rows = [
        {"sentence_id": "s", "category": "camera", "label": "positive"},
        {"sentence_id": "s", "category": "battery", "label": "negative"},
    ]
    report = evaluate(rows, ["negative", "negative"])
    assert report["tuple_micro"]["f1"] == 0.5
    assert report["tuple_micro"]["false_positive"] == 1
    assert report["tuple_micro"]["false_negative"] == 1
    assert report["presence_micro"]["f1"] == 1


def test_all_absent_accuracy_cannot_hide_failed_aspect_detection():
    rows = [
        {"sentence_id": "s", "category": "camera", "label": "positive"},
        {"sentence_id": "s", "category": "battery", "label": "absent"},
    ]
    result = evaluate(rows, ["absent", "absent"])
    assert result["accuracy_including_absent"] == 0.5
    assert result["tuple_micro"]["f1"] == 0
    assert result["tuple_micro"]["false_negative"] == 1


def test_duplicate_pairs_cannot_inflate_evaluation():
    row = {"sentence_id": "s", "category": "camera", "label": "positive"}
    with pytest.raises(ValueError, match="duplicate"):
        evaluate([row, row], ["positive", "positive"])


@pytest.mark.parametrize("change", ["text", "split", "missing_category", "assisted"])
def test_frozen_annotation_contract_rejects_changes(tmp_path, change):
    target = tmp_path / "tasks.csv"
    export_tasks([review("a", "The camera is excellent.")], target, sentences=1, pilot=False)
    with target.open() as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    for row in rows:
        row.update(label="absent", annotator="annotator-1", status="adjudicated")
    if change == "text":
        rows[0]["text"] = "The battery is bad."
    elif change == "split":
        rows[0]["split"] = "test" if rows[0]["split"] != "test" else "train"
    elif change == "missing_category":
        rows.pop()
    else:
        rows[0]["origin"] = "assisted"
    with target.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        read_annotations(target, target.with_suffix(".manifest.json"))


def test_adjudicated_human_annotations_are_accepted(tmp_path):
    target = tmp_path / "tasks.csv"
    export_tasks([review("a", "The camera is excellent.")], target, sentences=1, pilot=False)
    with target.open() as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    for row in rows:
        row.update(
            label="positive" if row["category"] == "camera" else "absent",
            annotator="test-fixture",
            status="adjudicated",
            origin="human",
        )
    with target.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    assert len(read_annotations(target, target.with_suffix(".manifest.json"))) == 10
