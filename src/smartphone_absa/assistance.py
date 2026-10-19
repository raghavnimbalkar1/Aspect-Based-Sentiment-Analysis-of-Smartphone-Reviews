"""Training-only pseudo labels; holdouts and the blind human workbench stay untouched."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from pathlib import Path

from smartphone_absa.annotations import read_annotations
from smartphone_absa.data import file_hash
from smartphone_absa.models.registry import ModelRegistry
from smartphone_absa.taxonomy import CATEGORY_IDS, TAXONOMY_VERSION
from smartphone_absa.workbench import AnnotationWorkbench


def prepare_assistance(
    workbench: AnnotationWorkbench, set_id: str, registry: ModelRegistry, model_id: str
) -> dict:
    if not any(study["id"] == set_id for study in workbench.sets()):
        raise ValueError("Unknown annotation study")
    output = registry.artifacts / "training-assistance" / set_id
    if output.exists():
        raise ValueError("Assisted training export already exists; preserve its provenance")
    with workbench.store.connection() as db:
        manifest = json.loads(
            db.execute(
                "SELECT manifest_json FROM annotation_sets WHERE id=?", (set_id,)
            ).fetchone()[0]
        )
    tasks = [task for task in workbench.tasks(set_id) if task["split"] == "train"]
    if not tasks:
        raise ValueError("This study has no training sentences")
    if registry.describe(model_id)["kind"] != "transferred_absa":
        raise ValueError("Use the pinned transferred model for training assistance")
    analyzer = registry.get(model_id)
    rows = []
    for task in tasks:
        result = analyzer.analyse(task["text"], task["sentence_id"], language="en")
        predictions = {aspect.category: aspect.sentiment for aspect in result.aspects}
        if not result.supported or result.model_id != model_id:
            raise ValueError("Training assistant returned an incompatible result")
        for category in CATEGORY_IDS:
            label = predictions.get(category, "absent")
            rows.append(
                {
                    **{
                        key: task[key]
                        for key in ("sentence_id", "review_id", "duplicate_group", "split", "text")
                    },
                    "category": category,
                    "label": label,
                    "annotator": f"model:{model_id}",
                    "status": "generated",
                    "origin": "assisted",
                    "taxonomy_version": TAXONOMY_VERSION,
                    "reference": "none" if label == "absent" else "explicit",
                    "note": "Machine-generated training label; not human adjudication. "
                    "Explicit-cue teacher may miss implicit aspects.",
                }
            )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    output.mkdir(parents=True)
    (output / "labels.csv").write_text(buffer.getvalue(), encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    provenance = {
        "set_id": set_id,
        "origin": "assisted",
        "status": "generated",
        "training_sentences": len(tasks),
        "training_pairs": len(rows),
        "labels_sha256": file_hash(output / "labels.csv"),
        "manifest_sha256": file_hash(output / "manifest.json"),
        "teacher": {k: v for k, v in registry.describe(model_id).items() if k != "path"},
        "label_counts": dict(Counter(row["label"] for row in rows)),
        "policy": "Only frozen training sentences are inferred. No holdout labels generated. "
        "Blind human tasks remain blank. Human training labels take precedence when fitting.",
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return provenance


def available_assistance(workbench: AnnotationWorkbench, artifacts: Path) -> list[dict]:
    result = []
    for study in workbench.sets():
        folder = artifacts / "training-assistance" / study["id"]
        try:
            provenance = json.loads((folder / "provenance.json").read_text())
            if (
                provenance["set_id"] != study["id"]
                or file_hash(folder / "labels.csv") != provenance["labels_sha256"]
                or file_hash(folder / "manifest.json") != provenance["manifest_sha256"]
            ):
                continue
            manifest = json.loads((folder / "manifest.json").read_text())
            if manifest["tasks_sha256"][:24] != study["id"]:
                continue
            rows = read_annotations(
                folder / "labels.csv", folder / "manifest.json", allow_assisted_train=True
            )
            if any(row["split"] != "train" or row["origin"] != "assisted" for row in rows):
                continue
            result.append(provenance)
        except (OSError, ValueError, KeyError):
            continue
    return result
