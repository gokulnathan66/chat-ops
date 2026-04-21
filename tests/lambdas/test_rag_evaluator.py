import pytest
from unittest.mock import patch, MagicMock
from src.lambdas.rag_evaluator import compute_rag_score, run_llm_judge, evaluate_session


def test_compute_rag_score_high_similarity():
    query_emb = [1.0, 0.0, 0.0]
    norm = (0.99**2 + 0.1**2) ** 0.5
    doc_emb_norm = [0.99 / norm, 0.1 / norm, 0.0]
    score = compute_rag_score(query_emb, [doc_emb_norm])
    assert score > 0.9


def test_compute_rag_score_low_similarity():
    query_emb = [1.0, 0.0, 0.0]
    doc_emb = [0.0, 1.0, 0.0]
    score = compute_rag_score(query_emb, [doc_emb])
    assert score < 0.2


def test_compute_rag_score_empty_docs():
    query_emb = [1.0, 0.0, 0.0]
    score = compute_rag_score(query_emb, [])
    assert score == 0.0


@patch("src.lambdas.rag_evaluator.BedrockService")
def test_run_llm_judge_returns_scores(mock_bedrock_cls):
    mock_bedrock = MagicMock()
    mock_bedrock_cls.return_value = mock_bedrock
    mock_bedrock.converse_structured.return_value = {
        "faithfulness": 0.85,
        "relevance": 0.78,
        "reason": "The answer is grounded in the retrieved documents.",
    }
    result = run_llm_judge(
        question="What is pricing?",
        retrieved_docs=[{"text_snippet": "Pricing is $49/mo."}],
        answer="Pricing is $49/mo.",
    )
    assert result["faithfulness"] == pytest.approx(0.85)
    assert result["relevance"] == pytest.approx(0.78)
    assert "reason" in result


@patch("src.lambdas.rag_evaluator.BedrockService")
@patch("src.lambdas.rag_evaluator.EmbeddingService")
@patch("src.lambdas.rag_evaluator.ConversationService")
@patch("src.lambdas.rag_evaluator.settings")
def test_evaluate_session_writes_eval_record(
    mock_settings, mock_conv_cls, mock_emb_cls, mock_bedrock_cls
):
    mock_settings.RAG_THRESHOLD = 0.6
    mock_settings.HITL_THRESHOLD = 0.6
    mock_settings.EVALUATIONS_TABLE = "evaluations"
    mock_settings.AWS_REGION = "us-east-1"

    mock_conv = MagicMock()
    mock_conv_cls.return_value = mock_conv
    mock_conv.get_conversation.return_value = {
        "metadata": {"session_id": "s1", "status": "complete"},
        "turns": [{
            "sk": "turn#001",
            "user_query": "What is pricing?",
            "ai_response": "Pricing is $49.",
            "route": "tools",
            "retrieved_docs": [{"text_snippet": "Pricing is $49/mo."}],
        }],
    }

    mock_emb = MagicMock()
    mock_emb_cls.return_value = mock_emb
    mock_emb.embed_query.return_value = [1.0, 0.0]
    mock_emb.embed_texts.return_value = [[0.99, 0.1]]

    mock_bedrock = MagicMock()
    mock_bedrock_cls.return_value = mock_bedrock
    mock_bedrock.converse_structured.return_value = {
        "faithfulness": 0.9, "relevance": 0.88, "reason": "good"
    }

    mock_dynamo = MagicMock()
    with patch("src.lambdas.rag_evaluator.boto3") as mock_boto3:
        mock_boto3.resource.return_value.Table.return_value = mock_dynamo
        result = evaluate_session("s1")

    assert result["rag_score"] > 0
    assert result["faithfulness"] == pytest.approx(0.9)
    assert result["hitl_flagged"] is False
    mock_dynamo.put_item.assert_called_once()
