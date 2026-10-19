"""Local study preparation and background experiments with immutable label snapshots."""

from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from smartphone_absa.annotations import export_tasks, read_annotations
from smartphone_absa.assistance import available_assistance
from smartphone_absa.data import file_hash
from smartphone_absa.domain import Review
from smartphone_absa.experiments import evaluate_models, train_tfidf
from smartphone_absa.models.registry import ModelRegistry, ModelUnavailable
from smartphone_absa.store import Store
from smartphone_absa.workbench import AnnotationWorkbench

log = logging.getLogger(__name__)


class ExperimentBusy(ValueError):
    pass


class StudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    sentences: int = Field(default=300, ge=1, le=2000)
    pilot: bool = False


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: str = Field(min_length=1, max_length=64)
    kind: Literal["compare", "train_tfidf"]
    models: list[str] = Field(default_factory=list, max_length=3)
    assisted_training: bool = False
    assisted_validation: bool = False


class ResearchService:
    def __init__(
        self, store: Store, artifacts: Path, registry: ModelRegistry, executor: ThreadPoolExecutor
    ):
        self.store = store
        self.artifacts = artifacts
        self.registry = registry
        self.executor = executor
        self.workbench = AnnotationWorkbench(store)

    def create_study(self, body: StudyRequest) -> dict:
        dataset = self.store.dataset(body.dataset_id)
        if not dataset:
            raise KeyError("Dataset not found")
        if not body.name.strip():
            raise ValueError("Enter a study name")

        def prepare():
            with self.store.connection() as db:
                rows = db.execute(
                    "SELECT payload_json FROM reviews WHERE dataset_id=? ORDER BY id",
                    (body.dataset_id,),
                ).fetchall()
            reviews = [Review.model_validate_json(row[0]) for row in rows]
            destination = self.artifacts / "annotation-tasks" / uuid.uuid4().hex / "tasks.csv"
            manifest = export_tasks(reviews, destination, body.sentences, pilot=body.pilot)
            if not manifest["sentences"]:
                raise ValueError("No eligible English reviews in this selection")
            manifest.update(
                source_dataset_id=body.dataset_id, source_dataset_fingerprint=dataset["fingerprint"]
            )
            sidecar = destination.with_suffix(".manifest.json")
            sidecar.write_text(json.dumps(manifest, indent=2) + "\n")
            return self.workbench.import_tasks(destination, sidecar, body.name)

        # Study preparation shares the single heavy-work queue with model inference/training.
        return self.executor.submit(prepare).result()

    @staticmethod
    def decode(row) -> dict:
        result = dict(row)
        result["config"] = json.loads(result.pop("config_json"))
        return result

    def runs(self) -> list[dict]:
        with self.store.connection() as db:
            return [
                self.decode(row)
                for row in db.execute(
                    "SELECT r.*,s.name AS study_name FROM experiment_runs r "
                    "JOIN annotation_sets s ON s.id=r.set_id "
                    "ORDER BY r.created_at DESC,r.rowid DESC "
                    "LIMIT 50"
                )
            ]

    def assistance(self) -> list[dict]:
        return available_assistance(self.workbench, self.artifacts)

    def start(self, body: ExperimentRequest) -> dict:
        study = next((item for item in self.workbench.sets() if item["id"] == body.set_id), None)
        if study is None:
            raise KeyError("Annotation study not found")
        validation = study["partitions"].get("validation", {})
        if not validation.get("total"):
            raise ValueError(
                "Choose a full study with validation sentences; the pilot is train-only"
            )
        if validation["completed"] != validation["total"]:
            raise ValueError(
                "Complete all validation sentences in the frozen study before evaluation"
            )
        if body.kind == "compare":
            if body.assisted_training:
                raise ValueError("Training assistance is only applicable to TF-IDF training")
            if not body.models or len(body.models) != len(set(body.models)):
                raise ValueError("Choose one to three different installed models")
            for model_id in body.models:
                if not self.registry.describe(model_id)["available"]:
                    raise ModelUnavailable("A selected model is not installed")
        elif body.models:
            raise ValueError("TF-IDF training uses its fixed baseline comparison")
        # Snapshot completed labels at submission, before any background work is queued.
        bundle = self.workbench.export(body.set_id)
        run_id = uuid.uuid4().hex
        inputs = self.artifacts / "experiment-inputs" / run_id
        inputs.mkdir(parents=True)
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            for name in ("annotations.csv", "annotations.manifest.json"):
                (inputs / name).write_bytes(archive.read(name))
        rows = read_annotations(
            inputs / "annotations.csv",
            inputs / "annotations.manifest.json",
            allow_assisted_validation=body.assisted_validation,
        )
        counts = {
            split: len({row["sentence_id"] for row in rows if row["split"] == split})
            for split in ("train", "validation", "test")
        }
        if counts["validation"] != validation["total"]:
            raise ValueError(
                "Validation labels changed during submission; review the study and retry"
            )
        if not counts["validation"]:
            raise ValueError(
                "Complete human validation labels in a full study; the pilot is train-only"
            )
        assistance = None
        if body.assisted_training:
            assistance = next(
                (item for item in self.assistance() if item["set_id"] == body.set_id), None
            )
            if assistance is None:
                raise ValueError("No verified assisted training export for this study")
            source = self.artifacts / "training-assistance" / body.set_id
            (inputs / "assisted-training.csv").write_bytes((source / "labels.csv").read_bytes())
            (inputs / "assistance-provenance.json").write_bytes(
                (source / "provenance.json").read_bytes()
            )
            if file_hash(inputs / "assisted-training.csv") != assistance["labels_sha256"]:
                raise ValueError("Assisted training export changed during submission")
            assisted = read_annotations(
                inputs / "assisted-training.csv",
                inputs / "annotations.manifest.json",
                allow_assisted_train=True,
            )
            if any(row["split"] != "train" or row["origin"] != "assisted" for row in assisted):
                raise ValueError("Assisted labels must be confined to training")
        if body.kind == "train_tfidf" and not counts["train"] and assistance is None:
            raise ValueError("Complete human training labels before training TF-IDF")
        config = {
            "models": body.models,
            "assisted_validation": body.assisted_validation,
            "completed_sentences": counts,
            "annotations_sha256": file_hash(inputs / "annotations.csv"),
            "manifest_sha256": file_hash(inputs / "annotations.manifest.json"),
            "test_evaluated": False,
            "experiment": f"{body.kind.replace('_', '-')}-{run_id[:12]}",
            "assisted_training_sha256": assistance["labels_sha256"] if assistance else None,
            "assistance_provenance_sha256": file_hash(inputs / "assistance-provenance.json")
            if assistance
            else None,
        }
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT id FROM experiment_runs WHERE set_id=? AND status IN ('queued','running')",
                (body.set_id,),
            ).fetchone():
                raise ExperimentBusy("This study already has an active experiment")
            db.execute(
                "INSERT INTO experiment_runs(id,set_id,kind,status,config_json) "
                "VALUES (?,?,?,'queued',?)",
                (run_id, body.set_id, body.kind, json.dumps(config)),
            )
        try:
            self.executor.submit(self.execute, run_id)
        except RuntimeError:
            self.update(run_id, "failed", "Application is shutting down; start a new run.")
            raise ValueError("Application is shutting down") from None
        return next(run for run in self.runs() if run["id"] == run_id)

    def update(self, run_id: str, status: str, error: str | None = None) -> None:
        with self.store.connection() as db:
            db.execute(
                "UPDATE experiment_runs SET status=?,error=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                (status, error, run_id),
            )

    def execute(self, run_id: str) -> None:
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM experiment_runs WHERE id=?", (run_id,)).fetchone()
        run = self.decode(row)
        config = run["config"]
        inputs = self.artifacts / "experiment-inputs" / run_id
        annotations, manifest = inputs / "annotations.csv", inputs / "annotations.manifest.json"
        self.update(run_id, "running")
        try:
            if (
                file_hash(annotations) != config["annotations_sha256"]
                or file_hash(manifest) != config["manifest_sha256"]
            ):
                raise ValueError("Experiment input snapshot changed; start a new run")
            output = self.artifacts / "experiments" / config["experiment"]
            if run["kind"] == "train_tfidf":
                assisted_training = None
                if config.get("assisted_training_sha256"):
                    assisted_training = inputs / "assisted-training.csv"
                    if (
                        file_hash(assisted_training) != config["assisted_training_sha256"]
                        or file_hash(inputs / "assistance-provenance.json")
                        != config["assistance_provenance_sha256"]
                    ):
                        raise ValueError("Assisted input snapshot changed; start a new run")
                report = train_tfidf(
                    annotations,
                    manifest,
                    output,
                    assisted_training=assisted_training,
                    allow_assisted_validation=config.get("assisted_validation", False),
                )
            else:
                report = evaluate_models(
                    annotations,
                    manifest,
                    output,
                    config["models"],
                    self.registry,
                    allow_assisted_validation=config.get("assisted_validation", False),
                )
            report["study_snapshot"] = {"set_id": run["set_id"], **config}
            (output / "metrics.json").write_text(json.dumps(report, indent=2) + "\n")
            self.update(run_id, "completed")
        except ValueError as exc:
            log.warning("Experiment %s rejected: %s", run_id, exc)
            self.update(run_id, "failed", str(exc))
        except Exception:
            log.exception("Experiment %s failed", run_id)
            self.update(run_id, "failed", "Experiment failed. See the local server log.")

    def interrupt(self) -> None:
        with self.store.connection() as db:
            db.execute(
                "UPDATE experiment_runs SET status='interrupted',"
                "error='Application stopped. Input snapshots are preserved; start a new run.' "
                "WHERE status IN ('queued','running')"
            )
