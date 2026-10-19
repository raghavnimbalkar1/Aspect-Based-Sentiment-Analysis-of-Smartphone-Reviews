from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from smartphone_absa.workbench import AnnotationEdit, AnnotationWorkbench, RevisionConflict


def annotation_router(workbench: AnnotationWorkbench) -> APIRouter:
    router = APIRouter(prefix="/api/annotations")

    @router.get("")
    def sets():
        return workbench.sets()

    @router.get("/{set_id}/tasks")
    def tasks(set_id: str, status: str = "all"):
        try:
            return workbench.tasks(set_id, status)
        except KeyError:
            raise HTTPException(404, "Annotation set not found") from None

    @router.put("/{set_id}/tasks/{sentence_id}")
    def save(set_id: str, sentence_id: str, body: AnnotationEdit):
        try:
            return workbench.save(set_id, sentence_id, body)
        except KeyError:
            raise HTTPException(404, "Sentence task not found") from None
        except RevisionConflict as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get("/{set_id}/tasks/{sentence_id}/history")
    def history(set_id: str, sentence_id: str):
        return [
            {"revision": row["revision"], "created_at": row["created_at"], "edit": row["edit"]}
            for row in workbench.history(set_id, sentence_id)
        ]

    @router.get("/{set_id}/export")
    def export(set_id: str):
        try:
            content = workbench.export(set_id)
        except KeyError:
            raise HTTPException(404, "Annotation set not found") from None
        return Response(
            content,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="annotations.zip"'},
        )

    return router
