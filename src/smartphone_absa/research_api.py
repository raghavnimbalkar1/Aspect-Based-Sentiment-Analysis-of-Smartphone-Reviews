from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from smartphone_absa.research import (
    ExperimentBusy,
    ExperimentRequest,
    ResearchService,
    StudyRequest,
)


def research_router(service: ResearchService) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.post("/annotations/studies", status_code=201)
    def create_study(body: StudyRequest):
        try:
            return service.create_study(body)
        except KeyError:
            raise HTTPException(404, "Dataset not found") from None

    @router.get("/experiments")
    def runs():
        return service.runs()

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
        import json

        return JSONResponse(
            json.loads(path.read_text()),
            headers={"Content-Disposition": 'attachment; filename="metrics.json"'},
        )

    return router
