import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch
from src.services.conversation import ConversationService

TABLE_NAME = "conversations"

def _create_table(dynamodb):
    dynamodb.create_table(
        TableName=TABLE_NAME,
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
    return dynamodb.Table(TABLE_NAME)


@mock_aws
@patch("src.services.conversation.settings")
def test_write_turn_creates_turn_item(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_table(dynamodb)

    svc = ConversationService()
    svc.write_turn("sess-1", 1, {
        "user_query": "What is pricing?",
        "ai_response": "Pricing is $49/mo.",
        "intent": "tools",
        "route": "tools",
        "retrieved_docs": [{"doc_id": "d1", "score": 0.9}],
        "token_usage": {"input": 100, "output": 50},
        "latency_ms": 1234.5,
    })

    item = table.get_item(Key={"session_id": "sess-1", "sk": "turn#001"})["Item"]
    assert item["user_query"] == "What is pricing?"
    assert item["ai_response"] == "Pricing is $49/mo."
    assert item["intent"] == "tools"
    assert item["token_usage"]["input"] == 100


@mock_aws
@patch("src.services.conversation.settings")
def test_write_turn_creates_metadata_item(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_table(dynamodb)

    svc = ConversationService()
    svc.write_turn("sess-1", 1, {"user_query": "hi", "ai_response": "hello"})

    meta = table.get_item(Key={"session_id": "sess-1", "sk": "metadata"})["Item"]
    assert meta["status"] == "active"
    assert meta["turn_count"] == 1
    assert "last_updated_at" in meta


@mock_aws
@patch("src.services.conversation.settings")
def test_mark_complete_updates_status(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_table(dynamodb)

    svc = ConversationService()
    svc.write_turn("sess-1", 1, {"user_query": "hi", "ai_response": "hello"})
    svc.mark_complete("sess-1")

    meta = table.get_item(Key={"session_id": "sess-1", "sk": "metadata"})["Item"]
    assert meta["status"] == "complete"


@mock_aws
@patch("src.services.conversation.settings")
def test_write_turn_increments_turn_count_across_multiple_turns(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = _create_table(dynamodb)

    svc = ConversationService()
    svc.write_turn("sess-multi", 1, {"user_query": "q1", "ai_response": "a1"})
    svc.write_turn("sess-multi", 2, {"user_query": "q2", "ai_response": "a2"})
    svc.write_turn("sess-multi", 3, {"user_query": "q3", "ai_response": "a3"})

    meta = table.get_item(Key={"session_id": "sess-multi", "sk": "metadata"})["Item"]
    assert meta["turn_count"] == 3


@mock_aws
@patch("src.services.conversation.settings")
def test_mark_complete_raises_for_nonexistent_session(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_table(dynamodb)

    svc = ConversationService()
    with pytest.raises(ValueError, match="does not exist"):
        svc.mark_complete("nonexistent-session")
