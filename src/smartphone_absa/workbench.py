"""Blind, durable sentence annotation with frozen identities and edit history."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from smartphone_absa.data import file_hash
from smartphone_absa.store import Store
from smartphone_absa.taxonomy import CATEGORY_IDS, LABELS, TAXONOMY_VERSION


class RevisionConflict(ValueError):
    pass


class LabelEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: Literal["absent", "positive", "negative", "neutral", "mixed"]
    reference: Literal["explicit", "implicit", "none"]


class AnnotationEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0)
    annotator: str = Field(min_length=1, max_length=100)
    status: Literal["draft", "adjudicated"] = "draft"
    labels: dict[str, LabelEdit]
    note: str = Field(default="", max_length=3000)


class AnnotationWorkbench:
    def __init__(self, store: Store):
        self.store = store

    def import_tasks(self, path: Path, manifest_path: Path, name: str) -> dict:
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("taxonomy_version") != TAXONOMY_VERSION:
            raise ValueError("Annotation taxonomy differs from the application taxonomy")
        if file_hash(path) != manifest.get("tasks_sha256"):
            raise ValueError("Task file differs from the frozen, blank export")
        tasks: dict[str, dict] = {}
        categories = defaultdict(set)
        groups = defaultdict(set)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row["label"] or row["annotator"] or row["category"] not in CATEGORY_IDS:
                    raise ValueError("Import an untouched blank task export; labels stay in SQLite")
                if row["taxonomy_version"] != TAXONOMY_VERSION:
                    raise ValueError("Unknown task taxonomy")
                task = {
                    key: row[key]
                    for key in ("sentence_id", "review_id", "duplicate_group", "split", "text")
                }
                sid, rid = task["sentence_id"], task["review_id"]
                if (
                    task["split"] not in ("train", "validation", "test")
                    or task["split"] != manifest["split_by_review"].get(rid)
                    or task["duplicate_group"] != manifest["group_by_review"].get(rid)
                    or hashlib.sha256(task["text"].encode()).hexdigest()
                    != manifest["sentence_hashes"].get(sid)
                ):
                    raise ValueError("Task changed the frozen text, split, or duplicate group")
                if sid in tasks and tasks[sid] != task:
                    raise ValueError("Inconsistent sentence identity")
                if row["category"] in categories[sid]:
                    raise ValueError("Duplicate category row")
                tasks[sid] = task
                categories[sid].add(row["category"])
                groups[task["duplicate_group"]].add(task["split"])
        if not tasks or any(value != set(CATEGORY_IDS) for value in categories.values()):
            raise ValueError("Each sentence must contain all ten category tasks")
        if any(len(value) != 1 for value in groups.values()):
            raise ValueError("Duplicate-group leakage across splits")
        set_id = manifest["tasks_sha256"][:24]
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT id FROM annotation_sets WHERE id=?", (set_id,)).fetchone()
            if not existing:
                db.execute(
                    "INSERT INTO annotation_sets(id,name,manifest_json) VALUES (?,?,?)",
                    (set_id, name.strip()[:120] or path.stem, json.dumps(manifest)),
                )
                db.executemany(
                    "INSERT INTO annotation_tasks(set_id,sentence_id,position,task_json) "
                    "VALUES (?,?,?,?)",
                    [
                        (set_id, sid, index, json.dumps(task))
                        for index, (sid, task) in enumerate(tasks.items())
                    ],
                )
        return next(item for item in self.sets() if item["id"] == set_id)

    def sets(self) -> list[dict]:
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT s.id,s.name,s.manifest_json,COUNT(t.sentence_id) AS total,"
                "SUM(CASE WHEN t.status='adjudicated' THEN 1 ELSE 0 END) AS completed,"
                "SUM(CASE WHEN t.revision>0 AND t.status='draft' THEN 1 ELSE 0 END) AS drafts "
                "FROM annotation_sets s JOIN annotation_tasks t ON t.set_id=s.id "
                "GROUP BY s.id ORDER BY s.created_at DESC"
            ).fetchall()
            partition_rows = db.execute(
                "SELECT set_id,json_extract(task_json,'$.split') AS split,COUNT(*) AS total,"
                "SUM(CASE WHEN status='adjudicated' THEN 1 ELSE 0 END) AS completed "
                "FROM annotation_tasks GROUP BY set_id,split"
            ).fetchall()
        result = []
        for row in rows:
            manifest = json.loads(row["manifest_json"])
            partitions = {
                part["split"]: {"total": part["total"], "completed": part["completed"]}
                for part in partition_rows
                if part["set_id"] == row["id"]
            }
            result.append(
                {
                    **{k: v for k, v in dict(row).items() if k != "manifest_json"},
                    "pilot_train_only": manifest["pilot_train_only"],
                    "partitions": partitions,
                    "dataset_id": manifest.get("source_dataset_id"),
                }
            )
        return result

    @staticmethod
    def decode(row) -> dict:
        result = dict(row)
        result.update(json.loads(result.pop("task_json")))
        result["labels"] = json.loads(result.pop("labels_json"))
        return result

    def tasks(self, set_id: str, status: str = "all") -> list[dict]:
        if status not in ("all", "pending", "adjudicated"):
            raise ValueError("Unknown annotation status")
        with self.store.connection() as db:
            if not db.execute("SELECT id FROM annotation_sets WHERE id=?", (set_id,)).fetchone():
                raise KeyError("Annotation set not found")
            rows = db.execute(
                "SELECT * FROM annotation_tasks WHERE set_id=? "
                + (
                    "AND status='draft' "
                    if status == "pending"
                    else "AND status='adjudicated' "
                    if status == "adjudicated"
                    else ""
                )
                + "ORDER BY position",
                (set_id,),
            ).fetchall()
        return [self.decode(row) for row in rows]

    def save(self, set_id: str, sentence_id: str, edit: AnnotationEdit) -> dict:
        if not edit.annotator.strip():
            raise ValueError("Enter an annotator name")
        if not set(edit.labels) <= set(CATEGORY_IDS):
            raise ValueError("Unknown aspect category")
        if edit.status == "adjudicated" and set(edit.labels) != set(CATEGORY_IDS):
            raise ValueError(
                "Complete all ten category states before marking the sentence complete"
            )
        for state in edit.labels.values():
            if state.label not in LABELS or (
                (state.label == "absent") != (state.reference == "none")
            ):
                raise ValueError(
                    "Absent needs reference none; present aspects need explicit or implicit"
                )
        payload = edit.model_dump(mode="json")
        # Blind input excludes model suggestions, ratings, and editable task identities.
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM annotation_tasks WHERE set_id=? AND sentence_id=?",
                (set_id, sentence_id),
            ).fetchone()
            if not row:
                raise KeyError("Sentence task not found")
            if row["revision"] != edit.revision:
                raise RevisionConflict("This sentence was edited elsewhere. Reload before saving.")
            revision = edit.revision + 1
            db.execute(
                "UPDATE annotation_tasks SET labels_json=?,annotator=?,note=?,status=?,"
                "revision=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                "WHERE set_id=? AND sentence_id=?",
                (
                    json.dumps(payload["labels"]),
                    edit.annotator.strip(),
                    edit.note,
                    edit.status,
                    revision,
                    set_id,
                    sentence_id,
                ),
            )
            db.execute(
                "INSERT INTO annotation_history(set_id,sentence_id,revision,payload_json) "
                "VALUES (?,?,?,?)",
                (set_id, sentence_id, revision, json.dumps(payload)),
            )
            updated = db.execute(
                "SELECT * FROM annotation_tasks WHERE set_id=? AND sentence_id=?",
                (set_id, sentence_id),
            ).fetchone()
            return self.decode(updated)

    def history(self, set_id: str, sentence_id: str) -> list[dict]:
        with self.store.connection() as db:
            return [
                {**dict(row), "edit": json.loads(row["payload_json"])}
                for row in db.execute(
                    "SELECT revision,payload_json,created_at FROM annotation_history "
                    "WHERE set_id=? AND sentence_id=? ORDER BY revision DESC",
                    (set_id, sentence_id),
                )
            ]

    def export(self, set_id: str) -> bytes:
        tasks = self.tasks(set_id, "adjudicated")
        if not tasks:
            raise ValueError("No completed sentences to export")
        with self.store.connection() as db:
            manifest = json.loads(
                db.execute(
                    "SELECT manifest_json FROM annotation_sets WHERE id=?", (set_id,)
                ).fetchone()[0]
            )
        handle = io.StringIO(newline="")
        fields = [
            "sentence_id",
            "review_id",
            "duplicate_group",
            "split",
            "text",
            "category",
            "label",
            "annotator",
            "status",
            "origin",
            "taxonomy_version",
            "reference",
            "note",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for task in tasks:
            for category in CATEGORY_IDS:
                writer.writerow(
                    {
                        **{
                            key: task[key]
                            for key in (
                                "sentence_id",
                                "review_id",
                                "duplicate_group",
                                "split",
                                "text",
                            )
                        },
                        "category": category,
                        **task["labels"][category],
                        "annotator": task["annotator"],
                        "status": "adjudicated",
                        "origin": "human",
                        "taxonomy_version": TAXONOMY_VERSION,
                        "note": task["note"],
                    }
                )
        manifest["workbench_export"] = {
            "completed_sentences": len(tasks),
            "single_annotator_possible": True,
            "inter_annotator_agreement_measured": False,
        }
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("annotations.csv", handle.getvalue())
            bundle.writestr("annotations.manifest.json", json.dumps(manifest, indent=2) + "\n")
        return output.getvalue()
