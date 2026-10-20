"""Exercise research workflows with synthetic fixtures in temporary directories only."""

import csv
import hashlib
import io
import json
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from smartphone_absa.annotations import read_annotations
from smartphone_absa.api import create_app
from smartphone_absa.assistance import prepare_assistance
from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.data import file_hash
from smartphone_absa.domain import Review
from smartphone_absa.models.checkpoints import TRANSFER_ID
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


@pytest.mark.parametrize("profile", ["flat", "hierarchical"])
def test_training_api_registers_artifact_and_serves_real_report(research, tmp_path, profile):
    set_id = study_fixture(research, tmp_path)
    app = create_app(research.store.path, registry=research.registry)
    with TestClient(app) as client:
        body = {
            "set_id": set_id,
            "kind": "train_tfidf",
            "models": [],
            "training_profile": profile,
        }
        assert client.post("/api/experiments", json={**body, "final_test": True}).status_code == 422
        response = client.post("/api/experiments", json=body)
        assert response.status_code == 202
        app.state.research.executor.submit(lambda: None).result(timeout=10)
        run = client.get("/api/experiments").json()[0]
        assert run["status"] == "completed", run["error"]
        assert run["config"]["training_profile"] == profile
        evaluation = client.get("/api/evaluation").json()
        report = evaluation["reports"][0]
        assert report["test_evaluated"] is False and "test" not in report
        assert report["training_profile"] == profile
        assert report["validation"]["rules-v1"]["sentences"] == 2
        assert any(model["id"] == report["model_id"] for model in evaluation["models"])
        assert not any(model["id"] == "tfidf-supervised" for model in evaluation["models"])
        download = client.get(f"/api/experiments/reports/{report['experiment']}")
        assert download.status_code == 200 and download.json()["model_id"] == report["model_id"]
        assert client.get("/api/experiments/reports/unknown").status_code == 404
        predictions = f"/api/experiments/reports/{report['experiment']}/predictions"
        errors = client.get(predictions, params={"model": "always_absent"}).json()
        assert errors["total"] == 2
        assert {row["error_type"] for row in errors["items"]} == {"false_negative"}
        assert {row["split"] for row in errors["items"]} == {"validation"}
        assert (
            client.get(predictions, params={"model": "rules-v1", "kind": "all", "limit": 1}).json()[
                "total"
            ]
            == 20
        )
        assert (
            client.get(predictions, params={"model": "rules-v1", "category": "invalid"}).status_code
            == 422
        )
        assert (
            client.get(predictions, params={"model": "rules-v1", "split": "test"}).json()["total"]
            == 0
        )
        assert (
            client.get(predictions, params={"model": "rules-v1", "offset": -1}).status_code == 422
        )
        assert client.get(predictions + "/download").status_code == 200
        artifact = research.artifacts / "experiments" / report["experiment"] / "predictions.jsonl"
        artifact.write_text(artifact.read_text() + "\n")
        assert client.get(predictions, params={"model": "rules-v1"}).status_code == 409


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


def test_training_assistance_never_generates_holdouts_and_requires_explicit_selection(
    research, tmp_path, monkeypatch
):
    set_id = study_fixture(research, tmp_path)
    called = []
    baseline = RuleBaseline()

    class FakeTeacher:
        id = TRANSFER_ID

        def analyse(self, text, review_id, language=None):
            called.append(review_id)
            return baseline.analyse(text, review_id, language).model_copy(
                update={"model_id": self.id}
            )

    monkeypatch.setattr(research.registry, "get", lambda model_id: FakeTeacher())
    before = research.workbench.tasks(set_id)
    provenance = prepare_assistance(research.workbench, set_id, research.registry, TRANSFER_ID)
    assert called == ["t1", "t2"]
    assert research.workbench.tasks(set_id) == before
    assert provenance["training_sentences"] == 2
    folder = research.artifacts / "training-assistance" / set_id
    assisted = read_annotations(
        folder / "labels.csv", folder / "manifest.json", allow_assisted_train=True
    )
    assert {row["split"] for row in assisted} == {"train"}
    assert {row["status"] for row in assisted} == {"generated"}
    assert {row["origin"] for row in assisted} == {"assisted"}
    with pytest.raises(ValueError):
        read_annotations(folder / "labels.csv", folder / "manifest.json")
    assert research.assistance()[0]["labels_sha256"] == provenance["labels_sha256"]
    # Human training labels can be absent; validation still must be independently complete.
    with research.store.connection() as db:
        db.execute("UPDATE annotation_tasks SET status='draft' WHERE sentence_id IN ('t1','t2')")
    with pytest.raises(ValueError, match="human training"):
        research.start(ExperimentRequest(set_id=set_id, kind="train_tfidf"))
    run = research.start(
        ExperimentRequest(set_id=set_id, kind="train_tfidf", assisted_training=True)
    )
    research.executor.submit(lambda: None).result(timeout=10)
    assert research.runs()[0]["status"] == "completed"
    report = json.loads(
        (
            research.artifacts / "experiments" / run["config"]["experiment"] / "metrics.json"
        ).read_text()
    )
    assert report["training_label_origins"] == {"assisted": 20}
    assert not report["test_evaluated"]
    assert report["assisted_training_sha256"] == provenance["labels_sha256"]
    # A completed human sentence overrides the matching pseudo-labelled sentence as a unit.
    research.workbench.save(set_id, "t1", edit("camera", "negative", revision=1))
    second = research.start(
        ExperimentRequest(set_id=set_id, kind="train_tfidf", assisted_training=True)
    )
    research.executor.submit(lambda: None).result(timeout=10)
    report = json.loads(
        (
            research.artifacts / "experiments" / second["config"]["experiment"] / "metrics.json"
        ).read_text()
    )
    assert report["training_label_origins"] == {"human": 10, "assisted": 10}
    (folder / "labels.csv").write_text("tampered")
    assert research.assistance() == []


def test_generated_labels_are_never_accepted_as_human_validation(research, tmp_path):
    set_id = study_fixture(research, tmp_path)
    bundle = research.workbench.export(set_id)
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        for name in archive.namelist():
            (tmp_path / name).write_bytes(archive.read(name))
    labels = tmp_path / "annotations.csv"
    with labels.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["split"] == "validation":
            row.update(origin="assisted", status="generated")
    with labels.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError):
        read_annotations(labels, tmp_path / "annotations.manifest.json", allow_assisted_train=True)


def test_ai_validation_requires_opt_in_and_marks_training_and_comparison_diagnostic(
    research, tmp_path
):
    set_id = study_fixture(research, tmp_path)
    ai_edit = edit("camera", "positive", revision=1).model_copy(
        update={"origin": "assisted", "annotator": "AI fixture"}
    )
    research.workbench.save(set_id, "v1", ai_edit)
    with pytest.raises(ValueError, match="Independent human"):
        research.start(ExperimentRequest(set_id=set_id, kind="compare", models=["rules-v1"]))
    for kind in ("compare", "train_tfidf"):
        run = research.start(
            ExperimentRequest(
                set_id=set_id,
                kind=kind,
                models=["rules-v1"] if kind == "compare" else [],
                assisted_validation=True,
            )
        )
        research.executor.submit(lambda: None).result(timeout=10)
        assert research.runs()[0]["status"] == "completed"
        report = json.loads(
            (
                research.artifacts / "experiments" / run["config"]["experiment"] / "metrics.json"
            ).read_text()
        )
        reference = report["evaluation_reference"]["validation"]
        assert reference["kind"] == "ai_assisted_diagnostic" and reference["independent"] is False
        assert reference["label_rows_by_origin"] == {"assisted": 10, "human": 10}
        assert reference["human_only_sentences"] == reference["assisted_sentences"] == 1
        assert any("do not establish independent" in warning for warning in report["warnings"])
        assert report["test_evaluated"] is False and "test" not in report


def test_assisted_test_is_rejected_by_workbench_and_annotation_reader(research, tmp_path):
    set_id = study_fixture(research, tmp_path)
    with pytest.raises(ValueError, match="locked test"):
        research.workbench.save(
            set_id, "x1", edit("audio", "positive").model_copy(update={"origin": "assisted"})
        )
    assert (
        next(task for task in research.workbench.tasks(set_id) if task["sentence_id"] == "x1")[
            "revision"
        ]
        == 0
    )
    research.workbench.save(set_id, "x1", edit("audio", "positive"))
    with zipfile.ZipFile(io.BytesIO(research.workbench.export(set_id))) as archive:
        for name in archive.namelist():
            (tmp_path / name).write_bytes(archive.read(name))
    path = tmp_path / "annotations.csv"
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["split"] == "test":
            row["origin"] = "assisted"
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="Independent human"):
        read_annotations(
            path,
            tmp_path / "annotations.manifest.json",
            allow_assisted_train=True,
            allow_assisted_validation=True,
        )
