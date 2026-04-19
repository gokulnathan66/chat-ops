# Backend Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conversation persistence (DynamoDB), a ConversationService, graph node instrumentation, and dashboard REST API to the existing FastAPI + LangGraph backend.

**Architecture:** Every chat turn is written to DynamoDB via ConversationService immediately after the LangGraph node executes. A new `dashboard.py` router exposes read endpoints for both dashboards and write endpoints for HITL resolution and ingestion triggering. Terraform defines all 4 DynamoDB tables.

**Tech Stack:** Python 3.13, FastAPI, boto3, DynamoDB, moto[dynamodb] (tests), uv, Terraform

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/services/conversation.py` | All DynamoDB reads/writes for conversations, evaluations, HITL, golden |
| Create | `src/api/dashboard.py` | REST endpoints for both dashboards |
| Create | `tests/__init__.py` | Test package root |
| Create | `tests/services/__init__.py` | |
| Create | `tests/services/test_conversation.py` | ConversationService unit tests |
| Create | `tests/api/__init__.py` | |
| Create | `tests/api/test_dashboard.py` | Dashboard endpoint integration tests |
| Modify | `src/setting/config.py` | Add DynamoDB table name settings |
| Modify | `src/states/config.py` | Add session_id, turn, retrieved_docs, token_usage, latency_ms |
| Modify | `src/schema/config.py` | Add optional session_id to GraphInvokeRequest |
| Modify | `src/api/routes.py` | Thread session_id through graph invocation |
| Modify | `src/nodes/general.py` | Write turn to DynamoDB after execution |
| Modify | `src/nodes/tools.py` | Write turn to DynamoDB after execution |
| Modify | `src/main.py` | Include dashboard router |
| Modify | `iac/terraform-aws/dynamodb.tf` | Define 4 tables with GSIs |
| Modify | `iac/terraform-aws/variables.tf` | Add threshold and table name vars |

---

## Task 1: Test infrastructure + DynamoDB settings

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/services/__init__.py`
- Create: `tests/api/__init__.py`
- Modify: `src/setting/config.py`

- [ ] **Step 1: Add dev dependencies**

```bash
uv add --dev pytest pytest-asyncio moto[dynamodb]
```

Expected output: `Resolved N packages` with `pytest`, `moto` in the list.

- [ ] **Step 2: Create test package files**

Create `tests/__init__.py`, `tests/services/__init__.py`, `tests/api/__init__.py` — all empty files.

```bash
mkdir -p tests/services tests/api
touch tests/__init__.py tests/services/__init__.py tests/api/__init__.py
```

- [ ] **Step 3: Add DynamoDB table settings to `src/setting/config.py`**

Current file ends around line 47. Add these fields to the `Settings` class:

```python
# DynamoDB table names
CONVERSATIONS_TABLE: str = "conversations"
EVALUATIONS_TABLE: str = "evaluations"
HITL_TABLE: str = "hitl_queue"
GOLDEN_RESULTS_TABLE: str = "golden_results"

# Evaluation thresholds
INACTIVITY_MINUTES: int = 15
RAG_THRESHOLD: float = 0.6
HITL_THRESHOLD: float = 0.6
GOLDEN_PASS_THRESHOLD: float = 0.7
RAG_RERANK_TOP_K_MULTIPLIER: int = 2
```

- [ ] **Step 4: Verify settings load**

```bash
uv run python -c "from src.setting.config import settings; print(settings.CONVERSATIONS_TABLE)"
```

Expected: `conversations`

- [ ] **Step 5: Commit**

```bash
git add tests/ src/setting/config.py
git commit -m "feat: add test infrastructure and DynamoDB table settings"
```

---

## Task 2: ConversationService — write_turn + mark_complete

**Files:**
- Create: `src/services/conversation.py`
- Create: `tests/services/test_conversation.py`

- [ ] **Step 1: Write failing tests for write_turn and mark_complete**

Create `tests/services/test_conversation.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/services/test_conversation.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `conversation` doesn't exist yet.

- [ ] **Step 3: Implement write_turn and mark_complete**

Create `src/services/conversation.py`:

```python
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timezone
from src.setting.config import settings


class ConversationService:
    def __init__(self):
        self._dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
        self._table = self._dynamodb.Table(settings.CONVERSATIONS_TABLE)

    def write_turn(self, session_id: str, turn_n: int, data: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._table.put_item(Item={
            "session_id": session_id,
            "sk": f"turn#{turn_n:03d}",
            "user_query": data.get("user_query", ""),
            "ai_response": data.get("ai_response", ""),
            "intent": data.get("intent", ""),
            "route": data.get("route", ""),
            "retrieved_docs": data.get("retrieved_docs", []),
            "token_usage": data.get("token_usage", {}),
            "latency_ms": data.get("latency_ms", 0),
            "created_at": now,
        })
        self._table.update_item(
            Key={"session_id": session_id, "sk": "metadata"},
            UpdateExpression=(
                "SET #s = :active, last_updated_at = :now, "
                "turn_count = if_not_exists(turn_count, :zero) + :one, "
                "created_at = if_not_exists(created_at, :now)"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":active": "active",
                ":now": now,
                ":zero": 0,
                ":one": 1,
            },
        )

    def mark_complete(self, session_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._table.update_item(
            Key={"session_id": session_id, "sk": "metadata"},
            UpdateExpression="SET #s = :complete, last_updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":complete": "complete", ":now": now},
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/services/test_conversation.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add src/services/conversation.py tests/services/test_conversation.py
git commit -m "feat: add ConversationService write_turn and mark_complete"
```

---

## Task 3: ConversationService — get_conversation + list_conversations

**Files:**
- Modify: `src/services/conversation.py`
- Modify: `tests/services/test_conversation.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/services/test_conversation.py`:

```python
@mock_aws
@patch("src.services.conversation.settings")
def test_get_conversation_returns_metadata_and_turns(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_table(dynamodb)

    svc = ConversationService()
    svc.write_turn("sess-2", 1, {"user_query": "q1", "ai_response": "a1"})
    svc.write_turn("sess-2", 2, {"user_query": "q2", "ai_response": "a2"})

    result = svc.get_conversation("sess-2")
    assert result["metadata"]["status"] == "active"
    assert result["metadata"]["turn_count"] == 2
    assert len(result["turns"]) == 2
    assert result["turns"][0]["user_query"] == "q1"
    assert result["turns"][1]["user_query"] == "q2"


@mock_aws
@patch("src.services.conversation.settings")
def test_list_conversations_by_status(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_table(dynamodb)

    svc = ConversationService()
    svc.write_turn("sess-3", 1, {"user_query": "q", "ai_response": "a"})
    svc.mark_complete("sess-3")

    results = svc.list_conversations("complete")
    assert len(results) == 1
    assert results[0]["session_id"] == "sess-3"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/services/test_conversation.py::test_get_conversation_returns_metadata_and_turns tests/services/test_conversation.py::test_list_conversations_by_status -v
```

Expected: `AttributeError` — methods not implemented yet.

- [ ] **Step 3: Implement get_conversation + list_conversations**

Add to the `ConversationService` class in `src/services/conversation.py`:

```python
    def get_conversation(self, session_id: str) -> dict:
        response = self._table.query(
            KeyConditionExpression=Key("session_id").eq(session_id)
        )
        items = response.get("Items", [])
        metadata = next((i for i in items if i["sk"] == "metadata"), {})
        turns = sorted(
            [i for i in items if i["sk"].startswith("turn#")],
            key=lambda x: x["sk"],
        )
        return {"metadata": metadata, "turns": turns}

    def list_conversations(self, status: str, limit: int = 50) -> list[dict]:
        response = self._table.query(
            IndexName="status-last_updated_at-index",
            KeyConditionExpression=Key("status").eq(status),
            Limit=limit,
            ScanIndexForward=False,
        )
        return response.get("Items", [])
```

- [ ] **Step 4: Run all conversation tests**

```bash
uv run pytest tests/services/test_conversation.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add src/services/conversation.py tests/services/test_conversation.py
git commit -m "feat: add ConversationService get_conversation and list_conversations"
```

---

## Task 4: ConversationService — write_hitl + resolve_hitl

**Files:**
- Modify: `src/services/conversation.py`
- Modify: `tests/services/test_conversation.py`

**Note on HITL table design:** The `hitl_queue` table uses `pk="HITL"` (literal singleton) as the partition key and `sk=<created_at>#<session_id>` as the sort key. Status transitions are simple attribute updates via a GSI (`queue_status-sk-index`). This avoids the delete-and-reinsert pattern required by the original spec's PK-as-status design.

- [ ] **Step 1: Add failing tests**

Append to `tests/services/test_conversation.py`:

```python
HITL_TABLE_NAME = "hitl_queue"

def _create_hitl_table(dynamodb):
    dynamodb.create_table(
        TableName=HITL_TABLE_NAME,
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
    return dynamodb.Table(HITL_TABLE_NAME)


@mock_aws
@patch("src.services.conversation.settings")
def test_write_hitl_creates_pending_item(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.HITL_TABLE = HITL_TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_table(dynamodb)
    _create_hitl_table(dynamodb)

    svc = ConversationService()
    svc.write_turn("sess-4", 1, {"user_query": "bad q", "ai_response": "bad a"})
    svc.write_hitl("sess-4", "rag_eval", {"rag_score": 0.3, "llm_judge_score": 0.4})

    hitl_table = dynamodb.Table(HITL_TABLE_NAME)
    response = hitl_table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq("pending"),
    )
    items = response["Items"]
    assert len(items) == 1
    assert items[0]["session_id"] == "sess-4"
    assert items[0]["trigger"] == "rag_eval"
    assert float(items[0]["rag_score"]) == pytest.approx(0.3)


@mock_aws
@patch("src.services.conversation.settings")
def test_resolve_hitl_updates_status(mock_settings):
    mock_settings.CONVERSATIONS_TABLE = TABLE_NAME
    mock_settings.HITL_TABLE = HITL_TABLE_NAME
    mock_settings.AWS_REGION = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_table(dynamodb)
    hitl_table = _create_hitl_table(dynamodb)

    svc = ConversationService()
    svc.write_turn("sess-5", 1, {"user_query": "q", "ai_response": "a"})
    svc.write_hitl("sess-5", "llm_judge", {"rag_score": 0.2, "llm_judge_score": 0.3})

    response = hitl_table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq("pending"),
    )
    queue_id = response["Items"][0]["sk"]

    svc.resolve_hitl(queue_id, "Human answered: pricing is $49.")

    item = hitl_table.get_item(Key={"pk": "HITL", "sk": queue_id})["Item"]
    assert item["queue_status"] == "resolved"
    assert item["human_response"] == "Human answered: pricing is $49."
    assert item["resolved_at"] is not None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/services/test_conversation.py::test_write_hitl_creates_pending_item tests/services/test_conversation.py::test_resolve_hitl_updates_status -v
```

Expected: `AttributeError` — methods not implemented.

- [ ] **Step 3: Implement write_hitl + resolve_hitl**

Add to `ConversationService` in `src/services/conversation.py`:

```python
    def write_hitl(self, session_id: str, trigger: str, scores: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        hitl_table = self._dynamodb.Table(settings.HITL_TABLE)
        conv = self.get_conversation(session_id)
        last_5 = conv["turns"][-5:]
        summary = " | ".join(
            f"Q: {t.get('user_query','')} A: {t.get('ai_response','')}" for t in last_5
        )
        hitl_table.put_item(Item={
            "pk": "HITL",
            "sk": f"{now}#{session_id}",
            "session_id": session_id,
            "queue_status": "pending",
            "trigger": trigger,
            "conversation_summary": summary,
            "rag_score": str(scores.get("rag_score", "")),
            "llm_judge_score": str(scores.get("llm_judge_score", "")),
            "assigned_to": None,
            "human_response": None,
            "resolved_at": None,
            "created_at": now,
        })

    def resolve_hitl(self, queue_id: str, human_response: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        hitl_table = self._dynamodb.Table(settings.HITL_TABLE)
        hitl_table.update_item(
            Key={"pk": "HITL", "sk": queue_id},
            UpdateExpression="SET queue_status = :resolved, human_response = :resp, resolved_at = :now",
            ExpressionAttributeValues={
                ":resolved": "resolved",
                ":resp": human_response,
                ":now": now,
            },
        )
```

- [ ] **Step 4: Run all conversation tests**

```bash
uv run pytest tests/services/test_conversation.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add src/services/conversation.py tests/services/test_conversation.py
git commit -m "feat: add ConversationService write_hitl and resolve_hitl"
```

---

## Task 5: Thread session_id through GraphState, schema, and routes

**Files:**
- Modify: `src/states/config.py`
- Modify: `src/schema/config.py`
- Modify: `src/api/routes.py`

- [ ] **Step 1: Update `src/states/config.py`**

Current content defines `GraphState`. Replace with:

```python
from typing import TypedDict, NotRequired


class GraphState(TypedDict):
    name: str
    user_query: str
    session_id: str
    turn: int
    intent: NotRequired[str]
    route: NotRequired[str]
    confidence: NotRequired[float]
    message: NotRequired[str]
    retrieved_docs: NotRequired[list[dict]]
    token_usage: NotRequired[dict]
    latency_ms: NotRequired[float]
```

- [ ] **Step 2: Update `src/schema/config.py`**

Add `session_id` as optional to `GraphInvokeRequest`. Find the class definition and add the field:

```python
import uuid
from pydantic import BaseModel, Field
from typing import Any, Optional


class SemanticSearchInput(BaseModel):
    query: str
    top_k: int = 5
    tags: Optional[list[str]] = None


class IntentRoute(BaseModel):
    intent: str
    route: str
    confidence: float
    reason: str


class GraphInvokeRequest(BaseModel):
    user_query: str
    messages: list[dict] = []
    message: str = ""
    session_id: Optional[str] = None
    turn: int = 1


class GraphInvokeResponse(BaseModel):
    result: dict[str, Any]
```

- [ ] **Step 3: Update `src/api/routes.py`**

```python
import uuid
from fastapi import APIRouter
from src.schema.config import GraphInvokeRequest, GraphInvokeResponse
from src.graph.builder import graph

router = APIRouter()


@router.post("/api/chat", response_model=GraphInvokeResponse)
async def chat(request: GraphInvokeRequest) -> GraphInvokeResponse:
    session_id = request.session_id or str(uuid.uuid4())
    result = graph.invoke({
        "name": "llmops",
        "user_query": request.user_query,
        "session_id": session_id,
        "turn": request.turn,
        "messages": request.messages,
        "message": request.message,
    })
    return GraphInvokeResponse(result=result)
```

- [ ] **Step 4: Smoke test the API starts without errors**

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/health
kill %1
```

Expected: `{"status":"ok"}` or similar health response.

- [ ] **Step 5: Commit**

```bash
git add src/states/config.py src/schema/config.py src/api/routes.py
git commit -m "feat: thread session_id and turn through GraphState and routes"
```

---

## Task 6: Instrument general.py to write turns

**Files:**
- Modify: `src/nodes/general.py`

- [ ] **Step 1: Read current `src/nodes/general.py`** to understand the existing structure before editing.

- [ ] **Step 2: Update `src/nodes/general.py`**

```python
import time
from langgraph.types import Command
from src.services.bedrock import BedrockService
from src.services.conversation import ConversationService
from src.states.config import GraphState

bedrock = BedrockService()
conversation_svc = ConversationService()

SYSTEM_PROMPT = (
    "You are a helpful general assistant. Answer the user's question directly. "
    "Do not invent information about indexed documents — only use what you know."
)


def general_node(state: GraphState) -> Command:
    start = time.time()
    response = bedrock.converse_text(
        messages=[{"role": "user", "content": state["user_query"]}],
        system_prompt=SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=1024,
    )
    latency_ms = (time.time() - start) * 1000

    token_usage = response.get("usage", {})

    conversation_svc.write_turn(
        session_id=state["session_id"],
        turn_n=state["turn"],
        data={
            "user_query": state["user_query"],
            "ai_response": response.get("text", ""),
            "intent": state.get("intent", "general"),
            "route": "general",
            "retrieved_docs": [],
            "token_usage": {
                "input": token_usage.get("inputTokens", 0),
                "output": token_usage.get("outputTokens", 0),
            },
            "latency_ms": latency_ms,
        },
    )

    return Command(
        update={"message": response.get("text", "")},
        goto="__end__",
    )
```

- [ ] **Step 3: Verify the app still starts**

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/health
kill %1
```

Expected: health endpoint responds without errors.

- [ ] **Step 4: Commit**

```bash
git add src/nodes/general.py
git commit -m "feat: instrument general_node to write turns to DynamoDB"
```

---

## Task 7: Instrument tools.py to write turns

**Files:**
- Modify: `src/nodes/tools.py`

- [ ] **Step 1: Read current `src/nodes/tools.py`** to understand current structure.

- [ ] **Step 2: Update `src/nodes/tools.py`**

```python
import time
from langgraph.types import Command
from src.services.bedrock import BedrockService
from src.services.conversation import ConversationService
from src.states.config import GraphState
from src.tools.rag import semantic_document_search

bedrock = BedrockService()
conversation_svc = ConversationService()

SYSTEM_PROMPT = "You are a helpful assistant. Use tools when needed to answer questions about indexed documents."


def tools_node(state: GraphState) -> Command:
    start = time.time()
    response = bedrock.invoke_agent(
        messages=[{"role": "user", "content": state["user_query"]}],
        tools=[semantic_document_search],
        system_prompt=SYSTEM_PROMPT,
    )
    latency_ms = (time.time() - start) * 1000

    text = bedrock.extract_text(response)
    retrieved_docs = _extract_retrieved_docs(response)
    token_usage = _extract_token_usage(response)

    conversation_svc.write_turn(
        session_id=state["session_id"],
        turn_n=state["turn"],
        data={
            "user_query": state["user_query"],
            "ai_response": text,
            "intent": state.get("intent", "tools"),
            "route": "tools",
            "retrieved_docs": retrieved_docs,
            "token_usage": token_usage,
            "latency_ms": latency_ms,
        },
    )

    return Command(
        update={
            "message": text,
            "retrieved_docs": retrieved_docs,
            "token_usage": token_usage,
            "latency_ms": latency_ms,
        },
        goto="__end__",
    )


def _extract_retrieved_docs(response) -> list[dict]:
    docs = []
    for msg in getattr(response, "messages", []):
        content = getattr(msg, "content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    for item in block.get("content", []):
                        if isinstance(item, dict) and item.get("type") == "text":
                            docs.append({"text_snippet": item["text"][:200]})
    return docs


def _extract_token_usage(response) -> dict:
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return {
            "input": getattr(usage, "input_tokens", 0),
            "output": getattr(usage, "output_tokens", 0),
        }
    return {"input": 0, "output": 0}
```

- [ ] **Step 3: Verify app starts**

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/health
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add src/nodes/tools.py
git commit -m "feat: instrument tools_node to write turns with retrieved_docs to DynamoDB"
```

---

## Task 8: Dashboard API — conversations + evaluations + metrics

**Files:**
- Create: `src/api/dashboard.py`
- Create: `tests/api/test_dashboard.py`
- Modify: `src/main.py`

- [ ] **Step 1: Write failing tests for GET endpoints**

Create `tests/api/test_dashboard.py`:

```python
import boto3
import pytest
from moto import mock_aws
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _setup_conversations_table(dynamodb):
    table = dynamodb.create_table(
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
    return table


def _setup_evaluations_table(dynamodb):
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


@mock_aws
@patch("src.services.conversation.settings")
@patch("src.api.dashboard.settings")
def test_get_conversations_returns_list(mock_dash_settings, mock_conv_settings):
    mock_conv_settings.CONVERSATIONS_TABLE = "conversations"
    mock_conv_settings.HITL_TABLE = "hitl_queue"
    mock_conv_settings.AWS_REGION = "us-east-1"
    mock_dash_settings.CONVERSATIONS_TABLE = "conversations"
    mock_dash_settings.EVALUATIONS_TABLE = "evaluations"
    mock_dash_settings.HITL_TABLE = "hitl_queue"
    mock_dash_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_dash_settings.AWS_REGION = "us-east-1"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    conv_table = _setup_conversations_table(dynamodb)
    _setup_evaluations_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("sess-api-1", 1, {"user_query": "q", "ai_response": "a"})

    from src.main import app
    client = TestClient(app)
    resp = client.get("/api/conversations?status=active")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(c["session_id"] == "sess-api-1" for c in data)


@mock_aws
@patch("src.services.conversation.settings")
@patch("src.api.dashboard.settings")
def test_get_conversation_detail(mock_dash_settings, mock_conv_settings):
    mock_conv_settings.CONVERSATIONS_TABLE = "conversations"
    mock_conv_settings.HITL_TABLE = "hitl_queue"
    mock_conv_settings.AWS_REGION = "us-east-1"
    mock_dash_settings.CONVERSATIONS_TABLE = "conversations"
    mock_dash_settings.EVALUATIONS_TABLE = "evaluations"
    mock_dash_settings.HITL_TABLE = "hitl_queue"
    mock_dash_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_dash_settings.AWS_REGION = "us-east-1"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _setup_conversations_table(dynamodb)
    _setup_evaluations_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("sess-api-2", 1, {"user_query": "what?", "ai_response": "this."})

    from src.main import app
    client = TestClient(app)
    resp = client.get("/api/conversations/sess-api-2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["turns"]) == 1
    assert data["turns"][0]["user_query"] == "what?"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/api/test_dashboard.py -v
```

Expected: `ImportError` or 404 — dashboard router doesn't exist yet.

- [ ] **Step 3: Create `src/api/dashboard.py`**

```python
import boto3
from boto3.dynamodb.conditions import Key
from fastapi import APIRouter, HTTPException
from src.setting.config import settings
from src.services.conversation import ConversationService

router = APIRouter()
_conversation_svc = ConversationService()


def _dynamodb():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION)


@router.get("/api/conversations")
async def list_conversations(status: str = "active", limit: int = 50):
    return _conversation_svc.list_conversations(status=status, limit=limit)


@router.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    result = _conversation_svc.get_conversation(session_id)
    if not result["metadata"]:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get("/api/evaluations")
async def list_evaluations(eval_type: str = "rag", limit: int = 50):
    table = _dynamodb().Table(settings.EVALUATIONS_TABLE)
    response = table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq(eval_type),
        Limit=limit,
        ScanIndexForward=False,
    )
    return response.get("Items", [])


@router.get("/api/metrics/summary")
async def metrics_summary():
    eval_table = _dynamodb().Table(settings.EVALUATIONS_TABLE)
    hitl_table = _dynamodb().Table(settings.HITL_TABLE)
    golden_table = _dynamodb().Table(settings.GOLDEN_RESULTS_TABLE)

    rag_evals = eval_table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("rag"),
        Limit=100,
        ScanIndexForward=False,
    ).get("Items", [])

    avg_rag = (
        sum(float(e.get("rag_score", 0)) for e in rag_evals) / len(rag_evals)
        if rag_evals else 0.0
    )
    avg_faithfulness = (
        sum(float(e.get("faithfulness", 0)) for e in rag_evals) / len(rag_evals)
        if rag_evals else 0.0
    )

    cost_evals = eval_table.query(
        IndexName="eval_type-created_at-index",
        KeyConditionExpression=Key("eval_type").eq("cost"),
        Limit=100,
        ScanIndexForward=False,
    ).get("Items", [])
    cost_today = sum(float(e.get("cost_usd", 0)) for e in cost_evals)

    hitl_pending = hitl_table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq("pending"),
    ).get("Count", 0)

    golden_items = golden_table.scan(
        FilterExpression=Key("pass").eq(True),
    )
    golden_pass = golden_items.get("Count", 0)
    golden_total = golden_table.scan().get("Count", 0)
    golden_pass_rate = (golden_pass / golden_total * 100) if golden_total else 0.0

    return {
        "avg_rag_score": round(avg_rag, 3),
        "avg_faithfulness": round(avg_faithfulness, 3),
        "cost_today_usd": round(cost_today, 4),
        "hitl_pending": hitl_pending,
        "golden_pass_rate_pct": round(golden_pass_rate, 1),
    }
```

- [ ] **Step 4: Register dashboard router in `src/main.py`**

Add the import and include at the bottom of `src/main.py`:

```python
from fastapi import FastAPI
from src.api.routes import router as chat_router
from src.api.dashboard import router as dashboard_router

app = FastAPI(title="llmops", version="1.0.0")
app.include_router(chat_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run dashboard tests**

```bash
uv run pytest tests/api/test_dashboard.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add src/api/dashboard.py src/main.py tests/api/test_dashboard.py
git commit -m "feat: add dashboard REST API - conversations, evaluations, metrics endpoints"
```

---

## Task 9: Dashboard API — HITL + golden + ingestion endpoints

**Files:**
- Modify: `src/api/dashboard.py`
- Modify: `tests/api/test_dashboard.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/api/test_dashboard.py`:

```python
def _setup_hitl_table(dynamodb):
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


@mock_aws
@patch("src.services.conversation.settings")
@patch("src.api.dashboard.settings")
def test_get_hitl_queue(mock_dash_settings, mock_conv_settings):
    mock_conv_settings.CONVERSATIONS_TABLE = "conversations"
    mock_conv_settings.HITL_TABLE = "hitl_queue"
    mock_conv_settings.AWS_REGION = "us-east-1"
    mock_dash_settings.CONVERSATIONS_TABLE = "conversations"
    mock_dash_settings.EVALUATIONS_TABLE = "evaluations"
    mock_dash_settings.HITL_TABLE = "hitl_queue"
    mock_dash_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_dash_settings.AWS_REGION = "us-east-1"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _setup_conversations_table(dynamodb)
    _setup_evaluations_table(dynamodb)
    _setup_hitl_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("sess-hitl-1", 1, {"user_query": "bad", "ai_response": "wrong"})
    svc.write_hitl("sess-hitl-1", "rag_eval", {"rag_score": 0.2, "llm_judge_score": 0.3})

    from src.main import app
    client = TestClient(app)
    resp = client.get("/api/hitl?status=pending")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert items[0]["session_id"] == "sess-hitl-1"


@mock_aws
@patch("src.services.conversation.settings")
@patch("src.api.dashboard.settings")
def test_post_hitl_respond(mock_dash_settings, mock_conv_settings):
    mock_conv_settings.CONVERSATIONS_TABLE = "conversations"
    mock_conv_settings.HITL_TABLE = "hitl_queue"
    mock_conv_settings.AWS_REGION = "us-east-1"
    mock_dash_settings.CONVERSATIONS_TABLE = "conversations"
    mock_dash_settings.EVALUATIONS_TABLE = "evaluations"
    mock_dash_settings.HITL_TABLE = "hitl_queue"
    mock_dash_settings.GOLDEN_RESULTS_TABLE = "golden_results"
    mock_dash_settings.AWS_REGION = "us-east-1"

    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _setup_conversations_table(dynamodb)
    _setup_evaluations_table(dynamodb)
    hitl_table = _setup_hitl_table(dynamodb)

    from src.services.conversation import ConversationService
    svc = ConversationService()
    svc.write_turn("sess-hitl-2", 1, {"user_query": "q", "ai_response": "a"})
    svc.write_hitl("sess-hitl-2", "rag_eval", {"rag_score": 0.1})

    response = hitl_table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq("pending"),
    )
    queue_id = response["Items"][0]["sk"]

    from src.main import app
    client = TestClient(app)
    resp = client.post(f"/api/hitl/{queue_id}/respond", json={"human_response": "The answer is X."})
    assert resp.status_code == 200

    item = hitl_table.get_item(Key={"pk": "HITL", "sk": queue_id})["Item"]
    assert item["queue_status"] == "resolved"
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/api/test_dashboard.py::test_get_hitl_queue tests/api/test_dashboard.py::test_post_hitl_respond -v
```

Expected: 404 — endpoints don't exist yet.

- [ ] **Step 3: Add HITL, golden, and ingestion endpoints to `src/api/dashboard.py`**

Append to `src/api/dashboard.py`:

```python
from pydantic import BaseModel
import boto3


class HitlRespondRequest(BaseModel):
    human_response: str


@router.get("/api/hitl")
async def list_hitl(status: str = "pending", limit: int = 50):
    table = _dynamodb().Table(settings.HITL_TABLE)
    response = table.query(
        IndexName="queue_status-sk-index",
        KeyConditionExpression=Key("queue_status").eq(status),
        Limit=limit,
        ScanIndexForward=False,
    )
    return response.get("Items", [])


@router.post("/api/hitl/{queue_id}/respond")
async def respond_hitl(queue_id: str, body: HitlRespondRequest):
    _conversation_svc.resolve_hitl(queue_id, body.human_response)
    return {"status": "resolved"}


@router.get("/api/golden-results")
async def list_golden_results(run_id: str | None = None, limit: int = 100):
    table = _dynamodb().Table(settings.GOLDEN_RESULTS_TABLE)
    if run_id:
        response = table.query(
            KeyConditionExpression=Key("run_id").eq(run_id),
            Limit=limit,
        )
    else:
        response = table.scan(Limit=limit)
    return response.get("Items", [])


class HitlCreateRequest(BaseModel):
    session_id: str
    trigger: str = "user_escalation"
    rag_score: float = 0.0
    llm_judge_score: float = 0.0


@router.post("/api/hitl")
async def create_hitl(body: HitlCreateRequest):
    _conversation_svc.write_hitl(
        body.session_id, body.trigger,
        {"rag_score": body.rag_score, "llm_judge_score": body.llm_judge_score}
    )
    return {"status": "created"}


@router.post("/api/ingestion/start")
async def start_ingestion(body: dict):
    import boto3 as _boto3
    s3_key = body.get("s3_key")
    if not s3_key:
        raise HTTPException(status_code=422, detail="s3_key is required")
    lambda_client = _boto3.client("lambda", region_name=settings.AWS_REGION)
    import json
    lambda_client.invoke(
        FunctionName="qdrant_ingestion",
        InvocationType="Event",
        Payload=json.dumps({"s3_key": s3_key, "bucket": settings.S3_BUCKET_NAME}).encode(),
    )
    return {"status": "ingestion_started", "s3_key": s3_key}
```

- [ ] **Step 4: Run all dashboard tests**

```bash
uv run pytest tests/api/test_dashboard.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/api/dashboard.py tests/api/test_dashboard.py
git commit -m "feat: add HITL, golden results, and ingestion trigger endpoints"
```

---

## Task 10: Terraform DynamoDB tables

**Files:**
- Modify: `iac/terraform-aws/dynamodb.tf`
- Modify: `iac/terraform-aws/variables.tf`

- [ ] **Step 1: Read current `iac/terraform-aws/dynamodb.tf`** to see existing content.

- [ ] **Step 2: Write `iac/terraform-aws/dynamodb.tf`**

```hcl
resource "aws_dynamodb_table" "conversations" {
  name         = var.conversations_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "sk"

  attribute {
    name = "session_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "status"
    type = "S"
  }
  attribute {
    name = "last_updated_at"
    type = "S"
  }

  global_secondary_index {
    name            = "status-last_updated_at-index"
    hash_key        = "status"
    range_key       = "last_updated_at"
    projection_type = "ALL"
  }
}

resource "aws_dynamodb_table" "evaluations" {
  name         = var.evaluations_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "sk"

  attribute {
    name = "session_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "eval_type"
    type = "S"
  }
  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "eval_type-created_at-index"
    hash_key        = "eval_type"
    range_key       = "created_at"
    projection_type = "ALL"
  }
}

resource "aws_dynamodb_table" "hitl_queue" {
  name         = var.hitl_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "queue_status"
    type = "S"
  }

  global_secondary_index {
    name            = "queue_status-sk-index"
    hash_key        = "queue_status"
    range_key       = "sk"
    projection_type = "ALL"
  }
}

resource "aws_dynamodb_table" "golden_results" {
  name         = var.golden_results_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"
  range_key    = "question_id"

  attribute {
    name = "run_id"
    type = "S"
  }
  attribute {
    name = "question_id"
    type = "S"
  }
}
```

- [ ] **Step 3: Add variables to `iac/terraform-aws/variables.tf`**

Append to existing `variables.tf`:

```hcl
variable "conversations_table" {
  description = "DynamoDB table name for conversations"
  type        = string
  default     = "conversations"
}

variable "evaluations_table" {
  description = "DynamoDB table name for evaluations"
  type        = string
  default     = "evaluations"
}

variable "hitl_table" {
  description = "DynamoDB table name for HITL queue"
  type        = string
  default     = "hitl_queue"
}

variable "golden_results_table" {
  description = "DynamoDB table name for golden dataset results"
  type        = string
  default     = "golden_results"
}

variable "eval_cron_schedule" {
  description = "EventBridge cron schedule for evaluation Lambda"
  type        = string
  default     = "rate(15 minutes)"
}

variable "golden_cron_schedule" {
  description = "EventBridge cron schedule for golden dataset runner"
  type        = string
  default     = "rate(1 hour)"
}

variable "rag_threshold" {
  description = "RAG score below which re-retrieval is triggered"
  type        = number
  default     = 0.6
}

variable "hitl_threshold" {
  description = "Score below which HITL flagging is triggered after re-retrieval"
  type        = number
  default     = 0.6
}

variable "inactivity_minutes" {
  description = "Minutes of inactivity before a session is marked complete"
  type        = number
  default     = 15
}
```

- [ ] **Step 4: Validate Terraform**

```bash
cd iac/terraform-aws && terraform init && terraform validate
cd ../..
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 5: Commit**

```bash
git add iac/terraform-aws/dynamodb.tf iac/terraform-aws/variables.tf
git commit -m "feat: define DynamoDB tables and eval threshold variables in Terraform"
```

---

## Task 11: Run full test suite + final smoke test

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass (`7 conversation + 4 dashboard = 11 passed`)

- [ ] **Step 2: Start server and verify health + chat endpoint**

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/conversations?status=active
kill %1
```

Expected: health returns `{"status":"ok"}`, conversations returns `[]` (empty — no DynamoDB in local env).

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: backend core complete - ConversationService, instrumented nodes, dashboard API, Terraform tables"
```
