from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from smartphone_absa.data import file_hash
from smartphone_absa.research import (
    ExperimentBusy,
    ExperimentRequest,
    ResearchService,
    StudyRequest,
)


def research_router(service: ResearchService) -> APIRouter:
    router = APIRouter(prefix="/api")

    def report_path(name: str):
        path = next(
            (
                path
                for path in (service.artifacts / "experiments").glob("*/metrics.json")
                if path.parent.name == name
            ),
            None,
        )
        if path is None:
            raise HTTPException(404, "Experiment report not found")
        return path

    def predictions_path(name: str):
        report = report_path(name)
        metadata = json.loads(report.read_text()).get("prediction_artifact", {})
        path = report.parent / "predictions.jsonl"
        if not path.is_file() or not metadata.get("sha256"):
            raise HTTPException(404, "This report has no per-sentence predictions")
        if file_hash(path) != metadata["sha256"]:
            raise HTTPException(409, "Prediction artifact integrity check failed")
        return path

    @router.post("/annotations/studies", status_code=201)
    def create_study(body: StudyRequest):
        try:
            return service.create_study(body)
        except KeyError:
            raise HTTPException(404, "Dataset not found") from None

    @router.get("/experiments")
    def runs():
        return service.runs()

    @router.get("/experiments/training-assistance")
    def assistance():
        return service.assistance()

    @router.post("/experiments", status_code=202)
    def start(body: ExperimentRequest):
        try:
            return service.start(body)
        except KeyError:
            raise HTTPException(404, "Annotation study not found") from None
        except ExperimentBusy as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/experiments/reports/{name}")
    def report(name: str):
        # Resolve only known report names; never interpolate a URL value into a file path.
        return JSONResponse(
            json.loads(report_path(name).read_text()),
            headers={"Content-Disposition": 'attachment; filename="metrics.json"'},
        )

    @router.get("/experiments/reports/{name}/predictions/download")
    def download_predictions(name: str):
        return FileResponse(
            predictions_path(name), media_type="application/x-ndjson", filename="predictions.jsonl"
        )

    @router.get("/experiments/reports/{name}/predictions")
    def predictions(
        name: str,
        model: str = Query(min_length=1, max_length=100),
        split: Literal["validation", "test"] = "validation",
        category: str = "",
        kind: Literal[
            "errors", "all", "false_positive", "false_negative", "wrong_sentiment"
        ] = "errors",
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=25, ge=1, le=100),
    ):
        from smartphone_absa.taxonomy import CATEGORY_IDS

        if category and category not in CATEGORY_IDS:
            raise HTTPException(422, "Unknown aspect category")
        rows = []
        with predictions_path(name).open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if row["split"] != split or row["model_id"] != model:
                    continue
                if category and row["category"] != category:
                    continue
                if kind == "errors" and row["error_type"] == "correct":
                    continue
                if kind not in ("all", "errors") and row["error_type"] != kind:
                    continue
                rows.append(row)
        return {"total": len(rows), "offset": offset, "items": rows[offset : offset + limit]}

    return router
