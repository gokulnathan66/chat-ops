from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import boto3
from boto3.dynamodb.conditions import Key

from src.services.bedrock import BedrockService
from src.services.conversation import ConversationService
from src.setting.config import settings

logger = logging.getLogger(__name__)

PCA_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Main topics discussed in the conversation",
        },
        "sentiment": {
            "type": "string",
            "enum": ["positive", "neutral", "negative"],
            "description": "Overall user sentiment",
        },
        "unresolved_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Questions the user asked that were not fully answered",
        },
    },
    "required": ["topics", "sentiment", "unresolved_questions"],
}


def _eval_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(settings.EVALUATIONS_TABLE)


def _hitl_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(settings.HITL_TABLE)


def get_stale_sessions() -> list[str]:
    cutoff = (datetime.now(UTC) - timedelta(minutes=settings.INACTIVITY_MINUTES)).isoformat()
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    resp = dynamodb.Table(settings.CONVERSATIONS_TABLE).query(
        IndexName="status-last_updated_at-index",
        KeyConditionExpression=Key("status").eq("active") & Key("last_updated_at").lt(cutoff),
        ProjectionExpression="session_id",
    )
    return [item["session_id"] for item in resp.get("Items", [])]


def analyze_conversation(session_id: str) -> dict:
    conv_svc = ConversationService()
    bedrock = BedrockService()

    conv = conv_svc.get_conversation(session_id)
    turns = conv["turns"]

    if not turns:
        return {"pca_topics": [], "pca_sentiment": "neutral", "pca_unresolved": []}

    conversation_text = "\n".join(
        f"User: {t['user_query']}\nAssistant: {t['ai_response']}" for t in turns
    )
    prompt = (
        "Analyze this conversation between a user and an AI assistant.\n\n"
        f"Conversation:\n{conversation_text}\n\n"
        "Return JSON with:\n"
        "- topics: list of main topics discussed\n"
        "- sentiment: overall user sentiment (positive, neutral, or negative)\n"
        "- unresolved_questions: questions the user asked that were not clearly answered"
    )

    result = bedrock.converse_structured(
        user_message=prompt,
        json_schema=PCA_SCHEMA,
        schema_name="pca_analysis",
        schema_description="Post-conversation analysis: topics, sentiment, unresolved questions",
    )

    now = datetime.now(UTC).isoformat()
    _eval_table().put_item(Item={
        "session_id": session_id,
        "sk": f"eval#pca#{now}",
        "eval_type": "pca",
        "pca_topics": result.get("topics", []),
        "pca_sentiment": result.get("sentiment", "neutral"),
        "pca_unresolved": result.get("unresolved_questions", []),
        "created_at": now,
    })

    return {
        "pca_topics": result.get("topics", []),
        "pca_sentiment": result.get("sentiment", "neutral"),
        "pca_unresolved": result.get("unresolved_questions", []),
    }


def detect_degradation() -> dict | None:
    """
    Sliding-window degradation check over the last N PCA results.

    Fires when:
      - negative_ratio >= PCA_DEGRADATION_THRESHOLD (default 60%), OR
      - avg unresolved questions per session >= PCA_UNRESOLVED_THRESHOLD (default 3)

    To avoid alert spam, checks whether a pca_alert was already written
    within the current degradation window before writing another.
    """
    window = settings.PCA_DEGRADATION_WINDOW
    recent = _eval_table().query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("pca"),
        Limit=window,
        ScanIndexForward=False,
    ).get("Items", [])

    if len(recent) < max(3, window // 2):
        logger.info("Not enough PCA data for degradation check | have=%d need=%d", len(recent), max(3, window // 2))
        return None

    neg_count = sum(1 for r in recent if r.get("pca_sentiment") == "negative")
    neg_ratio = neg_count / len(recent)
    avg_unresolved = sum(len(r.get("pca_unresolved") or []) for r in recent) / len(recent)

    logger.info(
        "Degradation check | window=%d neg_ratio=%.2f avg_unresolved=%.2f",
        len(recent), neg_ratio, avg_unresolved,
    )

    if neg_ratio < settings.PCA_DEGRADATION_THRESHOLD and avg_unresolved < settings.PCA_UNRESOLVED_THRESHOLD:
        return None

    # Dedup: skip if a pca_alert was already raised in the last window * 15 min
    alert_window_minutes = window * settings.INACTIVITY_MINUTES
    cutoff = (datetime.now(UTC) - timedelta(minutes=alert_window_minutes)).isoformat()
    recent_alerts = _eval_table().query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("pca_alert") & Key("created_at").gt(cutoff),
        Limit=1,
    ).get("Items", [])
    if recent_alerts:
        logger.info("Degradation detected but alert already raised recently — skipping")
        return None

    return {
        "negative_ratio": round(neg_ratio, 3),
        "avg_unresolved": round(avg_unresolved, 2),
        "sessions_analyzed": len(recent),
    }


def _write_degradation_alert(details: dict) -> None:
    now = datetime.now(UTC).isoformat()
    summary = (
        f"{details['negative_ratio'] * 100:.0f}% negative sentiment over last "
        f"{details['sessions_analyzed']} sessions — avg {details['avg_unresolved']:.1f} unresolved questions/session"
    )
    logger.warning("PCA degradation alert | %s", summary)

    _hitl_table().put_item(Item={
        "pk": "HITL",
        "sk": f"{now}#pca_degradation",
        "session_id": "system",
        "queue_status": "pending",
        "trigger": "pca_degradation",
        "conversation_summary": summary,
        "rag_score": "0",
        "llm_judge_score": str(round(1 - details["negative_ratio"], 3)),
        "created_at": now,
    })

    _eval_table().put_item(Item={
        "session_id": "system",
        "sk": f"alert#pca#{now}",
        "eval_type": "pca_alert",
        "negative_ratio": str(details["negative_ratio"]),
        "avg_unresolved": str(details["avg_unresolved"]),
        "sessions_analyzed": str(details["sessions_analyzed"]),
        "summary": summary,
        "created_at": now,
    })


def handler(event, context):
    """Scheduled every 15 min by EventBridge. Finds inactive sessions, runs PCA, checks for degradation."""
    stale = get_stale_sessions()
    logger.info("PCA runner started | stale_sessions=%d", len(stale))

    results = []
    for sid in stale:
        try:
            conv_svc = ConversationService()
            conv_svc.mark_complete(sid)
            result = analyze_conversation(sid)
            results.append({"session_id": sid, **result})
            logger.info("PCA done | session_id=%s sentiment=%s", sid, result["pca_sentiment"])
        except Exception:
            logger.exception("PCA failed | session_id=%s", sid)
            results.append({"session_id": sid, "error": True})

    if results:
        degradation = detect_degradation()
        if degradation:
            _write_degradation_alert(degradation)

    logger.info("PCA runner complete | evaluated=%d", len(results))
    return {"evaluated": len(results), "results": results}


def analyze_handler(event, context):
    """Direct invocation for a single session (used by tests / manual runs)."""
    session_id = event.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    return analyze_conversation(session_id)
