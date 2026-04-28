import boto3
from datetime import datetime, timezone
from src.setting.config import settings
from src.services.bedrock import BedrockService
from src.services.embedding import EmbeddingService
from src.services.conversation import ConversationService

LLM_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "faithfulness": {"type": "number", "description": "0-1: is the answer grounded in retrieved docs?"},
        "relevance": {"type": "number", "description": "0-1: are retrieved docs relevant to the question?"},
        "reason": {"type": "string"},
    },
    "required": ["faithfulness", "relevance", "reason"],
}


def compute_rag_score(query_emb: list, doc_embs: list) -> float:
    if not doc_embs:
        return 0.0
    scores = [sum(q * d for q, d in zip(query_emb, doc_emb)) for doc_emb in doc_embs]
    return max(scores)


def run_llm_judge(question: str, retrieved_docs: list[dict], answer: str) -> dict:
    bedrock = BedrockService()
    docs_text = "\n".join(d.get("text_snippet", "") for d in retrieved_docs)
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
        schema_description="LLM-as-judge evaluation scores for faithfulness and relevance",
    )


def evaluate_session(session_id: str) -> dict:
    conv_svc = ConversationService()
    emb_svc = EmbeddingService()
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    eval_table = dynamodb.Table(settings.EVALUATIONS_TABLE)

    conv = conv_svc.get_conversation(session_id)
    tools_turns = [t for t in conv["turns"] if t.get("route") == "tools"]

    if not tools_turns:
        return {"rag_score": 0.0, "faithfulness": 0.0, "relevance": 0.0, "hitl_flagged": False}

    all_rag_scores, all_faithfulness, all_relevance = [], [], []
    hitl_flagged = False

    for turn in tools_turns:
        query = turn["user_query"]
        answer = turn["ai_response"]
        retrieved_docs = turn.get("retrieved_docs", [])

        query_emb = emb_svc.embed_query(query)
        doc_texts = [d.get("text_snippet", "") for d in retrieved_docs if d.get("text_snippet")]
        doc_embs = emb_svc.embed_texts(doc_texts) if doc_texts else []
        rag_score = compute_rag_score(query_emb, doc_embs)

        judge = run_llm_judge(question=query, retrieved_docs=retrieved_docs, answer=answer)

        if rag_score < settings.RAG_THRESHOLD:
            from src.tools.rag import semantic_document_search
            reranked = semantic_document_search.invoke({"query": query, "top_k": 10})
            reranked_text = str(reranked)[:500]
            reranked_embs = emb_svc.embed_texts([reranked_text])
            rag_score = compute_rag_score(query_emb, reranked_embs)
            if rag_score < settings.HITL_THRESHOLD:
                hitl_flagged = True

        all_rag_scores.append(rag_score)
        all_faithfulness.append(float(judge.get("faithfulness", 0)))
        all_relevance.append(float(judge.get("relevance", 0)))

    avg_rag = sum(all_rag_scores) / len(all_rag_scores)
    avg_faith = sum(all_faithfulness) / len(all_faithfulness)
    avg_rel = sum(all_relevance) / len(all_relevance)
    now = datetime.now(timezone.utc).isoformat()

    eval_table.put_item(Item={
        "session_id": session_id,
        "sk": f"eval#rag#{now}",
        "eval_type": "rag",
        "rag_score": str(round(avg_rag, 4)),
        "faithfulness": str(round(avg_faith, 4)),
        "relevance": str(round(avg_rel, 4)),
        "re_retrieved": str(any(s < settings.RAG_THRESHOLD for s in all_rag_scores)),
        "hitl_flagged": hitl_flagged,
        "created_at": now,
    })

    if hitl_flagged:
        conv_svc.write_hitl(session_id, "rag_eval", {
            "rag_score": avg_rag,
            "llm_judge_score": avg_faith,
        })

    return {
        "rag_score": avg_rag,
        "faithfulness": avg_faith,
        "relevance": avg_rel,
        "hitl_flagged": hitl_flagged,
    }


def handler(event, context):
    session_id = event.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    return evaluate_session(session_id)
