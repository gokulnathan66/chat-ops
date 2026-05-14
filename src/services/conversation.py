from datetime import UTC, datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

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
        now = datetime.now(UTC).isoformat()
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
        now = datetime.now(UTC).isoformat()
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

    def write_cost(self, session_id: str, token_usage: dict, model_id: str) -> None:
        # Claude Haiku 4.5 pricing: $0.80/M input, $4.00/M output (on-demand)
        input_cost = token_usage.get("input", 0) * 0.80 / 1_000_000
        output_cost = token_usage.get("output", 0) * 4.00 / 1_000_000
        cost_usd = round(input_cost + output_cost, 8)
        now = datetime.now(UTC).isoformat()
        eval_table = self._dynamodb.Table(settings.EVALUATIONS_TABLE)
        eval_table.put_item(Item={
            "session_id": session_id,
            "sk": f"eval#cost#{now}",
            "eval_type": "cost",
            "model_id": model_id,
            "input_tokens": str(token_usage.get("input", 0)),
            "output_tokens": str(token_usage.get("output", 0)),
            "cost_usd": str(cost_usd),
            "created_at": now,
        })

    def mark_hitl_pending(self, session_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._table.update_item(
            Key={"session_id": session_id, "sk": "metadata"},
            UpdateExpression="SET #s = :s, last_updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "hitl_pending", ":now": now},
        )

    def mark_approval_pending(self, session_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._table.update_item(
            Key={"session_id": session_id, "sk": "metadata"},
            UpdateExpression="SET #s = :s, last_updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "approval_pending", ":now": now},
        )

    def write_human_turn(self, session_id: str, turn_n: int, human_response: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._table.put_item(Item={
            "session_id": session_id,
            "sk": f"turn#{turn_n:03d}",
            "user_query": "",
            "ai_response": human_response,
            "intent": "human",
            "route": "human",
            "retrieved_docs": [],
            "token_usage": _floats_to_decimals({"input": 0, "output": 0}),
            "latency_ms": Decimal("0"),
            "created_at": now,
        })
        self._table.update_item(
            Key={"session_id": session_id, "sk": "metadata"},
            UpdateExpression=(
                "SET last_updated_at = :now, "
                "turn_count = if_not_exists(turn_count, :zero) + :one"
            ),
            ExpressionAttributeValues={
                ":now": now,
                ":zero": 0,
                ":one": 1,
            },
        )

    def write_user_turn_hitl(self, session_id: str, turn_n: int, user_query: str) -> None:
        """Write a user message during HITL without changing session status."""
        now = datetime.now(UTC).isoformat()
        self._table.put_item(Item={
            "session_id": session_id,
            "sk": f"turn#{turn_n:03d}",
            "user_query": user_query,
            "ai_response": "",
            "intent": "hitl_user_reply",
            "route": "hitl_pending",
            "retrieved_docs": [],
            "token_usage": _floats_to_decimals({"input": 0, "output": 0}),
            "latency_ms": Decimal("0"),
            "created_at": now,
        })
        self._table.update_item(
            Key={"session_id": session_id, "sk": "metadata"},
            UpdateExpression=(
                "SET last_updated_at = :now, "
                "turn_count = if_not_exists(turn_count, :zero) + :one"
            ),
            ExpressionAttributeValues={
                ":now": now,
                ":zero": 0,
                ":one": 1,
            },
        )

    def mark_session_active(self, session_id: str) -> None:
        now = datetime.now(UTC).isoformat()
        self._table.update_item(
            Key={"session_id": session_id, "sk": "metadata"},
            UpdateExpression="SET #s = :active, last_updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":active": "active", ":now": now},
        )

    def write_hitl(self, session_id: str, trigger: str, scores: dict, extras: dict | None = None) -> None:
        now = datetime.now(UTC).isoformat()
        hitl_table = self._dynamodb.Table(settings.HITL_TABLE)
        conv = self.get_conversation(session_id)
        last_5 = conv["turns"][-5:]
        summary = " | ".join(
            f"Q: {t.get('user_query', '')} A: {t.get('ai_response', '')}" for t in last_5
        )
        item: dict = {
            "pk": "HITL",
            "sk": f"{now}#{session_id}",
            "session_id": session_id,
            "queue_status": "pending",
            "trigger": trigger,
            "hitl_type": "escalation",
            "conversation_summary": summary,
            "rag_score": str(scores.get("rag_score", "")),
            "llm_judge_score": str(scores.get("llm_judge_score", "")),
            "created_at": now,
        }
        if extras:
            item.update(extras)
        hitl_table.put_item(Item=item)

    def resolve_hitl(self, queue_id: str, human_response: str) -> None:
        from botocore.exceptions import ClientError
        now = datetime.now(UTC).isoformat()
        hitl_table = self._dynamodb.Table(settings.HITL_TABLE)
        try:
            hitl_table.update_item(
                Key={"pk": "HITL", "sk": queue_id},
                UpdateExpression="SET queue_status = :resolved, human_response = :resp, resolved_at = :now",
                ConditionExpression="attribute_exists(sk)",
                ExpressionAttributeValues={
                    ":resolved": "resolved",
                    ":resp": human_response,
                    ":now": now,
                },
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"HITL queue item {queue_id!r} does not exist") from e
            raise
