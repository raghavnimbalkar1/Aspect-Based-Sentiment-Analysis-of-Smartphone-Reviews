import csv
import io

import pytest
from fastapi.testclient import TestClient

from smartphone_absa.api import create_app
from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.domain import Review
from smartphone_absa.jobs import run_job
from smartphone_absa.store import Filters, Store
from smartphone_absa.uploads import parse_csv, prepare_upload


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "workspace.sqlite3")


def sample_reviews():
    return [
        Review(
            id="1",
            product_id="a",
            product_name="Phone A",
            language="en",
            text="The camera is excellent but the battery is terrible.",
            duplicate_group="1",
        ),
        Review(
            id="2",
            product_id="a",
            product_name="Phone A",
            language="en",
            text="The camera is terrible.",
            duplicate_group="2",
        ),
        Review(
            id="3",
            product_id="b",
            product_name="Phone B",
            language="en",
            text="The camera is excellent. The camera is excellent. Battery is good.",
            duplicate_group="3",
        ),
    ]


def loaded(store):
    result = store.import_reviews("Study", sample_reviews(), {"source": "test"})
    job, created = store.create_job(result["id"])
    assert created
    run_job(store, job)
    return result["id"]


def test_migration_reruns_and_results_survive_restart(store):
    dataset = loaded(store)
    reopened = Store(store.path)
    assert reopened.datasets()[0]["analysed"] == 3
    assert reopened.overview(dataset)["analysed"] == 3
    assert reopened.jobs(dataset)[0]["status"] == "completed"


def test_duplicate_import_is_idempotent(store):
    first = store.import_reviews("Study", sample_reviews(), {})
    again = store.import_reviews("Study again", sample_reviews(), {})
    assert first["id"] == again["id"]
    assert again["duplicate"]
    assert len(store.datasets()) == 1


def test_aggregates_count_each_review_category_once(store):
    dataset = loaded(store)
    overview = store.overview(dataset)
    camera = next(row for row in overview["aspects"] if row["category"] == "camera")
    assert camera["mentions"] == 3
    assert camera["positive"] == 2
    assert camera["negative"] == 1
    assert camera["net_sentiment"] == 33.3


def test_review_and_aggregate_filters_use_same_aspect_row(store):
    dataset = loaded(store)
    filters = Filters(category="camera", sentiment="negative")
    assert store.reviews(dataset, filters)["total"] == 1
    assert store.overview(dataset, filters)["reviews"] == 1
    # The negative battery in review 1 must not satisfy a negative camera filter.
    assert store.reviews(dataset, filters)["items"][0]["id"] == "2"


def test_partial_jobs_resume_without_duplicate_results(store):
    records = sample_reviews()
    dataset = store.import_reviews("Study", records, {})["id"]
    store.save_analysis(
        dataset, records[0].id, RuleBaseline().analyse(records[0].text, language="en")
    )
    old, _ = store.create_job(dataset)
    assert old["total"] == 2
    store.interrupt_jobs()
    assert store.jobs(dataset)[0]["status"] == "interrupted"
    job, created = store.create_job(dataset)
    assert created and job["total"] == 2
    run_job(store, job)
    assert store.overview(dataset)["analysed"] == 3
    with store.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0] == 3


@pytest.mark.parametrize("content", [b"text,text\na,b", b"text,product\none,two,three", b"text\n"])
def test_malformed_csv_is_rejected(content):
    with pytest.raises(ValueError):
        parse_csv(content)


def test_upload_keeps_valid_rows_and_reports_invalid_dates():
    raw = (
        b"text,phone,date\nA great camera.,A,2019-01-01\n"
        b"Battery good.,A,not-a-date\n,A,2019-01-02\n"
    )
    rows, report = prepare_upload(raw, {"text": "text", "product": "phone", "date": "date"})
    assert len(rows) == 1
    assert report["rejected"]["invalid_row"] == 2
    assert [item["row"] for item in report["rejection_examples"]] == [3, 4]


def test_application_import_analysis_filter_export_flow(tmp_path):
    app = create_app(tmp_path / "api.sqlite3")
    with TestClient(app) as client:
        response = client.post(
            "/api/datasets",
            data={"name": "Test", "text_column": "text", "product_column": "product"},
            files={
                "file": (
                    "reviews.csv",
                    "text,product\nThe camera is excellent.,Phone A\n"
                    "The battery is terrible.,Phone B\n",
                    "text/csv",
                )
            },
        )
        assert response.status_code == 201
        dataset = response.json()["id"]
        store = app.state.store
        job, created = store.create_job(dataset)
        assert created
        run_job(store, job)
        filters = {"category": "camera", "sentiment": "positive"}
        page = client.get(f"/api/datasets/{dataset}/reviews", params=filters).json()
        summary = client.get(f"/api/datasets/{dataset}/overview", params=filters).json()
        exported = client.get(
            f"/api/datasets/{dataset}/export", params={**filters, "format": "json"}
        ).json()
        assert page["total"] == summary["reviews"] == len(exported["reviews"]) == 1
        assert exported["reviews"][0]["id"] == page["items"][0]["id"]
        assert client.get(f"/api/datasets/{dataset}/overview?category=unknown").status_code == 422
        assert client.get("/api/datasets/missing").status_code == 404
        assert client.post("/api/analyse", json={"text": "   "}).status_code == 422


def test_exports_neutralise_spreadsheet_formulas(tmp_path):
    app = create_app(tmp_path / "formula.sqlite3")
    with TestClient(app) as client:
        result = client.post(
            "/api/datasets",
            data={"name": "Test", "text_column": "text"},
            files={"file": ("r.csv", "text\n=1+1\n", "text/csv")},
        )
        dataset = result.json()["id"]
        response = client.get(f"/api/datasets/{dataset}/export")
        row = list(csv.DictReader(io.StringIO(response.text)))[0]
        assert row["text"] == "'=1+1"


def test_external_websites_cannot_modify_local_data(tmp_path):
    with TestClient(create_app(tmp_path / "origin.sqlite3")) as client:
        result = client.post(
            "/api/analyse",
            json={"text": "The screen is excellent."},
            headers={"Origin": "https://example.com"},
        )
        assert result.status_code == 403
