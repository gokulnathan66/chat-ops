import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, HTTPException
from src.setting.config import settings
from src.services.conversation import ConversationService

router = APIRouter()
_conversation_svc = ConversationService()


def _dynamodb():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION)


@router.get("/api/conversations")
async def list_conversations(status: str = "active", limit: int = 50):
    return _conversation_svc.list_conversations(status=status, limit=limit)


@router.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    result = _conversation_svc.get_conversation(session_id)
    if not result["metadata"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get("/api/evaluations")
async def list_evaluations(eval_type: str = "rag", limit: int = 50):
    table = _dynamodb().Table(settings.EVALUATIONS_TABLE)
    response = table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq(eval_type),
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
    cost_today = sum(float(e.get("cost_usd", 0)) for e in cost_evals)

    hitl_pending = hitl_table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq("pending"),
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
