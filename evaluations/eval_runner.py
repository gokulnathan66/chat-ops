from datetime import UTC, datetime, timedelta

import boto3
from boto3.dynamodb.conditions import Key

from evaluations.pca import analyze_conversation
from evaluations.rag_evaluator import evaluate_session
from src.services.conversation import ConversationService
from src.setting.config import settings


def get_stale_sessions() -> list[str]:
    """Return active session IDs not updated within INACTIVITY_MINUTES."""
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    table = dynamodb.Table(settings.CONVERSATIONS_TABLE)
    cutoff = (
        datetime.now(UTC) - timedelta(minutes=settings.INACTIVITY_MINUTES)
    ).isoformat()
    response = table.query(
        IndexName="status-last_updated_at-index",
        KeyConditionExpression=Key("status").eq("active") & Key("last_updated_at").lt(cutoff),
        ProjectionExpression="session_id",
    )
    return [item["session_id"] for item in response.get("Items", [])]


def run_evals_for_session(session_id: str) -> dict:
    conv_svc = ConversationService()
    conv_svc.mark_complete(session_id)
    rag_result = evaluate_session(session_id)
    pca_result = analyze_conversation(session_id)
    return {"session_id": session_id, "rag": rag_result, "pca": pca_result}


def handler(event, context):
    session_ids = get_stale_sessions()
    results = []
    for sid in session_ids:
        try:
            results.append(run_evals_for_session(sid))
        except Exception as e:
            results.append({"session_id": sid, "error": str(e)})
    return {"evaluated": len(results), "results": results}
