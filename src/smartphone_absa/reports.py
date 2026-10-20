"""Validate local experiment reports before the dashboard or readiness checks use them."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from smartphone_absa.taxonomy import CATEGORY_IDS, LABELS, TAXONOMY_VERSION


class Score(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    true_positive: int = Field(ge=0)
    false_positive: int = Field(ge=0)
    false_negative: int = Field(ge=0)


class CategoryScore(Score):
    gold_support: int = Field(ge=0)
    predicted_support: int = Field(ge=0)


class Metrics(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="allow")
    tuple_micro: Score
    presence_micro: Score
    tuple_macro_f1: float = Field(ge=0, le=1)
    per_category: dict[str, CategoryScore]
    confusion_matrix: dict[str, dict[str, int]]
    sentences: int = Field(ge=1)
    pairs: int = Field(ge=1)

    @model_validator(mode="after")
    def complete_states(self):
        if set(self.per_category) != set(CATEGORY_IDS):
            raise ValueError("Report must include all aspect categories")
        if set(self.confusion_matrix) != set(LABELS) or any(
            set(row) != set(LABELS) or any(count < 0 for count in row.values())
            for row in self.confusion_matrix.values()
        ):
            raise ValueError("Report has an incomplete state confusion matrix")
        if (
            self.pairs != self.sentences * len(CATEGORY_IDS)
            or sum(sum(row.values()) for row in self.confusion_matrix.values()) != self.pairs
        ):
            raise ValueError("Report sentence, pair and confusion counts disagree")
        return self


class Reference(BaseModel):
    kind: str
    independent: bool
    sentences: int = Field(ge=0)
    human_only_sentences: int = Field(ge=0)
    assisted_sentences: int = Field(ge=0)
    label_rows_by_origin: dict[str, int]


class Coverage(BaseModel):
    expected_sentences: int | None = Field(default=None, ge=1)
    labelled_sentences: int = Field(ge=0)
    complete: bool


class PredictionArtifact(BaseModel):
    model_config = ConfigDict(extra="allow")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    rows: int = Field(ge=1)


class Development(BaseModel):
    model_config = ConfigDict(extra="allow")
    reference_previously_inspected: bool
    protocol_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    trial: int = Field(ge=1)


class Report(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="allow")
    model_id: str = Field(min_length=1)
    taxonomy_version: str
    annotations_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    training_sentences: int = Field(ge=0)
    elapsed_seconds: float = Field(ge=0)
    validation: dict[str, Metrics] = Field(min_length=1)
    test_evaluated: bool
    test: dict[str, Metrics] | None = None
    warnings: list[str] | None = None
    evaluation_reference: dict[str, Reference] | None = None
    evaluation_coverage: dict[str, Coverage] | None = None
    prediction_artifact: PredictionArtifact | None = None
    development: Development | None = None

    @model_validator(mode="after")
    def compatible(self):
        if self.taxonomy_version != TAXONOMY_VERSION:
            raise ValueError("Report taxonomy differs from the application")
        if self.test_evaluated != bool(self.test):
            raise ValueError("Report test marker and test results disagree")
        return self


def load_report(path: Path) -> dict:
    report = json.loads(path.read_text())
    return Report.model_validate(report).model_dump(mode="json", exclude_unset=True)


def report_catalog(artifacts: Path) -> tuple[list[dict], list[dict]]:
    reports, errors = [], []
    paths = sorted(
        (artifacts / "experiments").glob("*/metrics.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    for path in paths:
        try:
            reports.append({**load_report(path), "experiment": path.parent.name})
        except (ValueError, OSError):
            errors.append({"experiment": path.parent.name, "error": "Incomplete or invalid report"})
    return reports, errors


def independent_test_complete(report: dict) -> bool:
    """A boolean marker alone cannot establish a completed human test evaluation."""
    reference = (report.get("evaluation_reference") or {}).get("test", {})
    coverage = (report.get("evaluation_coverage") or {}).get("test", {})
    expected = coverage.get("expected_sentences", 0)
    return bool(
        report.get("test_evaluated")
        and report.get("test")
        and isinstance(expected, int)
        and expected > 0
        and coverage.get("complete") is True
        and coverage.get("labelled_sentences") == expected
        and reference.get("kind") == "independent_human"
        and reference.get("independent") is True
        and reference.get("sentences") == expected
        and reference.get("human_only_sentences") == expected
        and reference.get("assisted_sentences") == 0
        and reference.get("label_rows_by_origin") == {"human": expected * len(CATEGORY_IDS)}
        and all(metric["sentences"] == expected for metric in report["test"].values())
    )
