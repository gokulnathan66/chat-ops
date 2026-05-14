from __future__ import annotations

import logging
from datetime import UTC, datetime

import boto3
from boto3.dynamodb.conditions import Key

from src.services.bedrock import BedrockService
from src.services.embedding import EmbeddingService
from src.setting.config import settings
from src.tools.rag import rag_tool_service

logging.getLogger().setLevel(logging.INFO)
logger = logging.getLogger(__name__)

_GOLDEN_EVAL_TYPE = "golden_query"
_GOLDEN_SK = "golden_query"

LLM_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "faithfulness": {"type": "number", "description": "0-1: is the answer grounded in retrieved docs?"},
        "relevance": {"type": "number", "description": "0-1: are retrieved docs relevant to the question?"},
        "reason": {"type": "string"},
    },
    "required": ["faithfulness", "relevance", "reason"],
}


def _eval_table():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(settings.EVALUATIONS_TABLE)


def compute_rag_score(query_emb: list, doc_embs: list) -> float:
    if not doc_embs:
        return 0.0
    scores = [sum(q * d for q, d in zip(query_emb, doc_emb, strict=False)) for doc_emb in doc_embs]
    return max(scores)


def run_llm_judge(question: str, retrieved_docs: list[dict], answer: str) -> dict:
    bedrock = BedrockService()
    docs_text = "\n".join(d.get("text", "") for d in retrieved_docs)
    prompt = (
        f"Question: {question}\n"
        f"Retrieved documents: {docs_text}\n"
        f"Answer: {answer}\n\n"
        "Score faithfulness (0-1): is the answer grounded in the retrieved documents? "
        "Score relevance (0-1): are the retrieved documents relevant to the question? "
        "Provide a brief reason."
    )
    return bedrock.converse_structured(
        user_message=prompt,
        json_schema=LLM_JUDGE_SCHEMA,
        schema_name="llm_judge",
        schema_description="LLM-as-judge evaluation scores",
    )


def load_golden_queries() -> list[dict]:
    resp = _eval_table().query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq(_GOLDEN_EVAL_TYPE),
    )
    return resp.get("Items", [])


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _eval_single_query(query: str, job_id: str) -> dict:
    emb_svc = EmbeddingService()

    logger.info("RAG search start | query='%s'", query[:80])
    results = rag_tool_service.search(query=query, top_k=settings.top_k)
    logger.info("RAG search done | query='%s' hits=%d", query[:80], len(results))

    if not results:
        logger.warning("No results from Qdrant | query='%s' — check collection has docs", query[:80])

    query_emb = emb_svc.embed_query(query)
    logger.info("Query embedded | dim=%d", len(query_emb))

    doc_texts = [r.get("text", "") for r in results if r.get("text")]
    logger.info("Doc texts for embedding | count=%d", len(doc_texts))

    doc_embs = emb_svc.embed_texts(doc_texts) if doc_texts else []
    rag_score = compute_rag_score(query_emb, doc_embs)
    logger.info("RAG score | query='%s' score=%.4f", query[:80], rag_score)

    top_answer = results[0].get("text", "") if results else ""
    logger.info("Running LLM judge | query='%s' top_answer_len=%d", query[:80], len(top_answer))
    judge = run_llm_judge(question=query, retrieved_docs=results, answer=top_answer)
    logger.info("LLM judge raw response | %s", judge)

    faithfulness = _safe_float(judge.get("faithfulness"))
    relevance = _safe_float(judge.get("relevance"))
    logger.info("Scores | query='%s' rag=%.4f faithfulness=%.4f relevance=%.4f", query[:80], rag_score, faithfulness, relevance)

    now = datetime.now(UTC).isoformat()
    _eval_table().put_item(Item={
        "session_id": job_id,
        "sk": f"eval#rag#{now}",
        "eval_type": "rag",
        "query": query,
        "rag_score": str(round(rag_score, 4)),
        "faithfulness": str(round(faithfulness, 4)),
        "relevance": str(round(relevance, 4)),
        "created_at": now,
    })
    logger.info("DynamoDB write done | job_id=%s query='%s'", job_id, query[:80])

    return {
        "query": query,
        "rag_score": rag_score,
        "faithfulness": faithfulness,
        "relevance": relevance,
    }


def run_ingestion_evals(job_id: str) -> list[dict]:
    """Run all golden queries against Qdrant and store results linked to the ingestion job."""
    logger.info("Loading golden queries | job_id=%s", job_id)
    golden_queries = load_golden_queries()
    logger.info("Golden queries loaded | count=%d job_id=%s", len(golden_queries), job_id)

    if not golden_queries:
        logger.warning("No golden queries defined — skipping RAG eval for job_id=%s", job_id)
        return []

    logger.info("Running RAG evals | job_id=%s queries=%d", job_id, len(golden_queries))
    results = []
    for gq in golden_queries:
        query = gq.get("query", "").strip()
        if not query:
            continue
        try:
            result = _eval_single_query(query, job_id)
            results.append(result)
            logger.info("Eval done | query=%s rag_score=%.3f", query[:60], result["rag_score"])
        except Exception:
            logger.exception("Eval failed | query=%s job_id=%s", query[:60], job_id)
            results.append({"query": query, "error": True})

    logger.info("RAG evals complete | job_id=%s evaluated=%d", job_id, len(results))
    return results


def handler(event, context):
    session_id = event.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    return run_ingestion_evals(session_id)
