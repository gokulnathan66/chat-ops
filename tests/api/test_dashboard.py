import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch
from fastapi.testclient import TestClient
from boto3.dynamodb.conditions import Key


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
