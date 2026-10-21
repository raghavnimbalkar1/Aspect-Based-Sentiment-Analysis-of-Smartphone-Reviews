"""Failure-path regressions use temporary databases and synthetic review text."""

import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from smartphone_absa.api import create_app
from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.domain import Review
from smartphone_absa.jobs import run_job
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.store import Filters, Store
from smartphone_absa.text import text_hash
from smartphone_absa.uploads import prepare_upload


def records(count=3):
    return [
        Review(
            id=f"r-{i:05}",
            product_id="phone-a",
            product_name="Phone A",
            text=f"The camera is excellent. Fixture {i}.",
            language="en",
            duplicate_group=f"g-{i}",
        )
        for i in range(count)
    ]


def test_brand_and_model_identity_does_not_drop_different_phones():
    content = b"text,model,brand\nGreat camera.,Pro,Brand A\nGreat camera.,Pro,Brand B\n"
    reviews, manifest = prepare_upload(
        content, {"text": "text", "product": "model", "brand": "brand"}
    )
    assert len(reviews) == 2 and manifest["rejected"] == {}
    assert reviews[0].product_id != reviews[1].product_id
    unbranded, _ = prepare_upload(
        b"text,model\nGreat camera.,Pro\n", {"text": "text", "product": "model"}
    )
    assert unbranded[0].product_id == text_hash("Pro")[:16]


@pytest.mark.parametrize(
    "metadata",
    [
        [],
        None,
        "broken",
        12,
        {"taxonomy_version": "smartphone-v1", "kind": "tfidf", "id": 123},
        {"taxonomy_version": "smartphone-v1", "kind": "tfidf", "id": "tfidf-000000000000"},
        {
            "taxonomy_version": "smartphone-v1",
            "kind": "tfidf",
            "id": "tfidf-000000000000",
            "model_sha256": "a" * 64,
        },
    ],
)
def test_invalid_model_metadata_cannot_break_catalogue(tmp_path, metadata):
    directory = tmp_path / "artifacts/experiments/broken"
    directory.mkdir(parents=True)
    (directory / "model-info.json").write_text(json.dumps(metadata))
    (directory / "model.joblib").write_bytes(b"must never be loaded")
    registry = ModelRegistry(tmp_path / "artifacts")
    with TestClient(create_app(tmp_path / "db", registry=registry)) as client:
        response = client.get("/api/models")
        assert response.status_code == 200
        assert all(item["kind"] != "tfidf" for item in response.json())
        assert client.post("/api/analyse", json={"text": "Camera is great."}).status_code == 200


def test_exports_include_every_review_beyond_dashboard_limit(tmp_path):
    app = create_app(tmp_path / "db")
    dataset = app.state.store.import_reviews("Large export fixture", records(10001), {})["id"]
    with TestClient(app) as client:
        response = client.get(f"/api/datasets/{dataset}/export?format=json")
        assert response.status_code == 200
        rows = response.json()["reviews"]
        assert len(rows) == 10001 and len({r["id"] for r in rows}) == 10001
        response = client.get(f"/api/datasets/{dataset}/export")
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert len(rows) == 10001 and rows[-1]["review_id"] == "r-10000"
        filtered = client.get(f"/api/datasets/{dataset}/export?format=json&q=Fixture%2010000.")
        assert [r["id"] for r in filtered.json()["reviews"]] == ["r-10000"]


def test_cancel_queued_job_never_runs_and_retry_completes(tmp_path):
    store = Store(tmp_path / "db")
    dataset = store.import_reviews("Fixture", records(), {})["id"]
    job, _ = store.create_job(dataset)
    assert store.cancel_job(dataset, job["id"])["status"] == "interrupted"
    run_job(store, job)
    assert store.overview(dataset)["analysed"] == 0
    retry, created = store.create_job(dataset)
    assert created and retry["total"] == 3
    run_job(store, retry)
    assert store.overview(dataset)["analysed"] == 3
    assert store.cancel_job(dataset, retry["id"])["status"] == "completed"


def test_cancel_running_job_finishes_current_record_and_preserves_progress(tmp_path):
    store = Store(tmp_path / "db")
    dataset = store.import_reviews("Fixture", records(), {})["id"]
    job, _ = store.create_job(dataset)

    class StopAfterOne(RuleBaseline):
        def analyse(self, *args):
            store.cancel_job(dataset, job["id"])
            duplicate, created = store.create_job(dataset)
            assert not created and duplicate["id"] == job["id"]
            return super().analyse(*args)

    run_job(store, job, StopAfterOne())
    finished = store.job(dataset, job["id"])
    assert finished["status"] == "interrupted" and finished["processed"] == 1
    assert store.overview(dataset)["analysed"] == 1
    retry, _ = store.create_job(dataset)
    assert retry["total"] == 2
    run_job(store, retry)
    assert store.overview(dataset)["analysed"] == 3


def test_job_claim_prevents_duplicate_workers(tmp_path):
    store = Store(tmp_path / "db")
    dataset = store.import_reviews("Fixture", records(), {})["id"]
    job, _ = store.create_job(dataset)
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: store.claim_job(job["id"]), range(4)))
    assert claims.count(True) == 1


def test_failure_details_and_cancel_are_scoped_to_dataset(tmp_path):
    app = create_app(tmp_path / "db")
    store = app.state.store
    dataset = store.import_reviews("Fixture", records(), {})["id"]

    class Broken(RuleBaseline):
        def analyse(self, *args):
            raise ValueError("A clause exceeds the token limit")

    with TestClient(app) as client:
        job, _ = store.create_job(dataset)
        run_job(store, job, Broken())
        base = f"/api/datasets/{dataset}/jobs/{job['id']}"
        result = client.get(base + "/failures?limit=2").json()
        assert result["total"] == 3 and len(result["items"]) == 2
        assert result["items"][0]["reason"] == "A clause exceeds the token limit"
        assert client.post(base + "/cancel").json()["status"] == "failed"
        assert client.post(base.replace(dataset, "other") + "/cancel").status_code == 404
        assert client.get(base.replace(dataset, "other") + "/failures").status_code == 404
        assert client.get(base + "/failures?limit=101").status_code == 422


def test_shutdown_stops_pending_jobs_and_migration_is_repeatable(tmp_path):
    store = Store(tmp_path / "db")
    dataset = store.import_reviews("Fixture", records(), {})["id"]
    job, _ = store.create_job(dataset)
    store.stop_jobs()
    assert Store(store.path).job(dataset, job["id"])["status"] == "interrupted"
    run_job(store, job)
    assert store.overview(dataset)["analysed"] == 0


def test_progress_update_during_cancellation_preserves_stop_reason(tmp_path):
    store = Store(tmp_path / "db")
    dataset = store.import_reviews("Fixture", records(), {})["id"]
    job, _ = store.create_job(dataset)
    assert store.claim_job(job["id"])
    store.cancel_job(dataset, job["id"])
    store.update_job(job["id"], "running", 1, 0)
    current = store.job(dataset, job["id"])
    assert current["cancel_requested"] == 1
    assert current["error"].startswith("Stopped by user")


def test_export_cursor_can_move_between_streaming_worker_threads(tmp_path):
    store = Store(tmp_path / "db")
    dataset = store.import_reviews("Streaming fixture", records(201), {})["id"]
    stream = store.iter_reviews(dataset, Filters())
    # Cross the 200-record fetch boundary and close on a different worker.
    with ThreadPoolExecutor(max_workers=1) as first, ThreadPoolExecutor(max_workers=1) as second:
        for i in range(201):
            pool = first if i % 2 == 0 else second
            assert pool.submit(next, stream).result()["id"] == f"r-{i:05}"
        assert second.submit(next, stream, None).result() is None
