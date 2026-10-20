from __future__ import annotations

import importlib.util
import json
import re
import threading
from pathlib import Path

from smartphone_absa.baseline import MODEL_ID, RuleBaseline
from smartphone_absa.data import file_hash
from smartphone_absa.models.checkpoints import CHECKPOINT, REVISION, TRANSFER_FILES, TRANSFER_ID
from smartphone_absa.models.domain_adapter import ADAPTER_SHA256, CONFIG_SHA256, DOMAIN_ID
from smartphone_absa.models.inference import Analyzer
from smartphone_absa.taxonomy import TAXONOMY_VERSION


class ModelUnavailable(ValueError):
    pass


class ModelRegistry:
    def __init__(self, artifacts: Path, device: str = "cpu"):
        self.artifacts = artifacts
        self.device = device
        self.loaded: dict[str, Analyzer] = {MODEL_ID: RuleBaseline()}
        self.lock = threading.RLock()

    def specs(self) -> list[dict]:
        checkpoint = self.artifacts / "models" / TRANSFER_ID
        dependencies = all(
            importlib.util.find_spec(name) is not None
            for name in ("torch", "transformers", "sentencepiece")
        )
        ready = (
            (checkpoint / "checkpoint.json").exists()
            and all((checkpoint / name).is_file() for name in TRANSFER_FILES)
            and dependencies
        )
        result = [
            {
                "id": MODEL_ID,
                "name": "Rules + VADER",
                "kind": "rule_baseline",
                "available": True,
                "description": "Explicit aspect cues and clause-local sentiment rules.",
                "device": "cpu",
            },
            {
                "id": TRANSFER_ID,
                "name": "DeBERTa ABSA · transferred",
                "kind": "transferred_absa",
                "available": ready,
                "description": "Explicit aspects with a local transformer sentiment model.",
                "device": self.device,
                "path": str(checkpoint),
                "smartphone_finetuned": False,
                "checkpoint": CHECKPOINT,
                "revision": REVISION,
                "adapter_version": 1,
                "license": "MIT",
                "setup": "make model-setup",
            },
        ]
        result.append(
            {
                **result[1],
                "id": DOMAIN_ID,
                "name": "DeBERTa ABSA · domain adapter v2",
                "kind": "domain_absa",
                "description": "Shared transformer with expanded domain vocabulary "
                "and opinion scope.",
                "adapter_version": 2,
                "adapter_sha256": ADAPTER_SHA256,
                "configuration_sha256": CONFIG_SHA256,
                "shared_backbone": TRANSFER_ID,
                "development_tuned": True,
            }
        )
        for metadata in sorted((self.artifacts / "experiments").glob("*/model-info.json")):
            try:
                info = json.loads(metadata.read_text())
                if (
                    info["taxonomy_version"] == TAXONOMY_VERSION
                    and info["kind"] == "tfidf"
                    and re.fullmatch(r"tfidf-[a-f0-9]{12}", info["id"])
                    and (metadata.parent / "model.joblib").exists()
                ):
                    result.append(
                        {
                            **info,
                            "available": True,
                            "path": str(metadata.parent),
                            "name": f"TF-IDF · {info.get('training_profile', 'flat')} · "
                            f"{metadata.parent.name}",
                            "device": "cpu",
                        }
                    )
            except (ValueError, KeyError, OSError):
                continue
        return result

    def describe(self, model_id: str) -> dict:
        spec = next((spec for spec in self.specs() if spec["id"] == model_id), None)
        if spec is None:
            raise ValueError("Unknown model ID")
        return spec

    def get(self, model_id: str) -> Analyzer:
        with self.lock:
            if model_id in self.loaded:
                return self.loaded[model_id]
            spec = self.describe(model_id)
            if not spec["available"]:
                raise ModelUnavailable(
                    "Model is not installed. Run the setup command shown in Models."
                )
            path = Path(spec["path"])
            if spec["kind"] == "domain_absa":
                from smartphone_absa.models.domain_adapter import DomainABSA

                analyzer = DomainABSA(self.get(TRANSFER_ID))
            elif spec["kind"] == "transferred_absa":
                from smartphone_absa.models.inference import TransferredABSA

                info = json.loads((path / "checkpoint.json").read_text())
                if info.get("revision") != REVISION:
                    raise ValueError("Checkpoint revision differs from the pinned model")
                for name in TRANSFER_FILES:
                    if file_hash(path / name) != info["files"][name]["sha256"]:
                        raise ValueError(f"Checkpoint integrity check failed: {name}")
                analyzer = TransferredABSA(path, model_id, self.device)
            else:
                from smartphone_absa.models.inference import TfidfAnalyzer

                digest = file_hash(path / "model.joblib")
                if digest != spec["model_sha256"] or model_id != f"tfidf-{digest[:12]}":
                    raise ValueError("Trained classifier integrity check failed")
                analyzer = TfidfAnalyzer(path, model_id)
            self.loaded[model_id] = analyzer
            return analyzer
