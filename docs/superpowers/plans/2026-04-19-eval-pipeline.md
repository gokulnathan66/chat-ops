# Eval Lambda Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the 4 evaluation Lambda functions: eval_runner (cron orchestrator), rag_evaluator (embedding similarity + LLM-as-judge + re-retrieve + HITL), pca (post-conversation analysis), and golden_dataset_runner (golden dataset scoring).

**Architecture:** eval_runner is the cron entrypoint — it queries DynamoDB for idle/complete sessions and calls rag_evaluator and pca per session, then writes cost evaluations. golden_dataset_runner runs independently on its own cron. All Lambdas share ConversationService for DynamoDB access. Bedrock is used for LLM-as-judge scoring and PCA analysis.

**Tech Stack:** Python 3.13, boto3, AWS Bedrock, Qdrant, sentence-transformers, LangGraph (golden runner invokes graph directly), moto[dynamodb] (tests), uv

**Prerequisite:** Backend Core plan must be complete (ConversationService, DynamoDB tables, settings).

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/lambdas/eval_runner.py` | Cron entrypoint: scan idle sessions, orchestrate eval + cost |
| Modify | `src/lambdas/rag_evaluator.py` | Embedding similarity + LLM-as-judge + re-retrieve + HITL flag |
| Modify | `src/lambdas/pca.py` | Bedrock structured PCA: topics, sentiment, unresolved |
| Create | `src/lambdas/golden_dataset_runner.py` | Load golden.json from S3, run through LangGraph, score |
| Create | `tests/lambdas/__init__.py` | |
| Create | `tests/lambdas/test_rag_evaluator.py` | |
| Create | `tests/lambdas/test_pca.py` | |
| Create | `tests/lambdas/test_eval_runner.py` | |
| Create | `tests/lambdas/test_golden_dataset_runner.py` | |
| Modify | `iac/terraform-aws/lambda.tf` | Add 4 Lambda function definitions |
| Modify | `iac/terraform-aws/cloudwatch.tf` | EventBridge cron rules |

---

## Task 1: rag_evaluator — embedding similarity + LLM-as-judge

**Files:**
- Modify: `src/lambdas/rag_evaluator.py`
- Create: `tests/lambdas/__init__.py`
- Create: `tests/lambdas/test_rag_evaluator.py`

- [ ] **Step 1: Write failing tests**

```bash
mkdir -p tests/lambdas
touch tests/lambdas/__init__.py
```

Create `tests/lambdas/test_rag_evaluator.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from src.lambdas.rag_evaluator import compute_rag_score, run_llm_judge, evaluate_session


def test_compute_rag_score_high_similarity():
    import numpy as np
    query_emb = np.array([1.0, 0.0, 0.0])
    doc_emb = np.array([0.99, 0.1, 0.0])
    doc_emb = doc_emb / np.linalg.norm(doc_emb)
    score = compute_rag_score(query_emb, [doc_emb])
    assert score > 0.9


def test_compute_rag_score_low_similarity():
    import numpy as np
    query_emb = np.array([1.0, 0.0, 0.0])
    doc_emb = np.array([0.0, 1.0, 0.0])
    score = compute_rag_score(query_emb, [doc_emb])
    assert score < 0.2


def test_compute_rag_score_empty_docs():
    import numpy as np
    query_emb = np.array([1.0, 0.0, 0.0])
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
    import numpy as np
    mock_emb.embed_query.return_value = np.array([1.0, 0.0])
    mock_emb.embed_texts.return_value = [np.array([0.99, 0.1])]

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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/lambdas/test_rag_evaluator.py -v
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Implement `src/lambdas/rag_evaluator.py`**

```python
import json
import boto3
import numpy as np
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key
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

LLM_JUDGE_PROMPT = """You are an evaluator. Given a question, retrieved documents, and an AI answer, score:
- faithfulness (0-1): Is the answer grounded in the retrieved documents?
- relevance (0-1): Are the retrieved documents relevant to the question?

Question: {question}
Retrieved documents: {docs}
Answer: {answer}

Return JSON with faithfulness, relevance, and reason."""


def compute_rag_score(query_emb: np.ndarray, doc_embs: list[np.ndarray]) -> float:
    if not doc_embs:
        return 0.0
    scores = [float(np.dot(query_emb, d)) for d in doc_embs]
    return max(scores)


def run_llm_judge(question: str, retrieved_docs: list[dict], answer: str) -> dict:
    bedrock = BedrockService()
    docs_text = "\n".join(d.get("text_snippet", "") for d in retrieved_docs)
    prompt = LLM_JUDGE_PROMPT.format(question=question, docs=docs_text, answer=answer)
    return bedrock.converse_structured(
        messages=[{"role": "user", "content": prompt}],
        output_schema=LLM_JUDGE_SCHEMA,
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
            reranked_docs = [{"text_snippet": str(reranked)[:500]}]
            reranked_embs = emb_svc.embed_texts([str(reranked)[:500]])
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
    result = evaluate_session(session_id)
    return result
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/lambdas/test_rag_evaluator.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/lambdas/rag_evaluator.py tests/lambdas/test_rag_evaluator.py tests/lambdas/__init__.py
git commit -m "feat: implement rag_evaluator with embedding similarity, LLM-as-judge, re-retrieve, and HITL"
```

---

## Task 2: pca — post-conversation analysis

**Files:**
- Modify: `src/lambdas/pca.py`
- Create: `tests/lambdas/test_pca.py`

- [ ] **Step 1: Write failing tests**

Create `tests/lambdas/test_pca.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from src.lambdas.pca import analyze_conversation, handler

PCA_OUTPUT_SCHEMA = {
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
    mock_bedrock.converse_structured.return_value = PCA_OUTPUT_SCHEMA.copy()

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
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/lambdas/test_pca.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `src/lambdas/pca.py`**

```python
import boto3
from datetime import datetime, timezone
from src.setting.config import settings
from src.services.bedrock import BedrockService
from src.services.conversation import ConversationService

PCA_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Main topics discussed in the conversation",
        },
        "sentiment": {
            "type": "string",
            "enum": ["positive", "neutral", "negative"],
            "description": "Overall user sentiment",
        },
        "unresolved_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Questions the user asked that were not fully answered",
        },
    },
    "required": ["topics", "sentiment", "unresolved_questions"],
}

PCA_PROMPT = """Analyze this conversation between a user and an AI assistant.

Conversation:
{conversation}

Return JSON with:
- topics: list of main topics discussed
- sentiment: overall user sentiment (positive, neutral, or negative)
- unresolved_questions: questions the user asked that were not clearly answered"""


def analyze_conversation(session_id: str) -> dict:
    conv_svc = ConversationService()
    bedrock = BedrockService()
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    eval_table = dynamodb.Table(settings.EVALUATIONS_TABLE)

    conv = conv_svc.get_conversation(session_id)
    turns = conv["turns"]

    if not turns:
        return {"pca_topics": [], "pca_sentiment": "neutral", "pca_unresolved": []}

    conversation_text = "\n".join(
        f"User: {t['user_query']}\nAssistant: {t['ai_response']}" for t in turns
    )

    prompt = PCA_PROMPT.format(conversation=conversation_text)
    result = bedrock.converse_structured(
        messages=[{"role": "user", "content": prompt}],
        output_schema=PCA_SCHEMA,
    )

    now = datetime.now(timezone.utc).isoformat()
    eval_table.put_item(Item={
        "session_id": session_id,
        "sk": f"eval#pca#{now}",
        "eval_type": "pca",
        "pca_topics": result.get("topics", []),
        "pca_sentiment": result.get("sentiment", "neutral"),
        "pca_unresolved": result.get("unresolved_questions", []),
        "created_at": now,
    })

    return {
        "pca_topics": result.get("topics", []),
        "pca_sentiment": result.get("sentiment", "neutral"),
        "pca_unresolved": result.get("unresolved_questions", []),
    }


def handler(event, context):
    session_id = event.get("session_id")
    if not session_id:
        return {"error": "session_id required"}
    return analyze_conversation(session_id)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/lambdas/test_pca.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/lambdas/pca.py tests/lambdas/test_pca.py
git commit -m "feat: implement pca lambda for post-conversation analysis"
```

---

## Task 3: eval_runner — cron orchestrator + cost eval

**Files:**
- Create: `src/lambdas/eval_runner.py`
- Create: `tests/lambdas/test_eval_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/lambdas/test_eval_runner.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone, timedelta


@patch("src.lambdas.eval_runner.analyze_conversation")
@patch("src.lambdas.eval_runner.evaluate_session")
@patch("src.lambdas.eval_runner.ConversationService")
@patch("src.lambdas.eval_runner.settings")
def test_eval_runner_processes_complete_sessions(
    mock_settings, mock_conv_cls, mock_eval, mock_pca
):
    mock_settings.INACTIVITY_MINUTES = 15
    mock_settings.AWS_REGION = "us-east-1"

    mock_conv = MagicMock()
    mock_conv_cls.return_value = mock_conv
    mock_conv.list_conversations.return_value = [
        {"session_id": "s1", "status": "complete"},
        {"session_id": "s2", "status": "complete"},
    ]
    mock_eval.return_value = {"rag_score": 0.9, "faithfulness": 0.85, "hitl_flagged": False}
    mock_pca.return_value = {"pca_topics": ["pricing"], "pca_sentiment": "positive"}

    from src.lambdas.eval_runner import run_eval_cycle
    result = run_eval_cycle()

    assert mock_eval.call_count == 2
    assert mock_pca.call_count == 2
    assert result["sessions_evaluated"] == 2


@patch("src.lambdas.eval_runner.ConversationService")
@patch("src.lambdas.eval_runner.settings")
def test_eval_runner_marks_active_sessions_complete(mock_settings, mock_conv_cls):
    mock_settings.INACTIVITY_MINUTES = 15
    mock_settings.AWS_REGION = "us-east-1"

    stale_time = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
    mock_conv = MagicMock()
    mock_conv_cls.return_value = mock_conv
    mock_conv.list_conversations.side_effect = [
        [{"session_id": "s-stale", "status": "active", "last_updated_at": stale_time}],
        [],
    ]

    from src.lambdas.eval_runner import mark_idle_sessions_complete
    count = mark_idle_sessions_complete(mock_conv)
    mock_conv.mark_complete.assert_called_once_with("s-stale")
    assert count == 1


@patch("src.lambdas.eval_runner.analyze_conversation")
@patch("src.lambdas.eval_runner.evaluate_session")
@patch("src.lambdas.eval_runner.ConversationService")
@patch("src.lambdas.eval_runner.settings")
def test_eval_runner_writes_cost_eval(mock_settings, mock_conv_cls, mock_eval, mock_pca):
    mock_settings.INACTIVITY_MINUTES = 15
    mock_settings.AWS_REGION = "us-east-1"
    mock_settings.EVALUATIONS_TABLE = "evaluations"

    mock_conv = MagicMock()
    mock_conv_cls.return_value = mock_conv
    mock_conv.list_conversations.return_value = [{"session_id": "s3", "status": "complete"}]
    mock_conv.get_conversation.return_value = {
        "metadata": {"session_id": "s3"},
        "turns": [{"token_usage": {"input": 200, "output": 100}}],
    }
    mock_eval.return_value = {}
    mock_pca.return_value = {}

    mock_dynamo = MagicMock()
    with patch("src.lambdas.eval_runner.boto3") as mock_boto3:
        mock_boto3.resource.return_value.Table.return_value = mock_dynamo
        from src.lambdas.eval_runner import run_eval_cycle
        run_eval_cycle()

    mock_dynamo.put_item.assert_called_once()
    call_item = mock_dynamo.put_item.call_args[1]["Item"]
    assert call_item["eval_type"] == "cost"
    assert float(call_item["cost_usd"]) > 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/lambdas/test_eval_runner.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `src/lambdas/eval_runner.py`**

```python
import boto3
from datetime import datetime, timezone, timedelta
from src.setting.config import settings
from src.services.conversation import ConversationService
from src.lambdas.rag_evaluator import evaluate_session
from src.lambdas.pca import analyze_conversation

# Approximate Bedrock pricing for Claude Haiku (USD per 1K tokens)
BEDROCK_INPUT_PRICE_PER_1K = 0.00025
BEDROCK_OUTPUT_PRICE_PER_1K = 0.00125


def mark_idle_sessions_complete(conv_svc: ConversationService) -> int:
    threshold = datetime.now(timezone.utc) - timedelta(minutes=settings.INACTIVITY_MINUTES)
    active_sessions = conv_svc.list_conversations("active", limit=200)
    marked = 0
    for session in active_sessions:
        last_updated = session.get("last_updated_at", "")
        if last_updated and last_updated < threshold.isoformat():
            conv_svc.mark_complete(session["session_id"])
            marked += 1
    return marked


def write_cost_eval(session_id: str, conv_svc: ConversationService) -> None:
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    eval_table = dynamodb.Table(settings.EVALUATIONS_TABLE)

    conv = conv_svc.get_conversation(session_id)
    total_input = sum(int(t.get("token_usage", {}).get("input", 0)) for t in conv["turns"])
    total_output = sum(int(t.get("token_usage", {}).get("output", 0)) for t in conv["turns"])
    cost_usd = (
        (total_input / 1000 * BEDROCK_INPUT_PRICE_PER_1K) +
        (total_output / 1000 * BEDROCK_OUTPUT_PRICE_PER_1K)
    )

    now = datetime.now(timezone.utc).isoformat()
    eval_table.put_item(Item={
        "session_id": session_id,
        "sk": f"eval#cost#{now}",
        "eval_type": "cost",
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "cost_usd": str(round(cost_usd, 6)),
        "created_at": now,
    })


def run_eval_cycle() -> dict:
    conv_svc = ConversationService()
    marked = mark_idle_sessions_complete(conv_svc)
    complete_sessions = conv_svc.list_conversations("complete", limit=200)

    evaluated = 0
    for session in complete_sessions:
        session_id = session["session_id"]
        try:
            evaluate_session(session_id)
            analyze_conversation(session_id)
            write_cost_eval(session_id, conv_svc)
            evaluated += 1
        except Exception as e:
            print(f"[eval_runner] Failed to evaluate {session_id}: {e}")

    return {
        "sessions_marked_complete": marked,
        "sessions_evaluated": evaluated,
    }


def handler(event, context):
    return run_eval_cycle()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/lambdas/test_eval_runner.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/lambdas/eval_runner.py tests/lambdas/test_eval_runner.py
git commit -m "feat: implement eval_runner cron orchestrator with cost evaluation"
```

---

## Task 4: golden_dataset_runner

**Files:**
- Create: `src/lambdas/golden_dataset_runner.py`
- Create: `tests/lambdas/test_golden_dataset_runner.py`

- [ ] **Step 1: Write failing tests**

Create `tests/lambdas/test_golden_dataset_runner.py`:

```python
import pytest
import json
from unittest.mock import patch, MagicMock


GOLDEN_JSON = [
    {"id": "q1", "question": "What is pricing?", "expected_answer": "It's $49/mo."},
    {"id": "q2", "question": "What are the features?", "expected_answer": "Features include X and Y."},
]


@patch("src.lambdas.golden_dataset_runner.run_llm_judge")
@patch("src.lambdas.golden_dataset_runner.graph")
@patch("src.lambdas.golden_dataset_runner.settings")
def test_runner_scores_each_question(mock_settings, mock_graph, mock_judge):
    mock_settings.S3_BUCKET_NAME = "test-bucket"
    mock_settings.AWS_REGION = "us-east-1"
    mock_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_settings.GOLDEN_PASS_THRESHOLD = 0.7

    mock_graph.invoke.return_value = {"message": "It's $49/mo.", "retrieved_docs": []}
    mock_judge.return_value = {"faithfulness": 0.92, "relevance": 0.88, "reason": "good"}

    mock_dynamo = MagicMock()
    with patch("src.lambdas.golden_dataset_runner.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(GOLDEN_JSON).encode())
        }
        mock_boto3.resource.return_value.Table.return_value = mock_dynamo

        from src.lambdas.golden_dataset_runner import run_golden_dataset
        result = run_golden_dataset()

    assert result["total"] == 2
    assert result["passed"] == 2
    assert mock_dynamo.put_item.call_count == 2


@patch("src.lambdas.golden_dataset_runner.run_llm_judge")
@patch("src.lambdas.golden_dataset_runner.graph")
@patch("src.lambdas.golden_dataset_runner.settings")
def test_runner_marks_low_score_as_fail(mock_settings, mock_graph, mock_judge):
    mock_settings.S3_BUCKET_NAME = "test-bucket"
    mock_settings.AWS_REGION = "us-east-1"
    mock_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_settings.GOLDEN_PASS_THRESHOLD = 0.7

    mock_graph.invoke.return_value = {"message": "I don't know.", "retrieved_docs": []}
    mock_judge.return_value = {"faithfulness": 0.3, "relevance": 0.2, "reason": "poor"}

    mock_dynamo = MagicMock()
    with patch("src.lambdas.golden_dataset_runner.boto3") as mock_boto3:
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps([GOLDEN_JSON[0]]).encode())
        }
        mock_boto3.resource.return_value.Table.return_value = mock_dynamo

        from src.lambdas.golden_dataset_runner import run_golden_dataset
        result = run_golden_dataset()

    assert result["passed"] == 0
    call_item = mock_dynamo.put_item.call_args[1]["Item"]
    assert call_item["pass"] is False
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/lambdas/test_golden_dataset_runner.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Implement `src/lambdas/golden_dataset_runner.py`**

```python
import boto3
import json
import uuid
from datetime import datetime, timezone
from src.setting.config import settings
from src.graph.builder import graph
from src.lambdas.rag_evaluator import run_llm_judge

GOLDEN_S3_KEY = "golden.json"


def load_golden_dataset() -> list[dict]:
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    response = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=GOLDEN_S3_KEY)
    return json.loads(response["Body"].read())


def run_golden_dataset() -> dict:
    dataset = load_golden_dataset()
    dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    table = dynamodb.Table(settings.GOLDEN_RESULTS_TABLE)
    run_id = f"{uuid.uuid4()}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    run_at = datetime.now(timezone.utc).isoformat()

    passed = 0
    for entry in dataset:
        question_id = entry["id"]
        question = entry["question"]
        expected_answer = entry["expected_answer"]
        session_id = f"golden-{run_id}-{question_id}"

        result = graph.invoke({
            "name": "llmops",
            "user_query": question,
            "session_id": session_id,
            "turn": 1,
            "messages": [],
            "message": "",
        })

        actual_answer = result.get("message", "")
        retrieved_docs = result.get("retrieved_docs", [])

        judge = run_llm_judge(
            question=question,
            retrieved_docs=retrieved_docs,
            answer=actual_answer,
        )

        faithfulness = float(judge.get("faithfulness", 0))
        relevance = float(judge.get("relevance", 0))
        llm_judge_score = (faithfulness + relevance) / 2
        did_pass = llm_judge_score >= settings.GOLDEN_PASS_THRESHOLD

        if did_pass:
            passed += 1

        table.put_item(Item={
            "run_id": run_id,
            "question_id": question_id,
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": actual_answer,
            "faithfulness": str(round(faithfulness, 4)),
            "relevance": str(round(relevance, 4)),
            "llm_judge_score": str(round(llm_judge_score, 4)),
            "pass": did_pass,
            "run_at": run_at,
        })

    return {
        "run_id": run_id,
        "total": len(dataset),
        "passed": passed,
        "pass_rate": round(passed / len(dataset) * 100, 1) if dataset else 0.0,
    }


def handler(event, context):
    return run_golden_dataset()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/lambdas/test_golden_dataset_runner.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/lambdas/golden_dataset_runner.py tests/lambdas/test_golden_dataset_runner.py
git commit -m "feat: implement golden_dataset_runner Lambda"
```

---

## Task 5: Terraform Lambda + EventBridge definitions

**Files:**
- Modify: `iac/terraform-aws/lambda.tf`
- Modify: `iac/terraform-aws/cloudwatch.tf`

- [ ] **Step 1: Read current `iac/terraform-aws/lambda.tf`** to see existing content.

- [ ] **Step 2: Append eval Lambda definitions to `lambda.tf`**

```hcl
resource "aws_lambda_function" "eval_runner" {
  function_name = "eval_runner"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "eval_runner.handler"
  runtime       = "python3.13"
  timeout       = 300
  memory_size   = 512

  filename         = "dist/lambdas.zip"
  source_code_hash = filebase64sha256("dist/lambdas.zip")

  environment {
    variables = {
      CONVERSATIONS_TABLE  = var.conversations_table
      EVALUATIONS_TABLE    = var.evaluations_table
      HITL_TABLE           = var.hitl_table
      INACTIVITY_MINUTES   = tostring(var.inactivity_minutes)
      RAG_THRESHOLD        = tostring(var.rag_threshold)
      HITL_THRESHOLD       = tostring(var.hitl_threshold)
      AWS_REGION           = var.aws_region
    }
  }
}

resource "aws_lambda_function" "golden_dataset_runner" {
  function_name = "golden_dataset_runner"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "golden_dataset_runner.handler"
  runtime       = "python3.13"
  timeout       = 600
  memory_size   = 1024

  filename         = "dist/lambdas.zip"
  source_code_hash = filebase64sha256("dist/lambdas.zip")

  environment {
    variables = {
      GOLDEN_RESULTS_TABLE    = var.golden_results_table
      GOLDEN_PASS_THRESHOLD   = tostring(var.golden_pass_threshold)
      S3_BUCKET_NAME          = var.s3_bucket_name
      AWS_REGION              = var.aws_region
    }
  }
}
```

- [ ] **Step 3: Write `iac/terraform-aws/cloudwatch.tf`**

```hcl
resource "aws_cloudwatch_event_rule" "eval_runner_schedule" {
  name                = "eval-runner-schedule"
  description         = "Triggers eval_runner Lambda on a configurable schedule"
  schedule_expression = var.eval_cron_schedule
}

resource "aws_cloudwatch_event_target" "eval_runner_target" {
  rule      = aws_cloudwatch_event_rule.eval_runner_schedule.name
  target_id = "eval_runner"
  arn       = aws_lambda_function.eval_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_eval" {
  statement_id  = "AllowEventBridgeEvalRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.eval_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.eval_runner_schedule.arn
}

resource "aws_cloudwatch_event_rule" "golden_runner_schedule" {
  name                = "golden-runner-schedule"
  description         = "Triggers golden_dataset_runner Lambda on a configurable schedule"
  schedule_expression = var.golden_cron_schedule
}

resource "aws_cloudwatch_event_target" "golden_runner_target" {
  rule      = aws_cloudwatch_event_rule.golden_runner_schedule.name
  target_id = "golden_dataset_runner"
  arn       = aws_lambda_function.golden_dataset_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_golden" {
  statement_id  = "AllowEventBridgeGoldenRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.golden_dataset_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.golden_runner_schedule.arn
}
```

- [ ] **Step 4: Validate Terraform**

```bash
cd iac/terraform-aws && terraform validate
cd ../..
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 5: Commit**

```bash
git add iac/terraform-aws/lambda.tf iac/terraform-aws/cloudwatch.tf
git commit -m "feat: add eval Lambda and EventBridge cron definitions to Terraform"
```

---

## Task 6: Full test suite

- [ ] **Step 1: Run all lambda tests**

```bash
uv run pytest tests/lambdas/ -v
```

Expected: `10 passed` (4 rag_evaluator + 3 pca + 3 eval_runner + 2 golden_dataset_runner + 2 previously written = all green, adjust count based on final test count)

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: eval pipeline complete - rag_evaluator, pca, eval_runner, golden_dataset_runner"
```
