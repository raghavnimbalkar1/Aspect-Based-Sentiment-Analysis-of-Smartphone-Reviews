from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from smartphone_absa.taxonomy import Sentiment


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    product_id: str
    product_name: str
    brand: str = "Unknown"
    condition: str = "unspecified"
    text: str = Field(min_length=1, max_length=30000)
    title: str = ""
    rating: float | None = Field(default=None, ge=1, le=5)
    date: str | None = None
    verified: bool | None = None
    language: str = "unknown"
    duplicate_group: str
    source: str = "csv-upload"


class Sentence(BaseModel):
    id: str
    text: str
    start: int
    end: int


class Evidence(BaseModel):
    sentence_id: str
    text: str
    start: int
    end: int
    sentiment: Sentiment
    score: float | None = None


class AspectResult(BaseModel):
    category: str
    sentiment: Sentiment
    evidence: list[Evidence]


class Analysis(BaseModel):
    model_id: str
    taxonomy_version: str
    aspects: list[AspectResult]
    sentences: list[Sentence]
    warnings: list[str] = Field(default_factory=list)
    language: str = "unknown"
    supported: bool = True


class SingleAnalysisRequest(BaseModel):
    text: str = Field(min_length=1, max_length=30000)
    model: str = Field(default="rules-v1", min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")


class JobRequest(BaseModel):
    model: str = Field(default="rules-v1", min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")


class ModelComparisonRequest(BaseModel):
    text: str = Field(min_length=1, max_length=30000)
    models: list[str] = Field(min_length=2, max_length=3)


class DatasetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class Annotation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentence_id: str
    review_id: str
    duplicate_group: str
    text: str
    category: str
    label: Sentiment
    annotator: str = Field(min_length=1)
    status: Literal["draft", "adjudicated"] = "draft"
    origin: Literal["human", "assisted", "synthetic"] = "human"
    taxonomy_version: str
    reference: Literal["explicit", "implicit", "none"] = "none"
    note: str = ""
