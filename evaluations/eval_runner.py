from __future__ import annotations

import logging

from evaluations.rag_evaluator import run_ingestion_evals

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)


def handler(event, context):
    """Triggered by qdrant_ingestion Lambda after a successful document ingest."""
    logger.info("eval_runner invoked | event=%s", event)

    job_id = event.get("job_id")
    if not job_id:
        logger.warning("eval_runner invoked without job_id | event=%s", event)
        return {"error": "job_id required"}

    logger.info("eval_runner started | job_id=%s", job_id)
    results = run_ingestion_evals(job_id)
    logger.info("eval_runner complete | job_id=%s evaluated=%d results=%s", job_id, len(results), results)
    return {"job_id": job_id, "queries_evaluated": len(results), "results": results}
