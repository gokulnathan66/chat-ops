import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from decimal import Decimal
from src.setting.config import settings


def _floats_to_decimals(obj):
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _floats_to_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_floats_to_decimals(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_floats_to_decimals(v) for v in obj)
    return obj


class ConversationService:
    def __init__(self):
        self._dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
        self._table = self._dynamodb.Table(settings.CONVERSATIONS_TABLE)

    def write_turn(self, session_id: str, turn_n: int, data: dict) -> None:
        if turn_n < 1:
            raise ValueError(f"turn_n must be >= 1, got {turn_n}")
        now = datetime.now(timezone.utc).isoformat()
        self._table.put_item(Item={
            "session_id": session_id,
            "sk": f"turn#{turn_n:03d}",
            "user_query": data.get("user_query", ""),
            "ai_response": data.get("ai_response", ""),
            "intent": data.get("intent", ""),
            "route": data.get("route", ""),
            "retrieved_docs": _floats_to_decimals(data.get("retrieved_docs", [])),
            "token_usage": _floats_to_decimals(data.get("token_usage", {})),
            "latency_ms": _floats_to_decimals(data.get("latency_ms", 0)),
            "created_at": now,
        })
        self._table.update_item(
            Key={"session_id": session_id, "sk": "metadata"},
            UpdateExpression=(
                "SET #s = :active, last_updated_at = :now, "
                "turn_count = if_not_exists(turn_count, :zero) + :one, "
                "created_at = if_not_exists(created_at, :now)"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":active": "active",
                ":now": now,
                ":zero": 0,
                ":one": 1,
            },
        )

    def mark_complete(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._table.update_item(
                Key={"session_id": session_id, "sk": "metadata"},
                UpdateExpression="SET #s = :complete, last_updated_at = :now",
                ConditionExpression="attribute_exists(session_id)",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":complete": "complete", ":now": now},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"Session {session_id!r} does not exist") from e
            raise

    def get_conversation(self, session_id: str) -> dict:
        response = self._table.query(
            KeyConditionExpression=Key("session_id").eq(session_id)
        )
        items = response.get("Items", [])
        metadata = next((i for i in items if i["sk"] == "metadata"), {})
        turns = sorted(
            [i for i in items if i["sk"].startswith("turn#")],
            key=lambda x: x["sk"],
        )
        return {"metadata": metadata, "turns": turns}

    def list_conversations(self, status: str, limit: int = 50) -> list[dict]:
        response = self._table.query(
            IndexName="status-last_updated_at-index",
            KeyConditionExpression=Key("status").eq(status),
            Limit=limit,
            ScanIndexForward=False,
        )
        return response.get("Items", [])
