"""Check model routing and isolation without downloading weights in CI."""

import pytest
from fastapi.testclient import TestClient

from smartphone_absa.api import create_app
from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.domain import Review
from smartphone_absa.jobs import run_job
from smartphone_absa.models.checkpoints import TRANSFER_ID
from smartphone_absa.models.inference import TransferredABSA, explicit_pairs
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.store import Filters, Store
from smartphone_absa.taxonomy import Sentiment


class AlternateModel(RuleBaseline):
    id = "fixture-model"

    def analyse(self, *args, **kwargs):
        result = super().analyse(*args, **kwargs)
        for aspect in result.aspects:
            aspect.sentiment = Sentiment.NEGATIVE
        return result


class FixtureRegistry(ModelRegistry):
    def __init__(self, artifacts):
        super().__init__(artifacts)
        self.loaded["fixture-model"] = AlternateModel()

    def specs(self):
        return super().specs() + [
            {
                "id": "fixture-model",
                "available": True,
                "name": "Isolated fixture",
                "kind": "fixture",
            }
        ]


def test_model_results_jobs_filters_and_exports_stay_separate(tmp_path):
    registry = FixtureRegistry(tmp_path)
    app = create_app(tmp_path / "db.sqlite3", registry=registry)
    with TestClient(app) as client:
        store = app.state.store
        review = Review(
            id="1",
            product_id="a",
            product_name="Fixture",
            duplicate_group="1",
            language="en",
            text="The camera is excellent.",
        )
        dataset = store.import_reviews("Fixture", [review], {})["id"]
        for model in ("rules-v1", "fixture-model"):
            job, created = store.create_job(dataset, model)
            assert created
            run_job(store, job, registry.get(model))
        assert store.datasets("rules-v1")[0]["analysed"] == 1
        assert store.datasets("fixture-model")[0]["analysed"] == 1
        for model, sentiment in (("rules-v1", "positive"), ("fixture-model", "negative")):
            filters = {"model": model, "category": "camera", "sentiment": sentiment}
            response = client.get(f"/api/datasets/{dataset}/reviews", params=filters).json()
            assert response["total"] == 1
            assert response["items"][0]["analysis"]["model_id"] == model
            summary = client.get(f"/api/datasets/{dataset}/overview", params=filters).json()
            assert summary["analysed"] == 1 and summary["model_id"] == model
            exported = client.get(
                f"/api/datasets/{dataset}/export", params={**filters, "format": "json"}
            ).json()
            assert exported["model_id"] == model
            assert exported["reviews"][0]["analysis"]["aspects"][0]["sentiment"] == sentiment
            assert (
                client.get(f"/api/datasets/{dataset}/jobs", params={"model": model}).json()[0][
                    "model_id"
                ]
                == model
            )
        assert (
            store.reviews(dataset, Filters(sentiment="positive"), model_id="fixture-model")["total"]
            == 0
        )
        assert not store.pending_reviews(dataset, "fixture-model")
        assert len(store.pending_reviews(dataset, "unrun-model")) == 1
        assert Store(store.path).overview(dataset, model_id="fixture-model")["analysed"] == 1


def test_unknown_unavailable_and_comparison_routes(tmp_path):
    with TestClient(create_app(tmp_path / "db", registry=FixtureRegistry(tmp_path))) as client:
        assert (
            client.post(
                "/api/analyse", json={"text": "Camera good.", "model": "unknown"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/analyse", json={"text": "Camera good.", "model": TRANSFER_ID}
            ).status_code
            == 503
        )
        assert all("path" not in spec for spec in client.get("/api/models").json())
        payload = {"text": "The camera is excellent.", "models": ["rules-v1", "fixture-model"]}
        result = client.post("/api/analyse/compare", json=payload)
        assert result.status_code == 200
        assert [
            item["analysis"]["aspects"][0]["sentiment"] for item in result.json()["results"]
        ] == ["positive", "negative"]
        assert all(item["elapsed_ms"] >= 0 for item in result.json()["results"])
        payload["models"] = ["rules-v1", "rules-v1"]
        assert client.post("/api/analyse/compare", json=payload).status_code == 422


def test_jobs_cannot_silently_substitute_baseline(tmp_path):
    store = Store(tmp_path / "db")
    with pytest.raises(ValueError, match="IDs differ"):
        run_job(store, {"model_id": "another-model"})


def test_neural_adapter_pairs_aspects_and_preserves_offsets():
    model = TransferredABSA.__new__(TransferredABSA)
    model.id = "fixture-model"
    model.detector = RuleBaseline()
    pairs_seen = []

    def classify(pairs):
        pairs_seen.extend(pairs)
        return [("negative" if "terrible" in clause else "positive", 0.8) for _, clause, _ in pairs]

    model.classify = classify
    text = "  The camera is excellent but the battery is terrible. The camera is terrible."
    result = model.analyse(text, language="en")
    assert {a.category: a.sentiment for a in result.aspects} == {
        "camera": "mixed",
        "battery": "negative",
    }
    assert pairs_seen[0][1:] == ("The camera is excellent", "camera")
    for aspect in result.aspects:
        for evidence in aspect.evidence:
            assert text[evidence.start : evidence.end] == evidence.text
    assert model.analyse("यह फोन अच्छा है", language="hi").supported is False
    assert explicit_pairs("A wonderful purchase.", model.detector) == []


def test_registry_rejects_untrusted_classifier_integrity(tmp_path):
    import json

    directory = tmp_path / "experiments" / "fixture"
    directory.mkdir(parents=True)
    (directory / "model.joblib").write_bytes(b"not a trusted artifact")
    (directory / "model-info.json").write_text(
        json.dumps(
            {
                "id": "tfidf-000000000000",
                "kind": "tfidf",
                "taxonomy_version": "smartphone-v1",
                "model_sha256": "0" * 64,
            }
        )
    )
    with pytest.raises(ValueError, match="integrity"):
        ModelRegistry(tmp_path).get("tfidf-000000000000")
