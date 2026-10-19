from __future__ import annotations

import csv
import io
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from smartphone_absa import __version__
from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.domain import JobRequest, SingleAnalysisRequest
from smartphone_absa.jobs import run_job
from smartphone_absa.store import Filters, Store
from smartphone_absa.taxonomy import CATEGORIES, CATEGORY_IDS, PRESENT_LABELS, TAXONOMY_VERSION
from smartphone_absa.uploads import MAX_UPLOAD_BYTES, parse_csv, prepare_upload

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]


def query_filters(
    product: str = "", category: str = "", sentiment: str = "", q: str = Query("", max_length=200)
) -> Filters:
    if category and category not in CATEGORY_IDS:
        raise HTTPException(422, "Unknown aspect category")
    if sentiment and sentiment not in PRESENT_LABELS:
        raise HTTPException(422, "Unknown sentiment")
    return Filters(product=product, category=category, sentiment=sentiment, q=q)


def create_app(database: Path | None = None, frontend: Path | None = None) -> FastAPI:
    store = Store(database or Path(os.getenv("ABSA_DATABASE", ROOT / "data/workspace.sqlite3")))
    model = RuleBaseline()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="absa-analysis")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.interrupt_jobs()
        yield
        executor.shutdown(wait=True, cancel_futures=False)

    app = FastAPI(title="Smartphone ABSA", version=__version__, lifespan=lifespan)
    app.state.store = store

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
            parsed = urlparse(origin)
            if parsed.hostname not in ("127.0.0.1", "localhost") or parsed.port not in (8000, 5173):
                return JSONResponse(
                    {"detail": "Requests must originate from the local application"}, 403
                )
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > MAX_UPLOAD_BYTES + 1024 * 1024):
            return JSONResponse({"detail": "Request exceeds the upload size limit"}, 413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def require_dataset(dataset_id: str) -> dict:
        result = store.dataset(dataset_id)
        if result is None:
            raise HTTPException(404, "Dataset not found")
        return result

    @app.exception_handler(ValueError)
    async def invalid_input(request: Request, exc: ValueError):
        return JSONResponse({"detail": str(exc)}, 422)

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "version": __version__,
            "mode": "local",
            "model": model.id,
            "device": "cpu",
            "taxonomy_version": TAXONOMY_VERSION,
        }

    @app.get("/api/taxonomy")
    def taxonomy():
        return {
            "version": TAXONOMY_VERSION,
            "categories": [
                {"id": c.id, "name": c.name, "description": c.description} for c in CATEGORIES
            ],
            "sentiments": list(PRESENT_LABELS),
        }

    @app.post("/api/analyse")
    def analyse(body: SingleAnalysisRequest):
        if not body.text.strip():
            raise HTTPException(422, "Enter a review to analyse")
        return model.analyse(body.text)

    @app.get("/api/datasets")
    def datasets():
        return store.datasets()

    @app.get("/api/datasets/{dataset_id}")
    def dataset(dataset_id: str):
        return require_dataset(dataset_id)

    @app.post("/api/import/preview")
    def import_preview(file: UploadFile = File(...)):
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
        columns, rows = parse_csv(content)
        return {"columns": columns, "rows": len(rows), "preview": rows[:3]}

    @app.post("/api/datasets", status_code=201)
    def import_dataset(
        name: str = Form(..., min_length=1, max_length=120),
        text_column: str = Form(...),
        product_column: str = Form(""),
        brand_column: str = Form(""),
        date_column: str = Form(""),
        rating_column: str = Form(""),
        file: UploadFile = File(...),
    ):
        reviews, manifest = prepare_upload(
            file.file.read(MAX_UPLOAD_BYTES + 1),
            {
                "text": text_column,
                "product": product_column,
                "brand": brand_column,
                "date": date_column,
                "rating": rating_column,
            },
        )
        return {
            **store.import_reviews(name.strip() or "Imported reviews", reviews, manifest),
            "validation": manifest,
        }

    @app.get("/api/datasets/{dataset_id}/products")
    def products(dataset_id: str):
        require_dataset(dataset_id)
        return store.products(dataset_id)

    @app.get("/api/datasets/{dataset_id}/overview")
    def overview(dataset_id: str, filters: Filters = Depends(query_filters)):
        require_dataset(dataset_id)
        return store.overview(dataset_id, filters)

    @app.get("/api/datasets/{dataset_id}/reviews")
    def reviews(
        dataset_id: str,
        filters: Filters = Depends(query_filters),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        require_dataset(dataset_id)
        return store.reviews(dataset_id, filters, page, page_size)

    @app.get("/api/datasets/{dataset_id}/compare")
    def compare(dataset_id: str, products: list[str] = Query(...), q: str = ""):
        require_dataset(dataset_id)
        if not 2 <= len(set(products)) <= 3:
            raise HTTPException(422, "Choose two or three different phone models")
        known = {product["id"] for product in store.products(dataset_id)}
        if not set(products) <= known:
            raise HTTPException(422, "A phone model does not belong to this dataset")
        return [
            {"product_id": product, **store.overview(dataset_id, Filters(product=product, q=q))}
            for product in dict.fromkeys(products)
        ]

    @app.post("/api/datasets/{dataset_id}/jobs", status_code=202)
    def start_job(dataset_id: str, body: JobRequest):
        require_dataset(dataset_id)
        job, created = store.create_job(dataset_id)
        if created:
            executor.submit(run_job, store, job, model)
        return job

    @app.get("/api/datasets/{dataset_id}/jobs")
    def jobs(dataset_id: str):
        require_dataset(dataset_id)
        return store.jobs(dataset_id)

    @app.get("/api/datasets/{dataset_id}/export")
    def export(
        dataset_id: str,
        filters: Filters = Depends(query_filters),
        format: str = Query("csv", pattern="^(csv|json)$"),
    ):
        require_dataset(dataset_id)
        items = store.reviews(dataset_id, filters, page_size=10000)["items"]
        if format == "json":
            return Response(
                json.dumps(
                    {
                        "model_id": model.id,
                        "taxonomy_version": TAXONOMY_VERSION,
                        "filters": filters.__dict__,
                        "reviews": items,
                    }
                ),
                media_type="application/json",
                headers={"Content-Disposition": 'attachment; filename="reviews.json"'},
            )
        handle = io.StringIO(newline="")
        writer = csv.writer(handle)
        writer.writerow(
            [
                "review_id",
                "product",
                "date",
                "text",
                "category",
                "sentiment",
                "model_id",
                "taxonomy_version",
            ]
        )
        for item in items:
            aspects = item["analysis"]["aspects"] if item["analysis"] else []
            for aspect in aspects or [{"category": "", "sentiment": ""}]:
                values = [
                    item["id"],
                    item["product_name"],
                    item["date"],
                    item["text"],
                    aspect["category"],
                    aspect["sentiment"],
                    model.id,
                    TAXONOMY_VERSION,
                ]
                # Prevent uploaded text being executed as a spreadsheet formula.
                writer.writerow(
                    [
                        "'" + value
                        if isinstance(value, str)
                        and value.lstrip().startswith(("=", "+", "-", "@"))
                        else value
                        for value in values
                    ]
                )
        return Response(
            handle.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="predictions.csv"'},
        )

    @app.get("/api/evaluation")
    def evaluation():
        reports = []
        for path in sorted((ROOT / "artifacts/experiments").glob("*/metrics.json")):
            try:
                report = json.loads(path.read_text())
                reports.append({"experiment": path.parent.name, **report})
            except (ValueError, OSError):
                log.warning("Could not read experiment report %s", path.name)
        return {
            "reports": reports,
            "active_model": model.id,
            "models": [
                {
                    "id": "rules-v1",
                    "name": "Rules + VADER",
                    "status": "available",
                    "description": "Explicit aspect cues and local sentiment rules. CPU inference.",
                },
                {
                    "id": "tfidf-v1",
                    "name": "TF-IDF + logistic regression",
                    "status": "awaiting_annotations",
                    "description": "Training command is ready; requires adjudicated human labels.",
                },
                {
                    "id": "distilbert-pair",
                    "name": "DistilBERT pair classifier",
                    "status": "planned",
                    "description": "Next modeling phase after the annotation pilot.",
                },
            ],
        }

    build = frontend or ROOT / "frontend/dist"
    if (build / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=build / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        def index():
            return FileResponse(build / "index.html")

    return app


def serve() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
