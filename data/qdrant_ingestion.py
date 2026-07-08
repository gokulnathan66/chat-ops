from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from urllib.parse import unquote_plus

import boto3

from src.services.embedding import EmbeddingService
from src.services.qdrant import QdrantService
from src.services.s3 import S3Service
from src.setting.config import settings

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_EVAL_TYPE = "ingestion_job"
_SK = "ingestion_job"


def _update_job(job_id: str, updates: dict) -> None:
    table_name = settings.EVALUATIONS_TABLE
    region = settings.AWS_REGION
    logger.info("_update_job | job_id=%s table=%s region=%s updates=%s", job_id, table_name, region, list(updates.keys()))
    try:
        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)
        expr_parts = []
        attr_names: dict = {}
        attr_values: dict = {}
        for k, v in updates.items():
            safe = f"#f_{k}"
            attr_names[safe] = k
            attr_values[f":v_{k}"] = v
            expr_parts.append(f"{safe} = :v_{k}")
        table.update_item(
            Key={"session_id": job_id, "sk": _SK},
            UpdateExpression="SET " + ", ".join(expr_parts),
            ExpressionAttributeNames=attr_names,
            ExpressionAttributeValues=attr_values,
        )
        logger.info("_update_job succeeded | job_id=%s status=%s", job_id, updates.get("status"))
    except Exception:
        logger.exception("_update_job FAILED | job_id=%s table=%s region=%s", job_id, table_name, region)


def _extract_job_id_from_key(key: str) -> str | None:
    """Extract job_id embedded in key: documents/{job_id}/{filename}."""
    parts = key.split("/")
    if len(parts) >= 3 and parts[0] == "documents":
        return parts[1]
    return None


def _build_item_records(event: dict) -> list[dict]:
    """Normalise SQS-wrapped and direct S3 events into a flat list of S3 records."""
    result = []
    for record in event.get("Records", []):
        if record.get("eventSource") == "aws:sqs":
            inner = json.loads(record["body"]).get("Records", [])
            logger.info("SQS record unwrapped | inner_records=%d", len(inner))
            # URL-decode S3 keys — SQS wrapping encodes them (e.g. spaces become +)
            for r in inner:
                key = r.get("s3", {}).get("object", {}).get("key", "")
                if key:
                    r["s3"]["object"]["key"] = unquote_plus(key)
            result.extend(inner)
        else:
            result.append(record)
    return result


def lambda_handler(event, context):
    item_records = _build_item_records(event)

    # job_id comes from the S3 key: documents/{job_id}/{filename}
    job_id: str | None = None
    if item_records:
        first_key = item_records[0].get("s3", {}).get("object", {}).get("key", "")
        job_id = _extract_job_id_from_key(first_key)

    logger.info("qdrant_ingestion started | records=%d job_id=%s", len(item_records), job_id)

    if job_id:
        _update_job(job_id, {"status": "running", "started_at": datetime.now(UTC).isoformat()})

    s3_svc = S3Service()
    emb_svc = EmbeddingService()
    qdrant_svc = QdrantService()

    indexed: list[dict] = []

    for item in item_records:
        bucket, key = s3_svc.parse_event_record(item)
        logger.info("Processing s3://%s/%s", bucket, key)

        try:
            source_uri = s3_svc.build_s3_uri(bucket, key)
            text, metadata = s3_svc.read_document(bucket, key)
            title = s3_svc.infer_title(key)
            logger.info("Document read | title=%s chars=%d", title, len(text))

            chunks = emb_svc.chunk_text(text)
            if not chunks:
                logger.warning("Skipped empty document | key=%s", key)
                indexed.append({"bucket": bucket, "key": key, "status": "skipped_empty"})
                continue

            logger.info("Chunking done | chunks=%d", len(chunks))

            vectors = emb_svc.embed_texts(chunks)
            logger.info("Embeddings done | vectors=%d", len(vectors))

            doc_id, points = qdrant_svc.build_points(
                full_text=text,
                chunks=chunks,
                vectors=vectors,
                source="s3",
                title=title,
                url_or_file_path=source_uri,
                tags=["s3", "async-indexed"],
                section_prefix=title.replace(".", "_"),
            )
            qdrant_svc.upsert_points(points)
            logger.info("Upserted to Qdrant | doc_id=%s points=%d", doc_id, len(points))

            indexed.append({
                "bucket": bucket,
                "key": key,
                "doc_id": doc_id,
                "chunks_indexed": len(points),
                "metadata": metadata,
                "status": "indexed",
            })

        except Exception:
            logger.exception("Failed to index s3://%s/%s", bucket, key)
            indexed.append({"bucket": bucket, "key": key, "status": "error"})

    n_indexed = sum(1 for r in indexed if r["status"] == "indexed")
    n_skipped = sum(1 for r in indexed if r["status"] == "skipped_empty")
    n_errors  = sum(1 for r in indexed if r["status"] == "error")
    total_chunks = sum(r.get("chunks_indexed", 0) for r in indexed)

    logger.info(
        "qdrant_ingestion complete | total=%d indexed=%d skipped=%d errors=%d chunks=%d",
        len(indexed), n_indexed, n_skipped, n_errors, total_chunks,
    )

    if job_id:
        final_status = "error" if n_errors > 0 and n_indexed == 0 else "completed"
        _update_job(job_id, {
            "status": final_status,
            "completed_at": datetime.now(UTC).isoformat(),
            "chunks_indexed": str(total_chunks),
            "files_processed": str(n_indexed),
            "files_skipped": str(n_skipped),
            "files_errored": str(n_errors),
        })

        if final_status == "completed":
            _invoke_eval_runner(job_id)

    return {"statusCode": 200, "body": json.dumps({"indexed": indexed}, default=str)}


def _invoke_eval_runner(job_id: str) -> None:
    """Async-invoke the eval_runner Lambda to score golden queries against newly ingested docs."""
    fn = settings.LAMBDA_EVAL_RUNNER_FUNCTION
    try:
        boto3.client("lambda", region_name=settings.AWS_REGION).invoke(
            FunctionName=fn,
            InvocationType="Event",  # async, fire-and-forget
            Payload=json.dumps({"job_id": job_id}).encode(),
        )
        logger.info("eval_runner invoked | job_id=%s fn=%s", job_id, fn)
    except Exception:
        logger.exception("Failed to invoke eval_runner | job_id=%s fn=%s", job_id, fn)
