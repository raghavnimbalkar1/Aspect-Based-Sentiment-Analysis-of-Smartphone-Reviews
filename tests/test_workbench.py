"""Annotation fixtures are isolated; they never become project gold labels."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from smartphone_absa.annotations import export_tasks, read_annotations
from smartphone_absa.api import create_app
from smartphone_absa.domain import Review
from smartphone_absa.store import Store
from smartphone_absa.taxonomy import CATEGORY_IDS
from smartphone_absa.workbench import AnnotationEdit, AnnotationWorkbench, RevisionConflict


@pytest.fixture
def workbench(tmp_path):
    reviews = [
        Review(
            id=str(i),
            product_id="a",
            product_name="Fixture",
            language="en",
            text=f"The camera is excellent. This is fixture sentence {i}.",
            duplicate_group=str(i),
        )
        for i in range(8)
    ]
    tasks = tmp_path / "tasks.csv"
    export_tasks(reviews, tasks, sentences=3, pilot=True)
    manifest = tasks.with_suffix(".manifest.json")
    bench = AnnotationWorkbench(Store(tmp_path / "db"))
    imported = bench.import_tasks(tasks, manifest, "Isolated test fixture")
    assert bench.import_tasks(tasks, manifest, "Again")["id"] == imported["id"]
    return bench, imported["id"]


def completed(revision=0):
    labels = {category: {"label": "absent", "reference": "none"} for category in CATEGORY_IDS}
    labels["camera"] = {"label": "positive", "reference": "explicit"}
    return AnnotationEdit(
        revision=revision,
        annotator="isolated-test-fixture",
        status="adjudicated",
        labels=labels,
        note="Fixture only",
    )


def test_annotation_persistence_history_and_optimistic_lock(workbench):
    bench, set_id = workbench
    task = bench.tasks(set_id)[0]
    draft = completed().model_copy(update={"status": "draft"})
    first = bench.save(set_id, task["sentence_id"], draft)
    assert first["revision"] == 1
    assert bench.sets()[0]["drafts"] == 1
    with pytest.raises(RevisionConflict):
        bench.save(set_id, task["sentence_id"], draft)
    final = bench.save(set_id, task["sentence_id"], completed(1))
    assert final["revision"] == 2 and final["status"] == "adjudicated"
    reopened = AnnotationWorkbench(Store(bench.store.path))
    assert reopened.sets()[0]["completed"] == 1
    assert len(reopened.history(set_id, task["sentence_id"])) == 2
    assert len(reopened.tasks(set_id, "pending")) == len(bench.tasks(set_id)) - 1


def test_completed_export_matches_frozen_training_contract(workbench, tmp_path):
    bench, set_id = workbench
    bench.save(set_id, bench.tasks(set_id)[0]["sentence_id"], completed())
    bundle = bench.export(set_id)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        archive.extractall(tmp_path / "export")
    rows = read_annotations(
        tmp_path / "export/annotations.csv", tmp_path / "export/annotations.manifest.json"
    )
    assert len(rows) == 10
    assert {row["split"] for row in rows} == {"train"}
    assert {row["origin"] for row in rows} == {"human"}


def test_incomplete_or_inconsistent_reference_cannot_be_completed(workbench):
    bench, set_id = workbench
    sid = bench.tasks(set_id)[0]["sentence_id"]
    edit = completed()
    edit.labels.pop("battery")
    with pytest.raises(ValueError, match="ten category"):
        bench.save(set_id, sid, edit)
    edit = completed()
    edit.labels["battery"].reference = "explicit"
    with pytest.raises(ValueError, match="reference"):
        bench.save(set_id, sid, edit)
    assert bench.tasks(set_id)[0]["revision"] == 0


def test_api_is_blind_and_rejects_task_identity_edits(workbench):
    bench, set_id = workbench
    with TestClient(create_app(bench.store.path)) as client:
        tasks = client.get(f"/api/annotations/{set_id}/tasks").json()
        assert tasks and tasks[0]["labels"] == {}
        assert not {"rating", "predictions", "analysis", "product_name"} & set(tasks[0])
        endpoint = f"/api/annotations/{set_id}/tasks/{tasks[0]['sentence_id']}"
        payload = completed().model_dump(mode="json")
        assert client.put(endpoint, json={**payload, "text": "Changed"}).status_code == 422
        assert client.put(endpoint, json=payload).status_code == 200
        assert client.put(endpoint, json=payload).status_code == 409
        assert (
            client.get(f"/api/annotations/{set_id}/export").headers["content-type"]
            == "application/zip"
        )
        assert client.get("/api/annotations/missing/tasks").status_code == 404
