import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch
from fastapi.testclient import TestClient
from boto3.dynamodb.conditions import Key
from urllib.parse import quote


def _setup_conversations_table(dynamodb):
    table = dynamodb.create_table(
        TableName="conversations",
        KeySchema=[
            {"AttributeName": "session_id", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "last_updated_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "status-last_updated_at-index",
            "KeySchema": [
                {"AttributeName": "status", "KeyType": "HASH"},
                {"AttributeName": "last_updated_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )
    return table


def _setup_evaluations_table(dynamodb):
    return dynamodb.create_table(
        TableName="evaluations",
        KeySchema=[
            {"AttributeName": "session_id", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "eval_type", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "eval_type-created_at-index",
            "KeySchema": [
                {"AttributeName": "eval_type", "KeyType": "HASH"},
                {"AttributeName": "created_at", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )


def _setup_hitl_table(dynamodb):
    return dynamodb.create_table(
        TableName="hitl_queue",
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "queue_status", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[{
            "IndexName": "queue_status-sk-index",
            "KeySchema": [
                {"AttributeName": "queue_status", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            "Projection": {"ProjectionType": "ALL"},
        }],
        BillingMode="PAY_PER_REQUEST",
    )


@mock_aws
@patch("src.services.conversation.settings")
@patch("src.api.dashboard.settings")
def test_get_conversations_returns_list(mock_dash_settings, mock_conv_settings):
    mock_conv_settings.CONVERSATIONS_TABLE = "conversations"
    mock_conv_settings.HITL_TABLE = "hitl_queue"
    mock_conv_settings.AWS_REGION = "us-east-1"
    mock_dash_settings.CONVERSATIONS_TABLE = "conversations"
    mock_dash_settings.EVALUATIONS_TABLE = "evaluations"
    mock_dash_settings.HITL_TABLE = "hitl_queue"
    mock_dash_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_dash_settings.AWS_REGION = "us-east-1"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _setup_conversations_table(dynamodb)
    _setup_evaluations_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("sess-api-1", 1, {"user_query": "q", "ai_response": "a"})

    from src.main import app
    client = TestClient(app)
    resp = client.get("/api/conversations?status=active")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(c["session_id"] == "sess-api-1" for c in data)


@mock_aws
@patch("src.services.conversation.settings")
@patch("src.api.dashboard.settings")
def test_get_conversation_detail(mock_dash_settings, mock_conv_settings):
    mock_conv_settings.CONVERSATIONS_TABLE = "conversations"
    mock_conv_settings.HITL_TABLE = "hitl_queue"
    mock_conv_settings.AWS_REGION = "us-east-1"
    mock_dash_settings.CONVERSATIONS_TABLE = "conversations"
    mock_dash_settings.EVALUATIONS_TABLE = "evaluations"
    mock_dash_settings.HITL_TABLE = "hitl_queue"
    mock_dash_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_dash_settings.AWS_REGION = "us-east-1"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _setup_conversations_table(dynamodb)
    _setup_evaluations_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("sess-api-2", 1, {"user_query": "what?", "ai_response": "this."})

    from src.main import app
    client = TestClient(app)
    resp = client.get("/api/conversations/sess-api-2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["turns"]) == 1
    assert data["turns"][0]["user_query"] == "what?"


@mock_aws
@patch("src.services.conversation.settings")
@patch("src.api.dashboard.settings")
def test_get_hitl_queue(mock_dash_settings, mock_conv_settings):
    mock_conv_settings.CONVERSATIONS_TABLE = "conversations"
    mock_conv_settings.HITL_TABLE = "hitl_queue"
    mock_conv_settings.AWS_REGION = "us-east-1"
    mock_dash_settings.CONVERSATIONS_TABLE = "conversations"
    mock_dash_settings.EVALUATIONS_TABLE = "evaluations"
    mock_dash_settings.HITL_TABLE = "hitl_queue"
    mock_dash_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_dash_settings.AWS_REGION = "us-east-1"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _setup_conversations_table(dynamodb)
    _setup_evaluations_table(dynamodb)
    _setup_hitl_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("sess-hitl-1", 1, {"user_query": "bad", "ai_response": "wrong"})
    svc.write_hitl("sess-hitl-1", "rag_eval", {"rag_score": 0.2, "llm_judge_score": 0.3})

    from src.main import app
    client = TestClient(app)
    resp = client.get("/api/hitl?status=pending")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert items[0]["session_id"] == "sess-hitl-1"


@mock_aws
@patch("src.services.conversation.settings")
@patch("src.api.dashboard.settings")
def test_post_hitl_respond(mock_dash_settings, mock_conv_settings):
    mock_conv_settings.CONVERSATIONS_TABLE = "conversations"
    mock_conv_settings.HITL_TABLE = "hitl_queue"
    mock_conv_settings.AWS_REGION = "us-east-1"
    mock_dash_settings.CONVERSATIONS_TABLE = "conversations"
    mock_dash_settings.EVALUATIONS_TABLE = "evaluations"
    mock_dash_settings.HITL_TABLE = "hitl_queue"
    mock_dash_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_dash_settings.AWS_REGION = "us-east-1"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _setup_conversations_table(dynamodb)
    _setup_evaluations_table(dynamodb)
    hitl_table = _setup_hitl_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("sess-hitl-2", 1, {"user_query": "q", "ai_response": "a"})
    svc.write_hitl("sess-hitl-2", "rag_eval", {"rag_score": 0.1})

    response = hitl_table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq("pending"),
    )
    queue_id = response["Items"][0]["sk"]

    from src.main import app
    client = TestClient(app)
    encoded_queue_id = quote(queue_id, safe='')
    resp = client.post(f"/api/hitl/{encoded_queue_id}/respond", json={"human_response": "The answer is X."})
    assert resp.status_code == 200

    item = hitl_table.get_item(Key={"pk": "HITL", "sk": queue_id})["Item"]
    assert item["queue_status"] == "resolved"
