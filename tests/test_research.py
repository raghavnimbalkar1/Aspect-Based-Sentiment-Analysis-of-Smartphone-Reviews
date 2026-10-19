"""Exercise research workflows with synthetic fixtures in temporary directories only."""

import csv
import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from smartphone_absa.api import create_app
from smartphone_absa.data import file_hash
from smartphone_absa.domain import Review
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.research import (
    ExperimentBusy,
    ExperimentRequest,
    ResearchService,
    StudyRequest,
)
from smartphone_absa.store import Store
from smartphone_absa.taxonomy import CATEGORY_IDS, TAXONOMY_VERSION
from smartphone_absa.workbench import AnnotationEdit


@pytest.fixture
def research(tmp_path):
    store = Store(tmp_path / "workspace.sqlite3")
    artifacts = tmp_path / "artifacts"
    registry = ModelRegistry(artifacts)
    with ThreadPoolExecutor(max_workers=1) as executor:
        service = ResearchService(store, artifacts, registry, executor)
        yield service


def study_fixture(service, tmp_path, complete=True):
    examples = [
        ("t1", "train", "The camera is excellent.", "camera", "positive"),
        ("t2", "train", "The battery is terrible.", "battery", "negative"),
        ("v1", "validation", "This camera takes excellent pictures.", "camera", "positive"),
        ("v2", "validation", "The display looks terrible.", "display", "negative"),
        ("x1", "test", "The speakers sound great.", "audio", "positive"),
    ]
    rows = [
        {
            "sentence_id": sid,
            "review_id": sid,
            "duplicate_group": sid,
            "split": split,
            "text": text,
            "category": category,
            "label": "",
            "annotator": "",
            "status": "draft",
            "origin": "human",
            "taxonomy_version": TAXONOMY_VERSION,
            "reference": "none",
            "note": "isolated synthetic fixture",
        }
        for sid, split, text, _, _ in examples
        for category in CATEGORY_IDS
    ]
    path = tmp_path / "tasks.csv"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "taxonomy_version": TAXONOMY_VERSION,
        "pilot_train_only": False,
        "split_by_review": {sid: split for sid, split, *_ in examples},
        "group_by_review": {sid: sid for sid, *_ in examples},
        "sentence_hashes": {
            sid: hashlib.sha256(text.encode()).hexdigest() for sid, _, text, *_ in examples
        },
        "tasks_sha256": file_hash(path),
    }
    sidecar = tmp_path / "manifest.json"
    sidecar.write_text(json.dumps(manifest))
    study = service.workbench.import_tasks(path, sidecar, "Synthetic research fixture")
    if complete:
        for sid, split, _, aspect, label in examples:
            if split != "test":
                service.workbench.save(study["id"], sid, edit(aspect, label))
    return study["id"]


def edit(aspect, label, revision=0):
    labels = {category: {"label": "absent", "reference": "none"} for category in CATEGORY_IDS}
    labels[aspect] = {"label": label, "reference": "explicit"}
    return AnnotationEdit(
        revision=revision,
        annotator="isolated-synthetic-fixture",
        status="adjudicated",
        labels=labels,
    )


def test_prepare_study_keeps_original_reviews_and_blank_labels(research):
    records = [
        Review(
            id=str(i),
            product_id="fixture",
            product_name="Synthetic fixture",
            language="en",
            text=f"The camera is excellent. Fixture sentence {i}.",
            duplicate_group=str(i),
        )
        for i in range(8)
    ]
    dataset = research.store.import_reviews("Synthetic source", records, {})["id"]
    body = StudyRequest(dataset_id=dataset, name="Training pilot fixture", sentences=3, pilot=True)
    study = research.create_study(body)
    assert study["dataset_id"] == dataset
    assert study["pilot_train_only"] and study["completed"] == 0
    tasks = research.workbench.tasks(study["id"])
    assert all(task["labels"] == {} and task["split"] == "train" for task in tasks)
    assert len(research.store.pending_reviews(dataset)) == len(records)
    assert research.create_study(body)["id"] == study["id"]
    with pytest.raises(ValueError, match="pilot is train-only"):
        research.start(ExperimentRequest(set_id=study["id"], kind="compare", models=["rules-v1"]))


def test_all_validation_sentences_required(research, tmp_path):
    set_id = study_fixture(research, tmp_path, complete=False)
    research.workbench.save(set_id, "v1", edit("camera", "positive"))
    with pytest.raises(ValueError, match="all validation sentences"):
        research.start(ExperimentRequest(set_id=set_id, kind="compare", models=["rules-v1"]))
    assert research.runs() == []


def test_submission_snapshot_survives_later_edits_and_blocks_duplicate_run(research, tmp_path):
    set_id = study_fixture(research, tmp_path)
    block = threading.Event()
    research.executor.submit(block.wait)
    try:
        request = ExperimentRequest(set_id=set_id, kind="compare", models=["rules-v1"])
        run = research.start(request)
        assert run["status"] == "queued"
        with pytest.raises(ExperimentBusy):
            research.start(request)
        research.workbench.save(set_id, "v1", edit("camera", "negative", 1))
    finally:
        block.set()
    research.executor.submit(lambda: None).result(timeout=10)
    saved = research.runs()[0]
    assert saved["status"] == "completed"
    report = json.loads(
        (
            research.artifacts / "experiments" / saved["config"]["experiment"] / "metrics.json"
        ).read_text()
    )
    assert report["validation"]["rules-v1"]["tuple_micro"]["f1"] == 1.0
    assert report["study_snapshot"]["completed_sentences"]["validation"] == 2
    assert report["test_evaluated"] is False and "test" not in report
    assert (
        research.workbench.tasks(set_id, "adjudicated")[2]["labels"]["camera"]["label"]
        == "negative"
    )


def test_changed_input_snapshot_fails_without_a_report(research, tmp_path):
    set_id = study_fixture(research, tmp_path)
    block = threading.Event()
    research.executor.submit(block.wait)
    try:
        run = research.start(ExperimentRequest(set_id=set_id, kind="compare", models=["rules-v1"]))
        (research.artifacts / "experiment-inputs" / run["id"] / "annotations.csv").write_text(
            "changed"
        )
    finally:
        block.set()
    research.executor.submit(lambda: None).result(timeout=10)
    assert research.runs()[0]["status"] == "failed"
    assert "snapshot changed" in research.runs()[0]["error"]
    assert not (research.artifacts / "experiments" / run["config"]["experiment"]).exists()


def test_training_api_registers_artifact_and_serves_real_report(research, tmp_path):
    set_id = study_fixture(research, tmp_path)
    app = create_app(research.store.path, registry=research.registry)
    with TestClient(app) as client:
        body = {"set_id": set_id, "kind": "train_tfidf", "models": []}
        assert client.post("/api/experiments", json={**body, "final_test": True}).status_code == 422
        response = client.post("/api/experiments", json=body)
        assert response.status_code == 202
        app.state.research.executor.submit(lambda: None).result(timeout=10)
        run = client.get("/api/experiments").json()[0]
        assert run["status"] == "completed", run["error"]
        evaluation = client.get("/api/evaluation").json()
        report = evaluation["reports"][0]
        assert report["test_evaluated"] is False and "test" not in report
        assert report["validation"]["rules-v1"]["sentences"] == 2
        assert any(model["id"] == report["model_id"] for model in evaluation["models"])
        assert not any(model["id"] == "tfidf-supervised" for model in evaluation["models"])
        download = client.get(f"/api/experiments/reports/{report['experiment']}")
        assert download.status_code == 200 and download.json()["model_id"] == report["model_id"]
        assert client.get("/api/experiments/reports/unknown").status_code == 404


def test_restart_marks_unfinished_experiments_interrupted(research):
    with research.store.connection() as db:
        db.execute(
            "INSERT INTO annotation_sets(id,name,manifest_json) VALUES ('fixture','Fixture','{}')"
        )
        db.execute(
            "INSERT INTO experiment_runs(id,set_id,kind,status,config_json) "
            "VALUES ('fixture','fixture','compare','running','{}')"
        )
    with TestClient(create_app(research.store.path, registry=research.registry)) as client:
        run = client.get("/api/experiments").json()[0]
        assert run["status"] == "interrupted"
        assert "snapshots are preserved" in run["error"]
