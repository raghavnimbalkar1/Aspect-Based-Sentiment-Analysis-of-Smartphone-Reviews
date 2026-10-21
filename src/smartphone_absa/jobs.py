from __future__ import annotations

import logging

from smartphone_absa.baseline import RuleBaseline
from smartphone_absa.models.inference import Analyzer
from smartphone_absa.store import Store

log = logging.getLogger(__name__)


def run_job(store: Store, job: dict, model: Analyzer | None = None) -> None:
    model = model or RuleBaseline()
    if model.id != job["model_id"]:
        raise ValueError("Job and inference model IDs differ")
    processed = failed = 0
    if not store.claim_job(job["id"]):
        return
    try:
        for review in store.pending_reviews(job["dataset_id"], job["model_id"]):
            current = store.job(job["dataset_id"], job["id"])
            if current["cancel_requested"]:
                store.update_job(job["id"], "interrupted", processed, failed, current["error"])
                return
            try:
                result = model.analyse(review.text, review.id, review.language)
                store.save_analysis(job["dataset_id"], review.id, result)
                processed += 1
            except Exception as exc:
                failed += 1
                log.exception("Review analysis failed for record %s", review.id)
                store.record_job_failure(
                    job["id"],
                    review.id,
                    str(exc)
                    if isinstance(exc, ValueError)
                    else "Unexpected analysis error; see the local server log for details.",
                )
            if (processed + failed) % 10 == 0:
                store.update_job(job["id"], "running", processed, failed)
        store.update_job(
            job["id"],
            "completed" if not failed else "failed",
            processed,
            failed,
            f"{failed} {'record' if failed == 1 else 'records'} failed; "
            "retry processes only unfinished records."
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
