from __future__ import annotations

import re
import threading
from collections import defaultdict
from pathlib import Path
from typing import Protocol

from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.domain import Analysis, AspectResult, Evidence
from smartphone_absa.taxonomy import CATEGORIES, TAXONOMY_VERSION, aggregate_sentiments
from smartphone_absa.text import detect_language, split_sentences


class Analyzer(Protocol):
    id: str

    def analyse(
        self, text: str, review_id: str = "input", language: str | None = None
    ) -> Analysis: ...


def explicit_pairs(text: str, detector: RuleBaseline) -> list[tuple[str, str, str]]:
    """Return category, local clause, and actual cue; never borrow VADER's sentiment."""
    clauses = re.split(r"\b(?:but|however|although|yet|whereas)\b|[;\n]", text, flags=re.I)
    pairs = []
    for clause in clauses:
        parts = re.split(r"\band\b", clause, flags=re.I)
        if len(parts) < 2 or not all(
            any(p.search(part) for p in detector.patterns.values()) for part in parts
        ):
            parts = [clause]
        for part in parts:
            for category, pattern in detector.patterns.items():
                match = pattern.search(part)
                if match:
                    pairs.append((category, part.strip(), match.group()))
    return pairs


class TransferredABSA:
    """Three-state sentiment checkpoint with explicit candidates and review aggregation."""

    def __init__(self, path: Path, model_id: str, device: str = "cpu"):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self.id = model_id
        self.device = device
        self._lock = threading.Lock()
        self.detector = RuleBaseline()
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, use_fast=False)
        self.model = (
            AutoModelForSequenceClassification.from_pretrained(
                path,
                local_files_only=True,
                use_safetensors=True,
            )
            .to(device)
            .eval()
        )
        self.labels = {
            int(index): label.lower() for index, label in self.model.config.id2label.items()
        }
        if set(self.labels.values()) != {"positive", "negative", "neutral"}:
            raise ValueError("Transferred checkpoint has an unexpected sentiment label mapping")
        self.torch = torch

    def classify(self, pairs: list[tuple[str, str, str]]) -> list[tuple[str, float]]:
        if not pairs:
            return []
        # Reject oversized clauses explicitly rather than silently truncating an aspect/opinion.
        encoded = self.tokenizer(
            [text for _, text, _ in pairs],
            [aspect for _, _, aspect in pairs],
            padding=True,
            truncation=False,
            return_tensors="pt",
        )
        if encoded["input_ids"].shape[1] > 512:
            raise ValueError("A clause exceeds the transformer's 512-token limit; use shorter text")
        result = []
        with self._lock, self.torch.inference_mode():
            for start in range(0, len(pairs), 8):
                batch = {
                    key: value[start : start + 8].to(self.device) for key, value in encoded.items()
                }
                probabilities = self.model(**batch).logits.softmax(dim=-1).cpu()
                for row in probabilities:
                    index = int(row.argmax())
                    result.append((self.labels[index], float(row[index])))
        return result

    def analyse(self, text: str, review_id: str = "input", language: str | None = None) -> Analysis:
        language = language or detect_language(text)
        if language not in ("en", "unknown"):
            return Analysis(
                model_id=self.id,
                taxonomy_version=TAXONOMY_VERSION,
                aspects=[],
                sentences=[],
                language=language,
                supported=False,
                warnings=["This application currently supports English reviews."],
            )
        sentences = split_sentences(text, review_id)
        grouped: dict[str, list[Evidence]] = defaultdict(list)
        for sentence in sentences:
            pairs = explicit_pairs(sentence.text, self.detector)
            predictions = self.classify(pairs)
            local: dict[str, list[tuple[str, float]]] = defaultdict(list)
            for (category, _, _), prediction in zip(pairs, predictions, strict=True):
                local[category].append(prediction)
            for category, values in local.items():
                grouped[category].append(
                    Evidence(
                        sentence_id=sentence.id,
                        text=sentence.text,
                        start=sentence.start,
                        end=sentence.end,
                        sentiment=aggregate_sentiments([label for label, _ in values]),
                        score=sum(score for _, score in values) / len(values),
                    )
                )
        warnings = [
            "Transferred checkpoint; not fine-tuned on this smartphone corpus.",
            "Aspect detection uses explicit cues. Implicit aspects may be missed.",
            "Mixed combines opposing clause predictions; scores are uncalibrated.",
        ]
        if language == "unknown":
            warnings.append("Language identification is uncertain for this short text.")
        return Analysis(
            model_id=self.id,
            taxonomy_version=TAXONOMY_VERSION,
            sentences=sentences,
            language=language,
            warnings=warnings,
            aspects=[
                AspectResult(
                    category=category.id,
                    evidence=grouped[category.id],
                    sentiment=aggregate_sentiments(
                        [item.sentiment for item in grouped[category.id]]
                    ),
                )
                for category in CATEGORIES
                if category.id in grouped
            ],
        )


class TfidfAnalyzer:
    def __init__(self, directory: Path, model_id: str):
        import joblib

        self.id = model_id
        # Only files produced by the local training command enter the registry.
        self.artifact = joblib.load(directory / "model.joblib")
        if self.artifact["taxonomy_version"] != TAXONOMY_VERSION:
            raise ValueError("Trained model taxonomy is incompatible with this application")

    def analyse(self, text: str, review_id: str = "input", language: str | None = None) -> Analysis:
        language = language or detect_language(text)
        if language not in ("en", "unknown"):
            return Analysis(
                model_id=self.id,
                taxonomy_version=TAXONOMY_VERSION,
                aspects=[],
                sentences=[],
                language=language,
                supported=False,
                warnings=["This application currently supports English reviews."],
            )
        sentences = split_sentences(text, review_id)
        if not sentences:
            return Analysis(
                model_id=self.id,
                taxonomy_version=TAXONOMY_VERSION,
                aspects=[],
                sentences=[],
                language=language,
            )
        matrix = self.artifact["vectorizer"].transform([sentence.text for sentence in sentences])
        aspects = []
        for category in CATEGORIES:
            labels = self.artifact["models"][category.id].predict(matrix)
            evidence = [
                Evidence(
                    sentence_id=sentence.id,
                    text=sentence.text,
                    start=sentence.start,
                    end=sentence.end,
                    sentiment=label,
                )
                for sentence, label in zip(sentences, labels, strict=True)
                if label != "absent"
            ]
            if evidence:
                aspects.append(
                    AspectResult(
                        category=category.id,
                        evidence=evidence,
                        sentiment=aggregate_sentiments([item.sentiment for item in evidence]),
                    )
                )
        return Analysis(
            model_id=self.id,
            taxonomy_version=TAXONOMY_VERSION,
            aspects=aspects,
            sentences=sentences,
            language=language,
            warnings=["Local TF-IDF classifier; inspect the linked experiment report."],
        )
