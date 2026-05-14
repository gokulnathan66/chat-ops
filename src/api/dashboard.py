import logging
import uuid
from datetime import UTC, datetime

import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.services.conversation import ConversationService
from src.services.qdrant import QdrantService
from src.setting.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv"}
_EVAL_TYPE = "ingestion_job"
_SK = "ingestion_job"


def _get_conversation_svc() -> ConversationService:
    return ConversationService()


def _dynamodb():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION)


def _s3():
    return boto3.client("s3", region_name=settings.AWS_REGION)




def _write_ingestion_job(job_id: str, s3_key: str) -> None:
    _dynamodb().Table(settings.EVALUATIONS_TABLE).put_item(Item={
        "session_id": job_id,
        "sk": _SK,
        "eval_type": _EVAL_TYPE,
        "status": "started",
        "s3_key": s3_key,
        "created_at": datetime.now(UTC).isoformat(),
    })


def _read_ingestion_job(job_id: str) -> dict | None:
    try:
        resp = _dynamodb().Table(settings.EVALUATIONS_TABLE).get_item(
            Key={"session_id": job_id, "sk": _SK}
        )
        return resp.get("Item")
    except Exception:
        return None


def _list_ingestion_jobs(limit: int = 20) -> list[dict]:
    try:
        resp = _dynamodb().Table(settings.EVALUATIONS_TABLE).query(
            IndexName="eval_type-created_at-index",
            KeyConditionExpression=Key("eval_type").eq(_EVAL_TYPE),
            Limit=limit,
            ScanIndexForward=False,
        )
        return resp.get("Items", [])
    except Exception as exc:
        logger.warning("Could not list ingestion jobs: %s", exc)
        return []



_GOLDEN_EVAL_TYPE = "golden_query"
_GOLDEN_SK = "golden_query"


class HitlRespondRequest(BaseModel):
    human_response: str


class HitlApproveRequest(BaseModel):
    decision: str
    note: str = ""


class HitlCreateRequest(BaseModel):
    session_id: str
    trigger: str = "user_escalation"
    rag_score: float = 0.0
    llm_judge_score: float = 0.0


class GoldenQueryRequest(BaseModel):
    query: str


@router.get("/api/conversations")
async def list_conversations(status: str = "active", limit: int = 50):
    try:
        svc = _get_conversation_svc()
        if status == "all":
            sessions: list[dict] = []
            for s in ["active", "hitl_pending", "approval_pending", "complete"]:
                sessions.extend(svc.list_conversations(status=s, limit=limit))
            sessions.sort(key=lambda x: x.get("last_updated_at", ""), reverse=True)
            return sessions[:limit]
        return svc.list_conversations(status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DynamoDB unavailable: {str(e)}") from e


@router.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    result = _get_conversation_svc().get_conversation(session_id)
    if not result["metadata"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get("/api/evaluations")
async def list_evaluations(type: str = "rag", limit: int = 50):
    table = _dynamodb().Table(settings.EVALUATIONS_TABLE)
    response = table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq(type),
        Limit=limit,
        ScanIndexForward=False,
    )
    return response.get("Items", [])


@router.get("/api/metrics/summary")
async def metrics_summary():
    eval_table = _dynamodb().Table(settings.EVALUATIONS_TABLE)
    hitl_table = _dynamodb().Table(settings.HITL_TABLE)

    rag_evals = eval_table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("rag"),
        Limit=100,
        ScanIndexForward=False,
    ).get("Items", [])

    avg_rag = (
        sum(float(e.get("rag_score", 0)) for e in rag_evals) / len(rag_evals)
        if rag_evals else 0.0
    )
    avg_faithfulness = (
        sum(float(e.get("faithfulness", 0)) for e in rag_evals) / len(rag_evals)
        if rag_evals else 0.0
    )

    cost_evals = eval_table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("cost"),
        Limit=100,
        ScanIndexForward=False,
    ).get("Items", [])
    today_prefix = datetime.now(UTC).date().isoformat()
    cost_today = sum(
        float(e.get("cost_usd", 0))
        for e in cost_evals
        if e.get("created_at", "").startswith(today_prefix)
    )

    hitl_pending = hitl_table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq("pending"),
        Select="COUNT",
    ).get("Count", 0)

    return {
        "avg_rag_score": round(avg_rag, 3),
        "avg_faithfulness": round(avg_faithfulness, 3),
        "cost_today_usd": round(cost_today, 4),
        "hitl_pending": hitl_pending,
    }


@router.get("/api/hitl")
async def list_hitl(status: str = "pending", limit: int = 50):
    table = _dynamodb().Table(settings.HITL_TABLE)
    response = table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq(status),
        Limit=limit,
        ScanIndexForward=False,
    )
    return response.get("Items", [])


@router.post("/api/hitl")
async def create_hitl(body: HitlCreateRequest):
    _get_conversation_svc().write_hitl(
        body.session_id, body.trigger,
        {"rag_score": body.rag_score, "llm_judge_score": body.llm_judge_score}
    )
    return {"status": "created"}


@router.post("/api/hitl/{queue_id}/respond")
async def respond_hitl(queue_id: str, body: HitlRespondRequest):
    svc = _get_conversation_svc()
    hitl_table = _dynamodb().Table(settings.HITL_TABLE)
    item = hitl_table.get_item(Key={"pk": "HITL", "sk": queue_id}).get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="HITL item not found")
    if item.get("hitl_type") == "escalation":
        conv = svc.get_conversation(item["session_id"])
        turns = conv.get("turns", [])
        next_turn_n = max((int(t["sk"].replace("turn#", "")) for t in turns), default=0) + 1
        svc.write_human_turn(item["session_id"], next_turn_n, body.human_response)
        # Session stays hitl_pending — user and human agent continue chatting.
        # Only resolve_hitl transitions back to active.
    return {"status": "responded"}


@router.post("/api/hitl/{queue_id}/resolve")
async def resolve_hitl_endpoint(queue_id: str):
    svc = _get_conversation_svc()
    hitl_table = _dynamodb().Table(settings.HITL_TABLE)
    item = hitl_table.get_item(Key={"pk": "HITL", "sk": queue_id}).get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="HITL item not found")
    svc.resolve_hitl(queue_id, "resolved by human agent")
    svc.mark_session_active(item["session_id"])
    return {"status": "resolved"}


@router.post("/api/hitl/{queue_id}/approve")
async def approve_hitl(queue_id: str, body: HitlApproveRequest):
    if body.decision not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="decision must be 'approve' or 'reject'")
    svc = _get_conversation_svc()
    hitl_table = _dynamodb().Table(settings.HITL_TABLE)
    item = hitl_table.get_item(Key={"pk": "HITL", "sk": queue_id}).get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="HITL item not found")
    turn_n = int(item.get("turn_n", 1))
    action_description = item.get("action_description", "the requested action")
    if body.decision == "approve":
        outcome = f"Your request to \"{action_description}\" has been approved. {body.note or 'You may proceed.'}"
    else:
        outcome = f"Your request to \"{action_description}\" was not approved. {body.note or 'Please contact support for more information.'}"
    svc.write_human_turn(item["session_id"], turn_n + 1, outcome)
    svc.resolve_hitl(queue_id, f"{body.decision}: {body.note}")
    svc.mark_session_active(item["session_id"])
    return {"status": "resolved", "decision": body.decision}


@router.post("/api/ingestion/start")
async def start_ingestion(body: dict):
    """Re-ingest a file that is already in S3 under documents/."""
    s3_key = body.get("s3_key")
    if not s3_key:
        raise HTTPException(status_code=422, detail="s3_key is required")
    if not s3_key.startswith("documents/"):
        raise HTTPException(status_code=422, detail="s3_key must be under the documents/ prefix")

    # Extract job_id embedded in key: documents/{job_id}/{filename}
    parts = s3_key.split("/")
    job_id = parts[1] if len(parts) >= 3 else str(uuid.uuid4())

    _write_ingestion_job(job_id, s3_key)
    # S3 event already fired when the file was originally uploaded.
    # Copying the object to itself re-triggers the S3 → SQS → Lambda pipeline.
    try:
        _s3().copy_object(
            Bucket=settings.S3_BUCKET_NAME,
            CopySource={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
            Key=s3_key,
            MetadataDirective="REPLACE",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"S3 copy failed: {e}") from e

    return {"job_id": job_id, "status": "started", "s3_key": s3_key}


@router.post("/api/ingestion/upload")
async def upload_and_ingest(file: UploadFile = File(...)):
    """Upload a file and ingest it via S3 → SQS → Lambda."""
    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Duplicate check: reject if a file with the same name is already in Qdrant
    try:
        existing_docs = QdrantService().list_documents()
        for doc in existing_docs:
            existing_filename = doc.get("url_or_file_path", "").split("/")[-1]
            if existing_filename == file.filename:
                raise HTTPException(
                    status_code=409,
                    detail=f"'{file.filename}' is already ingested. Delete it first to re-ingest.",
                )
    except HTTPException:
        raise
    except Exception:
        pass  # Qdrant unavailable — allow upload to proceed

    job_id = str(uuid.uuid4())
    # Place under documents/ so the S3 event notification triggers SQS → Lambda.
    # job_id is embedded in the key so Lambda can extract it for status tracking.
    s3_key = f"documents/{job_id}/{file.filename}"

    try:
        content = await file.read()
        _s3().put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=s3_key,
            Body=content,
            ContentType=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"S3 upload failed: {e}") from e

    # Write job record before Lambda starts so status polling works immediately.
    _write_ingestion_job(job_id, s3_key)

    return {"job_id": job_id, "status": "started", "s3_key": s3_key, "filename": file.filename}


@router.get("/api/ingestion/docs")
async def list_ingested_docs():
    """List all unique documents currently stored in Qdrant."""
    try:
        return QdrantService().list_documents()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Qdrant unavailable: {e}") from e


@router.delete("/api/ingestion/docs/{doc_id}")
async def delete_ingested_doc(doc_id: str):
    """Delete all Qdrant vectors for a doc_id (cascaded delete)."""
    try:
        QdrantService().delete_by_doc_id(doc_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Qdrant delete failed: {e}") from e
    return {"status": "deleted", "doc_id": doc_id}


@router.get("/api/ingestion/status/{job_id}")
async def get_ingestion_status(job_id: str):
    job = _read_ingestion_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/api/ingestion/history")
async def ingestion_history(limit: int = 20):
    return _list_ingestion_jobs(limit)


# ---------------------------------------------------------------------------
# Golden queries (test questions for RAG eval)
# ---------------------------------------------------------------------------

@router.get("/api/golden-queries")
async def list_golden_queries():
    resp = _dynamodb().Table(settings.EVALUATIONS_TABLE).query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq(_GOLDEN_EVAL_TYPE),
        ScanIndexForward=False,
    )
    return resp.get("Items", [])


@router.post("/api/golden-queries")
async def add_golden_query(body: GoldenQueryRequest):
    query_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    _dynamodb().Table(settings.EVALUATIONS_TABLE).put_item(Item={
        "session_id": query_id,
        "sk": _GOLDEN_SK,
        "eval_type": _GOLDEN_EVAL_TYPE,
        "query": body.query,
        "created_at": now,
    })
    return {"query_id": query_id, "query": body.query, "created_at": now}


@router.put("/api/golden-queries/{query_id}")
async def update_golden_query(query_id: str, body: GoldenQueryRequest):
    _dynamodb().Table(settings.EVALUATIONS_TABLE).update_item(
        Key={"session_id": query_id, "sk": _GOLDEN_SK},
        UpdateExpression="SET #q = :q",
        ExpressionAttributeNames={"#q": "query"},
        ExpressionAttributeValues={":q": body.query},
    )
    return {"query_id": query_id, "query": body.query}


@router.delete("/api/golden-queries/{query_id}")
async def delete_golden_query(query_id: str):
    _dynamodb().Table(settings.EVALUATIONS_TABLE).delete_item(
        Key={"session_id": query_id, "sk": _GOLDEN_SK},
    )
    return {"status": "deleted"}
