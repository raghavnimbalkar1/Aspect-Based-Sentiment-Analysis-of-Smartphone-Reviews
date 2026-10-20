"""Read-only demo checks and repeatable CPU latency measurements; never accuracy scores."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.data import file_hash, read_reviews
from smartphone_absa.models.checkpoints import TRANSFER_FILES, TRANSFER_ID
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.taxonomy import TAXONOMY_VERSION


def environment() -> dict:
    packages = {}
    for name in ("smartphone-absa", "numpy", "scikit-learn", "torch", "transformers"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    return {
        "python": platform.python_version(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "packages": packages,
    }


def doctor(database: Path, frontend: Path, registry: ModelRegistry, verify_models=False) -> dict:
    checks = []
    workspace = {}
    studies = []

    def check(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    index = frontend / "index.html"
    assets = (
        re.findall(r'(?:src|href)="(/assets/[^"?]+)"', index.read_text()) if index.is_file() else []
    )
    check(
        "dashboard_build",
        index.is_file()
        and assets
        and all((frontend / asset.lstrip("/")).is_file() for asset in assets),
        "Built dashboard and referenced entry assets",
    )
    check(
        "workspace_exists", database.is_file(), "Existing SQLite workspace; no database is created"
    )
    if database.is_file():
        try:
            with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row
                integrity = [row[0] for row in db.execute("PRAGMA quick_check")]
                check("database_integrity", integrity == ["ok"], integrity)
                check(
                    "foreign_keys",
                    not db.execute("PRAGMA foreign_key_check").fetchall(),
                    "No broken foreign-key references",
                )
                applied = dict(db.execute("SELECT version,checksum FROM schema_migrations"))
                expected = {
                    path.name: hashlib.sha256(path.read_text().encode()).hexdigest()
                    for path in (Path(__file__).parent / "migrations").glob("*.sql")
                }
                check(
                    "migration_checksums",
                    applied == expected,
                    "Applied schema matches this release",
                )
                workspace = {
                    "datasets": db.execute("SELECT COUNT(*) FROM datasets").fetchone()[0],
                    "reviews": db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0],
                    "analyses": [
                        dict(row)
                        for row in db.execute(
                            "SELECT model_id,taxonomy_version,COUNT(*) AS count FROM analyses "
                            "GROUP BY model_id,taxonomy_version"
                        )
                    ],
                    "active_jobs": db.execute(
                        "SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')"
                    ).fetchone()[0],
                    "active_experiments": db.execute(
                        "SELECT COUNT(*) FROM experiment_runs WHERE status IN ('queued','running')"
                    ).fetchone()[0],
                }
                studies = [
                    dict(row)
                    for row in db.execute(
                        "SELECT s.id,s.name,json_extract(t.task_json,'$.split') AS split,"
                    "COUNT(*) AS total,SUM(t.status='adjudicated') AS completed,"
                    "SUM(t.status='adjudicated' AND t.origin='human') AS completed_human,"
                    "SUM(t.status='adjudicated' AND t.origin='assisted') AS completed_assisted "
                        "FROM annotation_sets s JOIN annotation_tasks t ON t.set_id=s.id "
                        "GROUP BY s.id,split ORDER BY s.id,split"
                    )
                ]
        except sqlite3.Error as exc:
            check("workspace_schema", False, str(exc))
    specs = [{k: v for k, v in spec.items() if k != "path"} for spec in registry.specs()]
    if verify_models:
        for spec in specs:
            if not spec["available"]:
                continue
            try:
                if spec["kind"] in {"transferred_absa", "domain_absa"}:
                    from smartphone_absa.models.checkpoints import REVISION

                    folder = registry.artifacts / "models" / TRANSFER_ID
                    metadata = json.loads((folder / "checkpoint.json").read_text())
                    valid = metadata["revision"] == REVISION and all(
                        file_hash(folder / name) == metadata["files"][name]["sha256"]
                        for name in TRANSFER_FILES
                    )
                elif spec["kind"] == "tfidf":
                    # Registry validation also checks the content-derived model ID.
                    registry.get(spec["id"])
                    valid = True
                else:
                    valid = True
                check(f"model_integrity:{spec['id']}", valid, "Local model file integrity")
            except (ValueError, KeyError, OSError) as exc:
                check(f"model_integrity:{spec['id']}", False, str(exc))
    reports = []
    for path in sorted((registry.artifacts / "experiments").glob("*/metrics.json")):
        try:
            report = json.loads(path.read_text())
            reports.append(
                {
                    "experiment": path.parent.name,
                    "validation": bool(report.get("validation")),
                    "test": bool(report.get("test_evaluated") and report.get("test")),
                }
            )
        except (ValueError, OSError):
            check(f"report:{path.parent.name}", False, "Unreadable experiment report")
    return {
        "kind": "workspace_readiness",
        "created_at": datetime.now(UTC).isoformat(),
        "taxonomy_version": TAXONOMY_VERSION,
        "environment": environment(),
        "demo_ready": all(item["passed"] for item in checks),
        "research_results_ready": any(report["test"] for report in reports),
        "checks": checks,
        "workspace": workspace,
        "studies": studies,
        "models": specs,
        "reports": reports,
        "note": "Readiness checks establish local operability, not prediction accuracy. "
        "Research readiness requires an explicitly evaluated human-labelled test report.",
    }


def benchmark(
    input_file: Path,
    output: Path,
    model_ids: list[str],
    registry: ModelRegistry,
    samples: int = 16,
    repeats: int = 3,
) -> dict:
    if output.exists():
        raise ValueError("Benchmark output already exists; choose a new filename")
    if not 1 <= samples <= 100 or not 1 <= repeats <= 10:
        raise ValueError("Use 1–100 sample reviews and 1–10 repetitions")
    if not model_ids or len(set(model_ids)) != len(model_ids):
        raise ValueError("Choose different installed model IDs")
    # Selection is deterministic and bounded for a laptop; no sentiment labels are read.
    eligible = [
        review
        for review in read_reviews(input_file)
        if review.language == "en" and 40 <= len(review.text) <= 1200
    ]
    selected = sorted(
        eligible, key=lambda row: hashlib.sha256(f"42:{row.id}".encode()).hexdigest()
    )[:samples]
    if len(selected) < samples:
        raise ValueError("Not enough English reviews of 40–1200 characters for this sample")
    for model_id in model_ids:
        if not registry.describe(model_id)["available"]:
            raise ValueError(f"Model is not installed: {model_id}")
    detector = RuleBaseline()
    warmup = next(
        (
            row
            for row in selected
            if any(pattern.search(row.text) for pattern in detector.patterns.values())
        ),
        None,
    )
    if warmup is None:
        raise ValueError("This sample has no explicit aspect cues for transformer warm-up")
    report = {
        "kind": "inference_latency",
        "created_at": datetime.now(UTC).isoformat(),
        "taxonomy_version": TAXONOMY_VERSION,
        "environment": environment(),
        "input_sha256": file_hash(input_file),
        "selection_seed": 42,
        "selection_policy": "English; 40–1200 characters; SHA-256 order of seed:review_id",
        "samples": [
            {
                "id": row.id,
                "characters": len(row.text),
                "text_sha256": hashlib.sha256(row.text.encode()).hexdigest(),
            }
            for row in selected
        ],
        "repeats": repeats,
        "warmup_review_id": warmup.id,
        "sample_reviews_with_explicit_cues": sum(
            any(pattern.search(row.text) for pattern in detector.patterns.values())
            for row in selected
        ),
        "models": {},
        "limitations": [
            "Latency only: no gold labels, accuracy or F1 measured.",
            "Sequential CPU calls in one process; excludes HTTP, rendering and database I/O.",
            "Initialization includes local integrity checks and lazy dependency/model loading.",
            "First inference is measured separately and excluded from warm timings.",
            "Warm repetitions reuse the same bounded sample; this is not a capacity/load test.",
            "The first request uses a review with explicit cues to exercise neural inference. "
            "Warm sample timings also include reviews without explicit cues.",
        ],
    }
    for model_id in model_ids:
        started = time.perf_counter()
        analyzer = registry.get(model_id)
        loading = time.perf_counter() - started
        first_started = time.perf_counter()
        analyzer.analyse(warmup.text, warmup.id, language="en")
        first = (time.perf_counter() - first_started) * 1000
        timings = []
        for _ in range(repeats):
            for row in selected:
                started = time.perf_counter()
                result = analyzer.analyse(row.text, row.id, language="en")
                timings.append((time.perf_counter() - started) * 1000)
                if result.model_id != model_id or not result.supported:
                    raise ValueError("Benchmark received an incompatible or unsupported result")
        report["models"][model_id] = {
            "spec": {k: v for k, v in registry.describe(model_id).items() if k != "path"},
            "initialization_seconds": loading,
            "first_inference_ms": first,
            "warm": {
                "requests": len(timings),
                "p50_ms": float(np.percentile(timings, 50)),
                "p95_ms": float(np.percentile(timings, 95)),
                "min_ms": min(timings),
                "max_ms": max(timings),
                "mean_ms": float(np.mean(timings)),
                "reviews_per_second": 1000 * len(timings) / sum(timings),
            },
            "warm_request_ms": timings,
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report
