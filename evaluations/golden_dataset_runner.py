import boto3
import json
import uuid
from datetime import datetime, timezone
from src.setting.config import settings
from src.services.bedrock import BedrockService
from src.services.s3 import S3Service
from src.tools.rag import semantic_document_search

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "faithfulness": {"type": "number", "description": "0-1: answer grounded in retrieved docs"},
        "relevance": {"type": "number", "description": "0-1: docs relevant to question"},
        "reason": {"type": "string"},
    },
    "required": ["faithfulness", "relevance", "reason"],
}


def load_golden_dataset(bucket: str, key: str = "golden.json") -> list[dict]:
    s3 = S3Service()
    text, _ = s3.read_document(bucket, key)
    return json.loads(text)


def run_golden_question(question: str, expected_answer: str) -> dict:
    bedrock = BedrockService()
    retrieved = semantic_document_search.invoke({"query": question, "top_k": 5})
    docs_text = "\n".join(
        d.get("text", str(d))[:300] for d in retrieved
    ) if retrieved else ""

    answer = bedrock.converse_text(
        user_message=(
            f"Answer this question using the provided context.\n\n"
            f"Context:\n{docs_text}\n\nQuestion: {question}"
        ),
        max_tokens=512,
    )

    scores = bedrock.converse_structured(
        user_message=(
            f"Question: {question}\n"
            f"Expected answer: {expected_answer}\n"
            f"Retrieved docs: {docs_text}\n"
            f"Generated answer: {answer}\n\n"
            "Score faithfulness (0-1): is the generated answer grounded in retrieved docs? "
            "Score relevance (0-1): are the retrieved docs relevant to the question?"
        ),
        json_schema=JUDGE_SCHEMA,
        schema_name="golden_judge",
        schema_description="LLM judge scores for golden dataset evaluation",
    )

    faithfulness = float(scores.get("faithfulness", 0))
    relevance = float(scores.get("relevance", 0))
    avg_score = (faithfulness + relevance) / 2
    return {
        "answer": answer,
        "faithfulness": faithfulness,
        "relevance": relevance,
        "avg_score": avg_score,
        "pass": avg_score >= settings.GOLDEN_PASS_THRESHOLD,
        "reason": scores.get("reason", ""),
    }


def run_golden_dataset(bucket: str | None = None) -> dict:
    bucket = bucket or settings.S3_BUCKET_NAME
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    table = dynamodb.Table(settings.GOLDEN_RESULTS_TABLE)
    dataset = load_golden_dataset(bucket)
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    results = []
    for item in dataset:
        question_id = item.get("question_id", str(uuid.uuid4()))
        question = item["question"]
        expected = item.get("expected_answer", "")
        try:
            result = run_golden_question(question, expected)
        except Exception as e:
            result = {
                "answer": "", "faithfulness": 0.0, "relevance": 0.0,
                "avg_score": 0.0, "pass": False, "reason": str(e),
            }
        table.put_item(Item={
            "run_id": run_id,
            "question_id": question_id,
            "question": question,
            "expected_answer": expected,
            "generated_answer": result["answer"],
            "faithfulness": str(round(result["faithfulness"], 4)),
            "relevance": str(round(result["relevance"], 4)),
            "avg_score": str(round(result["avg_score"], 4)),
            "pass": result["pass"],
            "reason": result["reason"],
            "created_at": now,
        })
        results.append({"question_id": question_id, "pass": result["pass"], "avg_score": result["avg_score"]})

    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    return {
        "run_id": run_id,
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
    }


def handler(event, context):
    bucket = event.get("bucket") or settings.S3_BUCKET_NAME
    return run_golden_dataset(bucket)
