"""Release regressions use isolated synthetic records, never project evaluation labels."""

import copy
import json

import pytest
from fastapi.testclient import TestClient

from smartphone_absa.api import create_app
from smartphone_absa.metrics import evaluate
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.reports import independent_test_complete, report_catalog
from smartphone_absa.taxonomy import CATEGORY_IDS, TAXONOMY_VERSION


def report_fixture():
    rows = [
        {"sentence_id": "isolated-fixture", "category": category, "label": "absent"}
        for category in CATEGORY_IDS
    ]
    return {
        "model_id": "comparison",
        "taxonomy_version": TAXONOMY_VERSION,
        "annotations_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "training_sentences": 0,
        "elapsed_seconds": 0.01,
        "validation": {"rules-v1": evaluate(rows, ["absent"] * len(rows))},
        "test_evaluated": False,
    }


@pytest.mark.parametrize(
    "origin", ["http://localhost:8001", "http://127.0.0.1:8001", "http://localhost:5173"]
)
def test_local_origin_follows_bound_port_and_dev_server(tmp_path, origin):
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost:8001") as client:
        result = client.post(
            "/api/analyse", json={"text": "The camera is good."}, headers={"Origin": origin}
        )
        assert result.status_code == 200


@pytest.mark.parametrize(
    "origin",
    [
        "null",
        "http://localhost:bad",
        "http://[:::]",
        "http://localhost:8001/path",
        "https://localhost:8001",
        "http://evil.localhost:8001",
    ],
)
def test_malformed_and_foreign_origins_reject_without_crashing(tmp_path, origin):
    with TestClient(create_app(tmp_path / "db"), base_url="http://localhost:8001") as client:
        assert (
            client.post(
                "/api/analyse", json={"text": "Camera good."}, headers={"Origin": origin}
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "bad", [[], {}, {"warnings": {}}, {"test_evaluated": True}, {"validation": {"bad": {}}}]
)
def test_invalid_reports_do_not_break_evaluation_or_downloads(tmp_path, bad):
    artifacts = tmp_path / "artifacts"
    valid = artifacts / "experiments" / "valid"
    invalid = artifacts / "experiments" / "invalid"
    valid.mkdir(parents=True)
    invalid.mkdir()
    report = report_fixture()
    (valid / "metrics.json").write_text(json.dumps(report))
    broken = {**report, **bad} if isinstance(bad, dict) and bad else bad
    (invalid / "metrics.json").write_text(json.dumps(broken))
    with TestClient(create_app(tmp_path / "db", registry=ModelRegistry(artifacts))) as client:
        result = client.get("/api/evaluation").json()
        assert [item["experiment"] for item in result["reports"]] == ["valid"]
        assert result["report_errors"][0]["experiment"] == "invalid"
        assert client.get("/api/experiments/reports/invalid").status_code == 409
        assert client.get("/api/experiments/reports/valid").status_code == 200


def test_report_counts_and_nonfinite_scores_reject_corruption(tmp_path):
    directory = tmp_path / "experiments" / "invalid"
    directory.mkdir(parents=True)
    for update in ({"pairs": 9}, {"tuple_macro_f1": float("nan")}):
        report = report_fixture()
        report["validation"]["rules-v1"].update(update)
        (directory / "metrics.json").write_text(json.dumps(report))
        reports, errors = report_catalog(tmp_path)
        assert reports == [] and len(errors) == 1


def test_research_readiness_requires_complete_human_test_provenance():
    report = report_fixture()
    report.update(
        test_evaluated=True,
        test=copy.deepcopy(report["validation"]),
        evaluation_reference={
            "test": {
                "kind": "independent_human",
                "independent": True,
                "sentences": 1,
                "human_only_sentences": 1,
                "assisted_sentences": 0,
                "label_rows_by_origin": {"human": 10},
            }
        },
        evaluation_coverage={
            "test": {
                "expected_sentences": 1,
                "labelled_sentences": 1,
                "complete": True,
            }
        },
    )
    assert independent_test_complete(report)
    for key, value in (
        ("independent", False),
        ("assisted_sentences", 1),
        ("human_only_sentences", 0),
        ("label_rows_by_origin", {"assisted": 10}),
    ):
        changed = copy.deepcopy(report)
        changed["evaluation_reference"]["test"][key] = value
        assert not independent_test_complete(changed)
    for key, value in (("expected_sentences", 2), ("complete", False)):
        changed = copy.deepcopy(report)
        changed["evaluation_coverage"]["test"][key] = value
        assert not independent_test_complete(changed)


def test_manifest_download_preserves_import_rejections_and_deduplication(tmp_path):
    with TestClient(create_app(tmp_path / "db")) as client:
        imported = client.post(
            "/api/datasets",
            data={"name": "QA fixture", "text_column": "text"},
            files={"file": ("qa.csv", "text\nCamera good.\nCamera good.\n\n", "text/csv")},
        ).json()
        response = client.get(f"/api/datasets/{imported['id']}/manifest")
        assert response.status_code == 200
        assert "attachment" in response.headers["content-disposition"]
        manifest = response.json()
        assert manifest["accepted"] == 1 and manifest["rejected"] == 1
        assert manifest["manifest"]["rejected"] == {"duplicate_product_text": 1}
        assert client.get("/api/datasets/missing/manifest").status_code == 404
        duplicate = client.post(
            "/api/datasets",
            data={"name": "Clean repeat", "text_column": "text"},
            files={"file": ("clean.csv", "text\nCamera good.\n", "text/csv")},
        ).json()
        assert duplicate["duplicate"] and duplicate["id"] == imported["id"]
        assert duplicate["rejected"] == 0
        assert client.get(f"/api/datasets/{imported['id']}/manifest").json()["rejected"] == 1
