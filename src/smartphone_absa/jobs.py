from __future__ import annotations

import logging

from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.store import Store

log = logging.getLogger(__name__)


def run_job(store: Store, job: dict, model: RuleBaseline | None = None) -> None:
    model = model or RuleBaseline()
    processed = failed = 0
    store.update_job(job["id"], "running", 0, 0)
    try:
        for review in store.pending_reviews(job["dataset_id"]):
            try:
                result = model.analyse(review.text, review.id, review.language)
                store.save_analysis(job["dataset_id"], review.id, result)
                processed += 1
            except Exception:
                failed += 1
                log.exception("Review analysis failed for record %s", review.id)
            if (processed + failed) % 10 == 0:
                store.update_job(job["id"], "running", processed, failed)
        store.update_job(
            job["id"],
            "completed" if not failed else "failed",
            processed,
            failed,
            f"{failed} records failed; retry processes only unfinished records."
            if failed
            else None,
        )
    except Exception:
        log.exception("Analysis job %s failed", job["id"])
        store.update_job(
            job["id"],
            "failed",
            processed,
            failed,
            "Processing stopped. Completed records are preserved; retry to continue.",
        )
