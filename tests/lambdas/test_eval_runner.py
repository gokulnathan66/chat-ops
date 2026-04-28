import pytest
from unittest.mock import patch, MagicMock
from evaluations.eval_runner import get_stale_sessions, run_evals_for_session, handler


@patch("evaluations.eval_runner.settings")
@patch("evaluations.eval_runner.boto3")
def test_get_stale_sessions(mock_boto3, mock_settings):
    mock_settings.AWS_REGION = "us-east-1"
    mock_settings.CONVERSATIONS_TABLE = "conversations"
    mock_settings.INACTIVITY_MINUTES = 15

    mock_table = MagicMock()
    mock_boto3.resource.return_value.Table.return_value = mock_table
    mock_table.query.return_value = {
        "Items": [{"session_id": "s1"}, {"session_id": "s2"}]
    }

    result = get_stale_sessions()
    assert result == ["s1", "s2"]
    mock_table.query.assert_called_once()


@patch("evaluations.eval_runner.analyze_conversation")
@patch("evaluations.eval_runner.evaluate_session")
@patch("evaluations.eval_runner.ConversationService")
def test_run_evals_for_session(mock_conv_cls, mock_eval, mock_pca):
    mock_conv = MagicMock()
    mock_conv_cls.return_value = mock_conv
    mock_eval.return_value = {"rag_score": 0.8, "faithfulness": 0.9, "relevance": 0.85, "hitl_flagged": False}
    mock_pca.return_value = {"pca_topics": ["pricing"], "pca_sentiment": "positive", "pca_unresolved": []}

    result = run_evals_for_session("s1")

    mock_conv.mark_complete.assert_called_once_with("s1")
    mock_eval.assert_called_once_with("s1")
    mock_pca.assert_called_once_with("s1")
    assert result["session_id"] == "s1"
    assert result["rag"]["rag_score"] == pytest.approx(0.8)
    assert result["pca"]["pca_sentiment"] == "positive"


@patch("evaluations.eval_runner.run_evals_for_session")
@patch("evaluations.eval_runner.get_stale_sessions")
def test_handler_evaluates_stale_sessions(mock_stale, mock_run):
    mock_stale.return_value = ["s1", "s2"]
    mock_run.side_effect = [
        {"session_id": "s1", "rag": {}, "pca": {}},
        {"session_id": "s2", "rag": {}, "pca": {}},
    ]

    result = handler({}, {})
    assert result["evaluated"] == 2
    assert len(result["results"]) == 2


@patch("evaluations.eval_runner.run_evals_for_session")
@patch("evaluations.eval_runner.get_stale_sessions")
def test_handler_handles_errors(mock_stale, mock_run):
    mock_stale.return_value = ["s-bad"]
    mock_run.side_effect = Exception("DynamoDB error")

    result = handler({}, {})
    assert result["evaluated"] == 1
    assert "error" in result["results"][0]
