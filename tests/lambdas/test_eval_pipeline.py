"""
Full eval pipeline integration tests.
Exercises: eval_runner -> rag_evaluator + pca -> DynamoDB writes -> HITL flagging.
Uses moto for DynamoDB and mocks for Bedrock/Embedding.
"""
import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch, MagicMock


# ── DynamoDB table helpers ────────────────────────────────────────────────────

def _create_conversations_table(dynamodb):
    return dynamodb.create_table(
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


def _create_evaluations_table(dynamodb):
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


def _create_hitl_table(dynamodb):
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


# ── Shared settings patch values ──────────────────────────────────────────────

SETTINGS_PATCH = {
    "CONVERSATIONS_TABLE": "conversations",
    "EVALUATIONS_TABLE": "evaluations",
    "HITL_TABLE": "hitl_queue",
    "AWS_REGION": "us-east-1",
    "RAG_THRESHOLD": 0.6,
    "HITL_THRESHOLD": 0.6,
    "INACTIVITY_MINUTES": 15,
}


def _apply_settings(mock_settings):
    for k, v in SETTINGS_PATCH.items():
        setattr(mock_settings, k, v)


# ── Tests ─────────────────────────────────────────────────────────────────────

@mock_aws
@patch("evaluations.rag_evaluator.EmbeddingService")
@patch("evaluations.rag_evaluator.BedrockService")
@patch("evaluations.rag_evaluator.settings")
@patch("evaluations.pca.BedrockService")
@patch("evaluations.pca.settings")
@patch("src.services.conversation.settings")
def test_full_pipeline_rag_and_pca_written(
    mock_conv_settings, mock_pca_settings, mock_pca_bedrock_cls,
    mock_rag_settings, mock_rag_bedrock_cls, mock_emb_cls,
):
    """rag_evaluator and pca both write eval records for a tools-route session."""
    _apply_settings(mock_conv_settings)
    _apply_settings(mock_pca_settings)
    _apply_settings(mock_rag_settings)

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_conversations_table(dynamodb)
    eval_table = _create_evaluations_table(dynamodb)
    _create_hitl_table(dynamodb)

    # Seed a conversation with a tools-route turn
    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("pipe-1", 1, {
        "user_query": "What is pricing?",
        "ai_response": "Pricing is $49/mo.",
        "route": "tools",
        "retrieved_docs": [{"text_snippet": "Pricing is $49/mo."}],
    })

    # Mock embedding service
    mock_emb = MagicMock()
    mock_emb_cls.return_value = mock_emb
    mock_emb.embed_query.return_value = [1.0, 0.0]
    mock_emb.embed_texts.return_value = [[0.99, 0.1]]

    # Mock RAG bedrock (LLM judge)
    mock_rag_bedrock = MagicMock()
    mock_rag_bedrock_cls.return_value = mock_rag_bedrock
    mock_rag_bedrock.converse_structured.return_value = {
        "faithfulness": 0.9, "relevance": 0.85, "reason": "well grounded"
    }

    # Mock PCA bedrock
    mock_pca_bedrock = MagicMock()
    mock_pca_bedrock_cls.return_value = mock_pca_bedrock
    mock_pca_bedrock.converse_structured.return_value = {
        "topics": ["pricing"], "sentiment": "positive", "unresolved_questions": []
    }

    from evaluations.rag_evaluator import evaluate_session
    from evaluations.pca import analyze_conversation

    rag_result = evaluate_session("pipe-1")
    pca_result = analyze_conversation("pipe-1")

    assert rag_result["rag_score"] > 0
    assert rag_result["hitl_flagged"] is False
    assert pca_result["pca_sentiment"] == "positive"

    # Both eval records should be in the evaluations table
    from boto3.dynamodb.conditions import Key
    rag_evals = eval_table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("rag"),
    )["Items"]
    pca_evals = eval_table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("pca"),
    )["Items"]

    assert len(rag_evals) == 1
    assert float(rag_evals[0]["faithfulness"]) == pytest.approx(0.9)
    assert len(pca_evals) == 1
    assert pca_evals[0]["pca_sentiment"] == "positive"


@mock_aws
@patch("src.tools.rag.semantic_document_search")
@patch("evaluations.rag_evaluator.EmbeddingService")
@patch("evaluations.rag_evaluator.BedrockService")
@patch("evaluations.rag_evaluator.settings")
@patch("src.services.conversation.settings")
def test_pipeline_hitl_flagged_on_low_score(
    mock_conv_settings, mock_rag_settings, mock_bedrock_cls, mock_emb_cls, mock_search,
):
    """When rag_score stays below HITL_THRESHOLD after re-retrieval, HITL is flagged."""
    _apply_settings(mock_conv_settings)
    _apply_settings(mock_rag_settings)

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_conversations_table(dynamodb)
    _create_evaluations_table(dynamodb)
    hitl_table = _create_hitl_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("pipe-hitl", 1, {
        "user_query": "Obscure question",
        "ai_response": "I don't know.",
        "route": "tools",
        "retrieved_docs": [{"text_snippet": "Unrelated content."}],
    })

    # Low similarity embeddings -> rag_score < RAG_THRESHOLD
    mock_emb = MagicMock()
    mock_emb_cls.return_value = mock_emb
    mock_emb.embed_query.return_value = [1.0, 0.0]
    mock_emb.embed_texts.return_value = [[0.0, 1.0]]  # orthogonal -> score ~0

    # Re-retrieval also returns low similarity
    mock_search.invoke.return_value = [{"text_snippet": "Still unrelated."}]

    mock_bedrock = MagicMock()
    mock_bedrock_cls.return_value = mock_bedrock
    mock_bedrock.converse_structured.return_value = {
        "faithfulness": 0.2, "relevance": 0.1, "reason": "not grounded"
    }

    from evaluations.rag_evaluator import evaluate_session
    result = evaluate_session("pipe-hitl")

    assert result["hitl_flagged"] is True

    # HITL record should be in the queue
    from boto3.dynamodb.conditions import Key
    items = hitl_table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq("pending"),
    )["Items"]
    assert len(items) == 1
    assert items[0]["session_id"] == "pipe-hitl"
    assert items[0]["trigger"] == "rag_eval"


@mock_aws
@patch("evaluations.rag_evaluator.EmbeddingService")
@patch("evaluations.rag_evaluator.BedrockService")
@patch("evaluations.rag_evaluator.settings")
@patch("evaluations.pca.BedrockService")
@patch("evaluations.pca.settings")
@patch("evaluations.eval_runner.settings")
@patch("src.services.conversation.settings")
def test_eval_runner_marks_complete_and_evaluates(
    mock_conv_settings, mock_runner_settings, mock_pca_settings, mock_pca_bedrock_cls,
    mock_rag_settings, mock_rag_bedrock_cls, mock_emb_cls,
):
    """eval_runner marks session complete then runs rag + pca evals."""
    _apply_settings(mock_conv_settings)
    _apply_settings(mock_runner_settings)
    _apply_settings(mock_pca_settings)
    _apply_settings(mock_rag_settings)

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    conv_table = _create_conversations_table(dynamodb)
    _create_evaluations_table(dynamodb)
    _create_hitl_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("pipe-runner", 1, {
        "user_query": "What is the refund policy?",
        "ai_response": "30-day refund.",
        "route": "tools",
        "retrieved_docs": [{"text_snippet": "30-day refund policy."}],
    })

    mock_emb = MagicMock()
    mock_emb_cls.return_value = mock_emb
    mock_emb.embed_query.return_value = [1.0, 0.0]
    mock_emb.embed_texts.return_value = [[0.99, 0.1]]

    mock_rag_bedrock = MagicMock()
    mock_rag_bedrock_cls.return_value = mock_rag_bedrock
    mock_rag_bedrock.converse_structured.return_value = {
        "faithfulness": 0.88, "relevance": 0.82, "reason": "grounded"
    }

    mock_pca_bedrock = MagicMock()
    mock_pca_bedrock_cls.return_value = mock_pca_bedrock
    mock_pca_bedrock.converse_structured.return_value = {
        "topics": ["refund"], "sentiment": "neutral", "unresolved_questions": []
    }

    from evaluations.eval_runner import run_evals_for_session
    result = run_evals_for_session("pipe-runner")

    # Session should be marked complete
    meta = conv_table.get_item(Key={"session_id": "pipe-runner", "sk": "metadata"})["Item"]
    assert meta["status"] == "complete"

    assert result["rag"]["rag_score"] > 0
    assert result["rag"]["hitl_flagged"] is False
    assert result["pca"]["pca_sentiment"] == "neutral"


@mock_aws
@patch("evaluations.rag_evaluator.EmbeddingService")
@patch("evaluations.rag_evaluator.BedrockService")
@patch("evaluations.rag_evaluator.settings")
@patch("src.services.conversation.settings")
def test_pipeline_general_route_skipped(
    mock_conv_settings, mock_rag_settings, mock_bedrock_cls, mock_emb_cls,
):
    """Sessions with only general-route turns return zero rag_score without writing eval."""
    _apply_settings(mock_conv_settings)
    _apply_settings(mock_rag_settings)

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_conversations_table(dynamodb)
    eval_table = _create_evaluations_table(dynamodb)
    _create_hitl_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("pipe-general", 1, {
        "user_query": "Hello",
        "ai_response": "Hi there!",
        "route": "general",
        "retrieved_docs": [],
    })

    from evaluations.rag_evaluator import evaluate_session
    result = evaluate_session("pipe-general")

    assert result["rag_score"] == 0.0
    assert result["hitl_flagged"] is False

    # No eval record should be written for general-only sessions
    from boto3.dynamodb.conditions import Key
    rag_evals = eval_table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("rag"),
    )["Items"]
    assert len(rag_evals) == 0
