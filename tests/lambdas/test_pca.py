import pytest
from unittest.mock import patch, MagicMock
from src.lambdas.pca import analyze_conversation, handler

PCA_OUTPUT = {
    "topics": ["pricing", "availability"],
    "sentiment": "positive",
    "unresolved_questions": ["Is bulk discount available?"],
}


@patch("src.lambdas.pca.BedrockService")
@patch("src.lambdas.pca.ConversationService")
@patch("src.lambdas.pca.settings")
def test_analyze_conversation_writes_pca_eval(mock_settings, mock_conv_cls, mock_bedrock_cls):
    mock_settings.EVALUATIONS_TABLE = "evaluations"
    mock_settings.AWS_REGION = "us-east-1"

    mock_conv = MagicMock()
    mock_conv_cls.return_value = mock_conv
    mock_conv.get_conversation.return_value = {
        "metadata": {"session_id": "s-pca-1"},
        "turns": [
            {"user_query": "What is pricing?", "ai_response": "It's $49."},
            {"user_query": "Is bulk discount available?", "ai_response": "I don't know."},
        ],
    }

    mock_bedrock = MagicMock()
    mock_bedrock_cls.return_value = mock_bedrock
    mock_bedrock.converse_structured.return_value = PCA_OUTPUT.copy()

    mock_dynamo = MagicMock()
    with patch("src.lambdas.pca.boto3") as mock_boto3:
        mock_boto3.resource.return_value.Table.return_value = mock_dynamo
        result = analyze_conversation("s-pca-1")

    assert result["pca_topics"] == ["pricing", "availability"]
    assert result["pca_sentiment"] == "positive"
    assert "Is bulk discount" in result["pca_unresolved"][0]
    mock_dynamo.put_item.assert_called_once()
    call_args = mock_dynamo.put_item.call_args[1]["Item"]
    assert call_args["eval_type"] == "pca"


@patch("src.lambdas.pca.analyze_conversation")
def test_handler_calls_analyze(mock_analyze):
    mock_analyze.return_value = {"pca_topics": [], "pca_sentiment": "neutral", "pca_unresolved": []}
    result = handler({"session_id": "s1"}, {})
    mock_analyze.assert_called_once_with("s1")
    assert "pca_topics" in result


def test_handler_missing_session_id():
    result = handler({}, {})
    assert "error" in result
