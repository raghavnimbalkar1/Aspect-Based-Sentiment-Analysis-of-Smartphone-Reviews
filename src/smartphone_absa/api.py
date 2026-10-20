from __future__ import annotations

import csv
import io
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from smartphone_absa import __version__
from smartphone_absa.annotation_api import annotation_router
from smartphone_absa.domain import JobRequest, ModelComparisonRequest, SingleAnalysisRequest
from smartphone_absa.jobs import run_job
from smartphone_absa.models.registry import ModelRegistry, ModelUnavailable
from smartphone_absa.reports import report_catalog
from smartphone_absa.research import ResearchService
from smartphone_absa.research_api import research_router
from smartphone_absa.store import Filters, Store
from smartphone_absa.taxonomy import CATEGORIES, CATEGORY_IDS, PRESENT_LABELS, TAXONOMY_VERSION
from smartphone_absa.uploads import MAX_UPLOAD_BYTES, parse_csv, prepare_upload
from smartphone_absa.workbench import AnnotationWorkbench

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


def create_app(
    database: Path | None = None,
    frontend: Path | None = None,
    registry: ModelRegistry | None = None,
) -> FastAPI:
    store = Store(database or Path(os.getenv("ABSA_DATABASE", ROOT / "data/workspace.sqlite3")))
    registry = registry or ModelRegistry(Path(os.getenv("ABSA_ARTIFACTS", ROOT / "artifacts")))
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="absa-analysis")
    research = ResearchService(store, registry.artifacts, registry, executor)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.interrupt_jobs()
        research.interrupt()
        yield
        executor.shutdown(wait=True, cancel_futures=False)

    app = FastAPI(title="Smartphone ABSA", version=__version__, lifespan=lifespan)
    app.state.store = store
    app.state.registry = registry
    app.state.research = research
    app.include_router(annotation_router(AnnotationWorkbench(store)))
    app.include_router(research_router(research))

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in ("GET", "HEAD", "OPTIONS") and origin:
            try:
                parsed = urlparse(origin)
                allowed = (
                    parsed.scheme == request.url.scheme
                    and parsed.hostname in ("127.0.0.1", "localhost")
                    and parsed.port in (request.url.port or 80, 5173)
                    and not parsed.username
                    and not parsed.password
                    and parsed.path in ("", "/")
                    and not parsed.query
                    and not parsed.fragment
                )
            except ValueError:
                allowed = False
            if not allowed:
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
            "model": "rules-v1",
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
        return registry.get(body.model).analyse(body.text)

    @app.exception_handler(ModelUnavailable)
    async def unavailable_model(request: Request, exc: ModelUnavailable):
        return JSONResponse({"detail": str(exc)}, 503)

    def public_specs():
        return [
            {key: value for key, value in spec.items() if key != "path"}
            for spec in registry.specs()
        ]

    @app.get("/api/models")
    def models():
        return public_specs()

    @app.post("/api/analyse/compare")
    def compare_models(body: ModelComparisonRequest):
        if not body.text.strip() or len(set(body.models)) != len(body.models):
            raise HTTPException(422, "Enter a review and select different models")
        analyzers = [registry.get(model_id) for model_id in body.models]
        results = []
        for analyzer in analyzers:
            started = time.perf_counter()
            analysis = analyzer.analyse(body.text)
            results.append(
                {
                    "analysis": analysis.model_dump(mode="json"),
                    "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                }
            )
        return {"results": results}

    @app.get("/api/datasets")
    def datasets(model: str = "rules-v1"):
        registry.describe(model)
        return store.datasets(model)

    @app.get("/api/datasets/{dataset_id}")
    def dataset(dataset_id: str):
        return require_dataset(dataset_id)

    @app.get("/api/datasets/{dataset_id}/manifest")
    def dataset_manifest(dataset_id: str):
        return JSONResponse(
            require_dataset(dataset_id),
            headers={"Content-Disposition": 'attachment; filename="dataset-manifest.json"'},
        )

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
        saved = store.import_reviews(name.strip() or "Imported reviews", reviews, manifest)
        return {
            "id": saved["id"],
            "name": saved["name"],
            "accepted": len(reviews),
            "rejected": sum(manifest["rejected"].values()),
            "duplicate": saved["duplicate"],
            "validation": manifest,
        }

    @app.get("/api/datasets/{dataset_id}/products")
    def products(dataset_id: str):
        require_dataset(dataset_id)
        return store.products(dataset_id)

    @app.get("/api/datasets/{dataset_id}/overview")
    def overview(
        dataset_id: str, filters: Filters = Depends(query_filters), model: str = "rules-v1"
    ):
        require_dataset(dataset_id)
        registry.describe(model)
        return store.overview(dataset_id, filters, model)

    @app.get("/api/datasets/{dataset_id}/reviews")
    def reviews(
        dataset_id: str,
        filters: Filters = Depends(query_filters),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        model: str = "rules-v1",
    ):
        require_dataset(dataset_id)
        registry.describe(model)
        return store.reviews(dataset_id, filters, page, page_size, model)

    @app.get("/api/datasets/{dataset_id}/compare")
    def compare(
        dataset_id: str, products: list[str] = Query(...), q: str = "", model: str = "rules-v1"
    ):
        require_dataset(dataset_id)
        if not 2 <= len(set(products)) <= 3:
            raise HTTPException(422, "Choose two or three different phone models")
        registry.describe(model)
        known = {product["id"] for product in store.products(dataset_id)}
        if not set(products) <= known:
            raise HTTPException(422, "A phone model does not belong to this dataset")
        return [
            {
                "product_id": product,
                **store.overview(dataset_id, Filters(product=product, q=q), model),
            }
            for product in dict.fromkeys(products)
        ]

    @app.post("/api/datasets/{dataset_id}/jobs", status_code=202)
    def start_job(dataset_id: str, body: JobRequest):
        require_dataset(dataset_id)
        spec = registry.describe(body.model)
        if not spec["available"]:
            raise ModelUnavailable("Model is not installed; see Model evaluation for setup.")
        job, created = store.create_job(dataset_id, body.model)
        if created:

            def execute():
                try:
                    run_job(store, job, registry.get(body.model))
                except Exception:
                    log.exception("Could not initialize job model")
                    store.update_job(
                        job["id"],
                        "failed",
                        0,
                        0,
                        "Model could not load. Check the local server log and retry.",
                    )

            executor.submit(execute)
        return job

    @app.get("/api/datasets/{dataset_id}/jobs")
    def jobs(dataset_id: str, model: str = "rules-v1"):
        require_dataset(dataset_id)
        registry.describe(model)
        return store.jobs(dataset_id, model)

    @app.get("/api/datasets/{dataset_id}/export")
    def export(
        dataset_id: str,
        filters: Filters = Depends(query_filters),
        format: str = Query("csv", pattern="^(csv|json)$"),
        model: str = "rules-v1",
    ):
        require_dataset(dataset_id)
        registry.describe(model)
        items = store.reviews(dataset_id, filters, page_size=10000, model_id=model)["items"]
        if format == "json":
            return Response(
                json.dumps(
                    {
                        "model_id": model,
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
                    model,
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
        reports, errors = report_catalog(registry.artifacts)
        specs = public_specs()
        cards = [
            {**spec, "status": "available" if spec["available"] else "not_installed"}
            for spec in specs
        ]
        if not any(spec.get("kind") == "tfidf" for spec in specs):
            cards.append(
                {
                    "id": "tfidf-supervised",
                    "name": "TF-IDF + logistic regression",
                    "status": "awaiting_annotations",
                    "available": False,
                    "description": "Requires training and validation labels. Assisted training "
                    "and AI-validation diagnostics each require explicit selection.",
                }
            )
        return {
            "reports": reports,
            "report_errors": errors,
            "active_model": "rules-v1",
            "models": cards,
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
