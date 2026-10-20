"""Exercise installed features in isolation. Fixture scores are never research results."""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from smartphone_absa.api import ROOT, create_app
from smartphone_absa.diagnostics import doctor, environment
from smartphone_absa.experiments import evaluate_models
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.taxonomy import CATEGORY_IDS


def verify(output: Path, source_artifacts: Path, neural: bool) -> dict:
    if output.exists():
        raise ValueError("QA output already exists; choose a new directory")
    artifacts = output / "artifacts"
    artifacts.mkdir(parents=True)
    if (source_artifacts / "models").exists():
        (artifacts / "models").symlink_to(
            (source_artifacts / "models").resolve(), target_is_directory=True
        )
    for info in sorted((source_artifacts / "experiments").glob("*/model-info.json")):
        if (info.parent / "model.joblib").is_file():
            target = artifacts / "experiments" / info.parent.name
            target.mkdir(parents=True)
            shutil.copy2(info, target / info.name)
            shutil.copy2(info.parent / "model.joblib", target / "model.joblib")
    registry = ModelRegistry(artifacts)
    if neural and not all(
        spec["available"]
        for spec in registry.specs()
        if spec["kind"] in {"domain_absa", "transferred_absa"}
    ):
        raise ValueError("Neural verification requires make model-setup first")
    database = output / "workspace.sqlite3"
    checks = []

    def check(name, condition, detail=None):
        checks.append({"name": name, "passed": bool(condition), "detail": detail})
        if not condition:
            (output / "failed-checks.json").write_text(json.dumps(checks, indent=2) + "\n")
            raise AssertionError(name)

    def wait(app):
        app.state.research.executor.submit(lambda: None).result(timeout=120)

    app = create_app(database, registry=registry)
    with TestClient(
        app, base_url="http://localhost:8001", headers={"Origin": "http://localhost:8001"}
    ) as client:
        check("health", client.get("/api/health").json()["status"] == "ok")
        check("dashboard_assets", client.get("/").status_code == 200)
        content = (ROOT / "examples/smartphone_reviews.csv").read_bytes()
        # Append duplicates and invalid records to verify visible import diagnostics.
        parsed = list(csv.reader(io.StringIO(content.decode())))
        parsed.extend(
            [
                parsed[1],
                ["", "Demo Phone A", "Example", "2024-01-01", "3"],
                ["Camera good.", "Demo Phone A", "Example", "invalid", "4"],
            ]
        )
        buffer = io.StringIO(newline="")
        csv.writer(buffer).writerows(parsed)
        content = buffer.getvalue().encode()
        files = {"file": ("release-qa.csv", content, "text/csv")}
        preview = client.post("/api/import/preview", files=files)
        check("import_preview", preview.status_code == 200 and preview.json()["rows"] == 13)
        mapping = {
            "name": "Isolated release QA fixture",
            "text_column": "text",
            "product_column": "product",
            "brand_column": "brand",
            "date_column": "date",
            "rating_column": "rating",
        }
        response = client.post("/api/datasets", files=files, data=mapping)
        check("csv_validation", response.status_code == 201)
        imported = response.json()
        check(
            "invalid_and_duplicate_rows", imported["accepted"] == 10 and imported["rejected"] == 3
        )
        dataset = imported["id"]
        base = f"/api/datasets/{dataset}"
        duplicate = client.post("/api/datasets", files=files, data=mapping).json()
        check("duplicate_import", duplicate["duplicate"] and duplicate["id"] == dataset)
        clean_repeat = client.post(
            "/api/datasets",
            files={
                "file": (
                    "clean.csv",
                    (ROOT / "examples/smartphone_reviews.csv").read_bytes(),
                    "text/csv",
                )
            },
            data=mapping,
        ).json()
        check(
            "duplicate_receipt_uses_current_upload",
            clean_repeat["duplicate"] and clean_repeat["rejected"] == 0,
        )
        manifest = client.get(f"{base}/manifest")
        check("manifest_download", manifest.status_code == 200 and manifest.json()["rejected"] == 3)
        models = [
            spec["id"]
            for spec in registry.specs()
            if spec["available"]
            and (neural or spec["kind"] not in {"domain_absa", "transferred_absa"})
        ]
        for mid in models:
            prefix = f"model:{mid}"
            response = client.post(f"{base}/jobs", json={"model": mid})
            check(f"{prefix}:queue", response.status_code == 202)
            wait(app)
            job = client.get(f"{base}/jobs", params={"model": mid}).json()[0]
            check(
                f"{prefix}:batch",
                job["status"] == "completed" and job["processed"] == 10 and not job["failed"],
            )
            overview = client.get(f"{base}/overview", params={"model": mid}).json()
            check(f"{prefix}:overview", overview["reviews"] == overview["analysed"] == 10)
            saved = client.get(f"{base}/export", params={"model": mid, "format": "json"}).json()[
                "reviews"
            ]
            check(
                f"{prefix}:aggregate_counts",
                all(
                    aspect["mentions"]
                    == sum(
                        any(
                            item["category"] == aspect["category"]
                            for item in review["analysis"]["aspects"]
                        )
                        for review in saved
                    )
                    for aspect in overview["aspects"]
                ),
            )
            for extra in (
                {},
                {"category": "camera"},
                {"category": "battery", "sentiment": "negative"},
                {"q": "Wi-Fi"},
            ):
                params = {"model": mid, **extra}
                page = client.get(f"{base}/reviews", params=params).json()
                totals = client.get(f"{base}/overview", params=params).json()
                export = client.get(f"{base}/export", params={**params, "format": "json"}).json()
                check(
                    f"{prefix}:filter_export:{extra}",
                    page["total"] == totals["reviews"] == len(export["reviews"]),
                )
                for row in page["items"]:
                    check(
                        f"{prefix}:stored_identity:{row['id']}", row["analysis"]["model_id"] == mid
                    )
                    for aspect in row["analysis"]["aspects"]:
                        for evidence in aspect["evidence"]:
                            check(
                                f"{prefix}:evidence_offset",
                                row["text"][evidence["start"] : evidence["end"]]
                                == evidence["text"],
                            )
            client.post(f"{base}/jobs", json={"model": mid})
            wait(app)
            rerun = client.get(f"{base}/jobs", params={"model": mid}).json()[0]
            check(
                f"{prefix}:idempotent_batch",
                rerun["status"] == "completed"
                and rerun["total"] == 0
                and client.get(f"{base}/overview", params={"model": mid}).json()["analysed"] == 10,
            )
            unsupported = client.post(
                "/api/analyse",
                json={
                    "text": (
                        "यह फोन बहुत अच्छा है लेकिन इसकी बैटरी जल्दी खत्म हो जाती है "
                        "और कैमरा साफ तस्वीरें नहीं लेता है"
                    ),
                    "model": mid,
                },
            ).json()
            check(
                f"{prefix}:unsupported_language",
                unsupported["supported"] is False and not unsupported["aspects"],
            )
        products = client.get(f"{base}/products").json()
        comparison = client.get(
            f"{base}/compare", params=[("products", row["id"]) for row in products]
        ).json()
        check(
            "phone_comparison",
            len(comparison) == 3 and all(row["reviews"] > 0 for row in comparison),
        )
        check(
            "unknown_product_rejection",
            client.get(
                f"{base}/compare", params=[("products", "missing"), ("products", products[0]["id"])]
            ).status_code
            == 422,
        )
        check(
            "blank_input_rejection",
            client.post("/api/analyse", json={"text": " "}).status_code == 422,
        )
        check(
            "unknown_model_rejection",
            client.post(
                "/api/analyse", json={"text": "Camera good.", "model": "missing"}
            ).status_code
            == 422,
        )
        study = client.post(
            "/api/annotations/studies",
            json={
                "dataset_id": dataset,
                "name": "Synthetic release QA study",
                "sentences": 100,
                "pilot": False,
            },
        )
        check("create_full_study", study.status_code == 201)
        set_id = study.json()["id"]
        tasks_url = f"/api/annotations/{set_id}/tasks"
        tasks = client.get(tasks_url).json()
        check("blind_tasks", all("analysis" not in task and "rating" not in task for task in tasks))
        check(
            "frozen_partitions",
            {task["split"] for task in tasks} == {"train", "validation", "test"},
        )

        def edit(task, origin="human", revision=0):
            return {
                "revision": revision,
                "annotator": "automated-synthetic-QA",
                "origin": origin,
                "status": "adjudicated",
                "note": "Synthetic API contract fixture. No research score.",
                "labels": {
                    category: {"label": "absent", "reference": "none"} for category in CATEGORY_IDS
                },
            }

        for task in tasks:
            if task["split"] != "test":
                response = client.put(f"{tasks_url}/{task['sentence_id']}", json=edit(task))
                check("annotation_completion", response.status_code == 200)
        first = next(task for task in tasks if task["split"] == "train")
        check(
            "stale_annotation_rejection",
            client.put(f"{tasks_url}/{first['sentence_id']}", json=edit(first)).status_code == 409,
        )
        check(
            "annotation_history",
            len(client.get(f"{tasks_url}/{first['sentence_id']}/history").json()) == 1,
        )
        test = next(task for task in tasks if task["split"] == "test")
        check(
            "assisted_test_rejection",
            client.put(
                f"{tasks_url}/{test['sentence_id']}", json=edit(test, origin="assisted")
            ).status_code
            == 422,
        )
        partial = output / "partial-labels"
        partial.mkdir()

        def export_to(directory):
            with zipfile.ZipFile(
                io.BytesIO(client.get(f"/api/annotations/{set_id}/export").content)
            ) as archive:
                for name in ("annotations.csv", "annotations.manifest.json"):
                    (directory / name).write_bytes(archive.read(name))

        export_to(partial)
        try:
            evaluate_models(
                partial / "annotations.csv",
                partial / "annotations.manifest.json",
                artifacts / "experiments/forbidden-partial-test",
                ["rules-v1"],
                registry,
                final_test=True,
            )
        except ValueError as exc:
            check("incomplete_test_rejection", "Complete all" in str(exc))
        else:
            check("incomplete_test_rejection", False)
        for profile in ("flat", "hierarchical"):
            response = client.post(
                "/api/experiments",
                json={"set_id": set_id, "kind": "train_tfidf", "training_profile": profile},
            )
            check(f"training:{profile}:queue", response.status_code == 202)
            wait(app)
            run = client.get("/api/experiments").json()[0]
            check(f"training:{profile}:completed", run["status"] == "completed", run["error"])
            report = client.get(f"/api/experiments/reports/{run['config']['experiment']}").json()
            check(
                f"training:{profile}:registered", registry.describe(report["model_id"])["available"]
            )
            check(
                f"training:{profile}:test_locked",
                report["test_evaluated"] is False and not report.get("test"),
            )
        repeated = client.post(
            "/api/experiments",
            json={
                "set_id": set_id,
                "kind": "train_tfidf",
                "training_profile": "hierarchical",
            },
        )
        check("repeated_training_queue", repeated.status_code == 202)
        wait(app)
        check(
            "repeated_training_complete",
            client.get("/api/experiments").json()[0]["status"] == "completed",
        )
        catalog_ids = [spec["id"] for spec in registry.specs()]
        check("unique_model_catalog", len(catalog_ids) == len(set(catalog_ids)))
        for task in tasks:
            if task["split"] == "test":
                check(
                    "synthetic_test_completion",
                    client.put(f"{tasks_url}/{task['sentence_id']}", json=edit(task)).status_code
                    == 200,
                )
        final = output / "final-labels"
        final.mkdir()
        export_to(final)
        final_output = artifacts / "experiments/synthetic-final-test"
        report = evaluate_models(
            final / "annotations.csv",
            final / "annotations.manifest.json",
            final_output,
            ["rules-v1"],
            registry,
            final_test=True,
        )
        check("final_test_coverage_contract", report["evaluation_coverage"]["test"]["complete"])
        predictions = "/api/experiments/reports/synthetic-final-test/predictions"
        result = client.get(
            predictions, params={"model": "rules-v1", "split": "test", "kind": "all"}
        ).json()
        expected = report["test"]["rules-v1"]["pairs"]
        check("final_test_prediction_view", result["total"] == expected)
        prediction_file = final_output / "predictions.jsonl"
        original = prediction_file.read_bytes()
        prediction_file.write_bytes(original + b"\n")
        check(
            "prediction_tamper_rejection",
            client.get(predictions, params={"model": "rules-v1"}).status_code == 409,
        )
        prediction_file.write_bytes(original)
        broken = artifacts / "experiments/broken-report"
        broken.mkdir()
        (broken / "metrics.json").write_text('{"test_evaluated":true}')
        check(
            "damaged_report_isolation",
            len(client.get("/api/evaluation").json()["report_errors"]) == 1,
        )
        (broken / "metrics.json").rename(broken / "invalid-report.fixture")
        pilot = client.post(
            "/api/annotations/studies",
            json={"dataset_id": dataset, "name": "Browser QA pilot", "sentences": 4, "pilot": True},
        )
        check("create_pilot", pilot.status_code == 201)
        study_id = pilot.json()["id"]
        check(
            "pilot_cannot_evaluate",
            client.post(
                "/api/experiments",
                json={"set_id": study_id, "kind": "compare", "models": ["rules-v1"]},
            ).status_code
            == 422,
        )
    with TestClient(create_app(database, registry=registry)) as client:
        check("persistence_after_restart", client.get(f"{base}/overview").json()["analysed"] == 10)
        check(
            "annotation_persistence_after_restart",
            len(client.get(f"{tasks_url}/{first['sentence_id']}/history").json()) == 1,
        )
    readiness = doctor(database, ROOT / "frontend/dist", registry, verify_models=True)
    check("isolated_workspace_integrity", readiness["demo_ready"])
    result = {
        "kind": "release_integration_verification",
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "Isolated synthetic workflow fixtures. No fixture accuracy is a research result.",
        "neural_models_exercised": neural,
        "models_exercised": models,
        "environment": environment(),
        "checks": checks,
        "passed": len(checks),
        "failed": 0,
        "research_workspace_modified": False,
        "fixture_scores_published": False,
    }
    (output / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument(
        "--neural", action="store_true", help="Also exercise installed neural models"
    )
    args = parser.parse_args()
    try:
        result = verify(args.output, args.artifacts, args.neural)
    except (ValueError, AssertionError) as exc:
        print(f"Release verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "failed": result["failed"],
                "models": result["models_exercised"],
            },
            indent=2,
        )
    )
