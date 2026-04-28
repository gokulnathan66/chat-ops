import boto3
from datetime import datetime, timezone
from src.setting.config import settings
from src.services.bedrock import BedrockService
from src.services.conversation import ConversationService

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


def analyze_conversation(session_id: str) -> dict:
    conv_svc = ConversationService()
    bedrock = BedrockService()
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    eval_table = dynamodb.Table(settings.EVALUATIONS_TABLE)

    conv = conv_svc.get_conversation(session_id)
    turns = conv["turns"]

    if not turns:
        return {"pca_topics": [], "pca_sentiment": "neutral", "pca_unresolved": []}

    conversation_text = "\n".join(
        f"User: {t['user_query']}\nAssistant: {t['ai_response']}" for t in turns
    )

    prompt = (
        f"Analyze this conversation between a user and an AI assistant.\n\n"
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

    now = datetime.now(timezone.utc).isoformat()
    eval_table.put_item(Item={
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


def handler(event, context):
    session_id = event.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    return analyze_conversation(session_id)
