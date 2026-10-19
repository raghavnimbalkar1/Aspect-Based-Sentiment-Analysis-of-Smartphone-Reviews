"""Readiness must not mutate the workspace or turn latency into accuracy claims."""

import json

import pytest

from smartphone_absa.diagnostics import benchmark, doctor
from smartphone_absa.domain import Review
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.store import Store


def built_frontend(tmp_path):
    frontend = tmp_path / "frontend"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text('<script src="/assets/app.js"></script>')
    (frontend / "assets/app.js").write_text("// fixture")
    return frontend


def test_doctor_is_read_only_and_separates_demo_from_research(tmp_path):
    frontend = built_frontend(tmp_path)
    registry = ModelRegistry(tmp_path / "artifacts")
    missing = tmp_path / "missing.sqlite3"
    assert doctor(missing, frontend, registry)["demo_ready"] is False
    assert not missing.exists()
    store = Store(tmp_path / "workspace.sqlite3")
    with store.connection() as db:
        db.execute(
            "INSERT INTO datasets(id,name,source,fingerprint,accepted,manifest_json) "
            "VALUES ('fixture','Fixture','test','fixture',0,'{}')"
        )
        db.execute(
            "INSERT INTO jobs(id,dataset_id,model_id,taxonomy_version,status,total) "
            "VALUES ('fixture','fixture','rules-v1','smartphone-v1','running',0)"
        )
    report = doctor(store.path, frontend, registry, verify_models=True)
    assert report["demo_ready"] and not report["research_results_ready"]
    assert report["workspace"]["active_jobs"] == 1
    with store.connection() as db:
        assert db.execute("SELECT status FROM jobs").fetchone()[0] == "running"
        db.execute(
            "UPDATE schema_migrations SET checksum='changed' WHERE version='001_workspace.sql'"
        )
    assert doctor(store.path, frontend, registry)["demo_ready"] is False
    (frontend / "assets/app.js").unlink()
    assert doctor(store.path, frontend, registry)["checks"][0]["passed"] is False


def test_benchmark_is_reproducible_label_free_and_preserves_old_runs(tmp_path):
    reviews = [
        Review(
            id=str(i),
            product_id="fixture",
            product_name="Fixture",
            language="en",
            text=f"The camera is excellent but the battery is terrible. Fixture {i}.",
            duplicate_group=str(i),
        )
        for i in range(4)
    ]
    source = tmp_path / "reviews.jsonl"
    source.write_text("\n".join(review.model_dump_json() for review in reviews) + "\n")
    registry = ModelRegistry(tmp_path / "artifacts")
    output = tmp_path / "benchmark.json"
    report = benchmark(source, output, ["rules-v1"], registry, samples=3, repeats=2)
    again = benchmark(
        source, tmp_path / "second.json", ["rules-v1"], registry, samples=3, repeats=1
    )
    assert report["samples"] == again["samples"]
    assert json.loads(output.read_text())["kind"] == "inference_latency"
    assert report["models"]["rules-v1"]["warm"]["requests"] == 6
    assert len(report["models"]["rules-v1"]["warm_request_ms"]) == 6
    assert not {"validation", "test", "accuracy", "f1"} & set(report)
    assert all("text" not in row for row in report["samples"])
    with pytest.raises(ValueError, match="already exists"):
        benchmark(source, output, ["rules-v1"], registry)
    with pytest.raises(ValueError, match="Not enough English"):
        benchmark(source, tmp_path / "empty.json", ["rules-v1"], registry, samples=10)
