import pytest
from unittest.mock import patch, MagicMock
from src.lambdas.golden_dataset_runner import (
    load_golden_dataset,
    run_golden_question,
    run_golden_dataset,
    handler,
)

GOLDEN_DATA = [
    {"question_id": "q1", "question": "What is pricing?", "expected_answer": "It is $49/mo."},
    {"question_id": "q2", "question": "What is the refund policy?", "expected_answer": "30-day refund."},
]


@patch("src.lambdas.golden_dataset_runner.S3Service")
def test_load_golden_dataset(mock_s3_cls):
    import json
    mock_s3 = MagicMock()
    mock_s3_cls.return_value = mock_s3
    mock_s3.read_document.return_value = (json.dumps(GOLDEN_DATA), {})

    result = load_golden_dataset("my-bucket", "golden.json")
    assert len(result) == 2
    assert result[0]["question_id"] == "q1"


@patch("src.lambdas.golden_dataset_runner.semantic_document_search")
@patch("src.lambdas.golden_dataset_runner.BedrockService")
def test_run_golden_question_pass(mock_bedrock_cls, mock_search):
    mock_bedrock = MagicMock()
    mock_bedrock_cls.return_value = mock_bedrock
    mock_bedrock.converse_text.return_value = "Pricing is $49/mo."
    mock_bedrock.converse_structured.return_value = {
        "faithfulness": 0.9, "relevance": 0.88, "reason": "well grounded"
    }
    mock_search.invoke.return_value = [{"text_snippet": "Pricing is $49/mo."}]

    result = run_golden_question("What is pricing?", "It is $49/mo.")
    assert result["pass"] is True
    assert result["avg_score"] == pytest.approx(0.89)
    assert result["faithfulness"] == pytest.approx(0.9)


@patch("src.lambdas.golden_dataset_runner.semantic_document_search")
@patch("src.lambdas.golden_dataset_runner.BedrockService")
def test_run_golden_question_fail(mock_bedrock_cls, mock_search):
    mock_bedrock = MagicMock()
    mock_bedrock_cls.return_value = mock_bedrock
    mock_bedrock.converse_text.return_value = "I don't know."
    mock_bedrock.converse_structured.return_value = {
        "faithfulness": 0.3, "relevance": 0.2, "reason": "not grounded"
    }
    mock_search.invoke.return_value = []

    result = run_golden_question("What is pricing?", "It is $49/mo.")
    assert result["pass"] is False
    assert result["avg_score"] < 0.7


@patch("src.lambdas.golden_dataset_runner.settings")
@patch("src.lambdas.golden_dataset_runner.run_golden_question")
@patch("src.lambdas.golden_dataset_runner.load_golden_dataset")
@patch("src.lambdas.golden_dataset_runner.boto3")
def test_run_golden_dataset_writes_results(mock_boto3, mock_load, mock_run_q, mock_settings):
    mock_settings.AWS_REGION = "us-east-1"
    mock_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_settings.S3_BUCKET_NAME = "my-bucket"
    mock_settings.GOLDEN_PASS_THRESHOLD = 0.7

    mock_load.return_value = GOLDEN_DATA
    mock_run_q.side_effect = [
        {"answer": "A1", "faithfulness": 0.9, "relevance": 0.85, "avg_score": 0.875, "pass": True, "reason": "ok"},
        {"answer": "A2", "faithfulness": 0.4, "relevance": 0.3, "avg_score": 0.35, "pass": False, "reason": "bad"},
    ]

    mock_table = MagicMock()
    mock_boto3.resource.return_value.Table.return_value = mock_table

    result = run_golden_dataset("my-bucket")
    assert result["total"] == 2
    assert result["passed"] == 1
    assert result["pass_rate"] == pytest.approx(0.5)
    assert mock_table.put_item.call_count == 2


@patch("src.lambdas.golden_dataset_runner.run_golden_dataset")
def test_handler_calls_run(mock_run):
    mock_run.return_value = {"run_id": "r1", "total": 2, "passed": 1, "pass_rate": 0.5}
    result = handler({"bucket": "my-bucket"}, {})
    mock_run.assert_called_once_with("my-bucket")
    assert result["run_id"] == "r1"
