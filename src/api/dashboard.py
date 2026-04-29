import boto3
import json
from boto3.dynamodb.conditions import Key
from datetime import date
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.setting.config import settings
from src.services.conversation import ConversationService

router = APIRouter()


def _get_conversation_svc() -> ConversationService:
    return ConversationService()


def _dynamodb():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION)


class HitlRespondRequest(BaseModel):
    human_response: str


class HitlCreateRequest(BaseModel):
    session_id: str
    trigger: str = "user_escalation"
    rag_score: float = 0.0
    llm_judge_score: float = 0.0


@router.get("/api/conversations")
async def list_conversations(status: str = "active", limit: int = 50):
    try:
        return _get_conversation_svc().list_conversations(status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DynamoDB unavailable: {str(e)}")


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
    golden_table = _dynamodb().Table(settings.GOLDEN_RESULTS_TABLE)

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
    today_prefix = date.today().isoformat()
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

    golden_total_resp = golden_table.scan()
    golden_total = golden_total_resp.get("Count", 0)
    golden_pass = sum(1 for item in golden_total_resp.get("Items", []) if item.get("pass"))
    golden_pass_rate = (golden_pass / golden_total * 100) if golden_total else 0.0

    return {
        "avg_rag_score": round(avg_rag, 3),
        "avg_faithfulness": round(avg_faithfulness, 3),
        "cost_today_usd": round(cost_today, 4),
        "hitl_pending": hitl_pending,
        "golden_pass_rate_pct": round(golden_pass_rate, 1),
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
    _get_conversation_svc().resolve_hitl(queue_id, body.human_response)
    return {"status": "resolved"}


@router.get("/api/golden-results")
async def list_golden_results(run_id: str | None = None, limit: int = 100):
    table = _dynamodb().Table(settings.GOLDEN_RESULTS_TABLE)
    if run_id:
        response = table.query(
            KeyConditionExpression=Key("run_id").eq(run_id),
            Limit=limit,
        )
    else:
        response = table.scan(Limit=limit)
    return response.get("Items", [])


@router.post("/api/ingestion/start")
async def start_ingestion(body: dict):
    s3_key = body.get("s3_key")
    if not s3_key:
        raise HTTPException(status_code=422, detail="s3_key is required")
    lambda_client = boto3.client("lambda", region_name=settings.AWS_REGION)
    lambda_client.invoke(
        FunctionName="qdrant_ingestion",
        InvocationType="Event",
        Payload=json.dumps({"s3_key": s3_key, "bucket": settings.S3_BUCKET_NAME}).encode(),
    )
    return {"status": "ingestion_started", "s3_key": s3_key}
