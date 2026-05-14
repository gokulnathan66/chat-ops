# 01 — Runtime: API, Graph, Nodes, Services

Covers what happens when a user sends a chat request, end to end.

## FastAPI tier

`src/main.py` mounts two routers, enables wide-open CORS, and exposes `/health`.

| Router | File | Purpose |
|--------|------|---------|
| `api_router` | `src/api/routes.py` | Chat endpoint + conversation reads |
| `dashboard_router` | `src/api/dashboard.py` | Control plane: HITL CRUD, ingestion upload/status, golden queries, evaluations, metrics |

### Key endpoints

| Method | Path | Behaviour |
|--------|------|-----------|
| `POST` | `/api/chat` | Invokes the LangGraph. If the session is `hitl_pending`, the user message is appended to the conversation **without** running the AI (a human is in control). |
| `GET` | `/api/conversations?status=...` | Lists sessions by status (`active`, `hitl_pending`, `approval_pending`, `complete`, or `all`) |
| `GET` | `/api/conversations/{session_id}` | Full session: metadata + ordered turns |
| `GET` | `/api/metrics/summary` | Avg RAG score, avg faithfulness, today's cost, HITL pending count |
| `GET/POST` | `/api/hitl`, `/api/hitl/{queue_id}/respond|resolve|approve` | HITL queue CRUD (see `04-hitl.md`) |
| `POST` | `/api/ingestion/upload` | Multipart PDF/TXT/CSV upload → S3 → triggers the async pipeline |
| `POST` | `/api/ingestion/start` | Re-ingest an S3 key by self-copying it (re-fires the S3 event) |
| `GET/DELETE` | `/api/ingestion/docs[/{doc_id}]` | List/delete documents in Qdrant |
| `GET` | `/api/ingestion/status/{job_id}` / `/api/ingestion/history` | Job tracking |
| `GET/POST/PUT/DELETE` | `/api/golden-queries[...]` | Golden test queries used by the eval runner |

### Chat request lifecycle

```
POST /api/chat {user_query, session_id?, turn, ...}
  │
  ├─ Generate session_id if missing (uuid4)
  │
  ├─ Read session metadata from DynamoDB
  │   └─ if status == "hitl_pending":
  │        write user turn (intent="hitl_user_reply") and return immediately
  │        — the AI does NOT run while a human owns the session
  │
  ├─ graph.invoke({name, user_query, session_id, turn, messages, message})
  │   │
  │   ▼
  │   intent_node → routes to one of: general | tools | escalate | approval_required
  │
  └─ Return GraphInvokeResponse(result=<final state>)
```

The route is wrapped in Langfuse `@observe()`, so the whole request becomes one trace.

## LangGraph state machine

Defined in `src/graph/builder.py`. Five nodes, all leaf nodes go to `END`:

```
START
  │
  ▼
intent  ──► general            ──► END
       ──► tools               ──► END
       ──► escalate            ──► END
       ──► approval_required   ──► END
```

The intent node returns a `Command(update=..., goto=...)` that LangGraph uses to jump directly to the chosen leaf.

### `GraphState` (src/states/config.py)

```python
class GraphState(TypedDict):
    name: str
    user_query: str
    session_id: str
    turn: int
    intent:          NotRequired[str]
    route:           NotRequired[str]
    confidence:      NotRequired[float]
    message:         NotRequired[str]   # final assistant text
    retrieved_docs:  NotRequired[list[dict]]
    token_usage:     NotRequired[dict]
    latency_ms:      NotRequired[float]
    reason:          NotRequired[str]
    action_payload:  NotRequired[dict]  # set when route == approval_required
```

### Nodes

#### `intent_node` (`src/nodes/intent.py`)

Calls `BedrockService.converse_structured()` with a forced tool-use schema:

```json
{
  "intent": "general | tools | escalate | approval_required",
  "route":  "general | tools | escalate | approval_required",
  "confidence": <number>,
  "reason": "<string>",
  "action_payload": {                    // required when route == approval_required
    "action_type": "<string>",
    "action_description": "<string>",
    "risk_level": "low | medium | high"
  }
}
```

Routing rules baked into the system prompt (`prompt_service.render("intent_router")`):

- **tools** — request needs document retrieval (financials, filings, company facts)
- **general** — conversational, no retrieval, no sensitive action
- **escalate** — ambiguous, out-of-scope, or confidence < 0.5 → human agent
- **approval_required** — any export/share/send/disclose request, regardless of phrasing → reviewer gate

The node returns `Command(update={...}, goto=route)`.

#### `general_node` (`src/nodes/general.py`)

`BedrockService.converse()` with the `general_assistant` prompt, temp 0.3, max_tokens 1024. Writes the turn to DynamoDB with `intent="general"`, `route="general"` and writes a cost row keyed by Claude Haiku 4.5 pricing ($0.80/M input, $4.00/M output).

#### `tools_node` (`src/nodes/tools.py`)

Builds a LangChain agent via `BedrockService.create_agent()` with `[semantic_document_search]` as the tool list and the `rag_assistant` prompt. The Langfuse `CallbackHandler` is attached so tool calls show up as nested spans. Extracts:

- final assistant text from the last `AIMessage`
- `retrieved_docs` from any `ToolMessage`s (first 200 chars of each chunk)
- `token_usage` from the last `AIMessage.usage_metadata`

Writes the turn (with `retrieved_docs`) and a cost row.

#### `hitl_escalate_node` (`src/nodes/hitl_escalate.py`)

Writes a fixed escalation message as the assistant turn, transitions session status to `hitl_pending`, and inserts a row into the HITL queue with `hitl_type="escalation"` and the model's `reason` for context.

#### `approval_gate_node` (`src/nodes/approval_gate.py`)

Writes a polite "your request needs supervisor authorization" message, transitions session status to `approval_pending`, and inserts a HITL row with `hitl_type="approval"` plus `action_type`, `action_description`, `risk_level` from `action_payload`.

## Services (`src/services/`)

| Service | File | Responsibility |
|---------|------|----------------|
| `BedrockService` | `bedrock.py` | `converse`, `converse_text`, `converse_stream`, `converse_structured` (forced tool-use for JSON), `create_agent`/`invoke_agent` (LangChain via `ChatBedrockConverse`) |
| `QdrantService` | `qdrant.py` | Collection bootstrap with payload indexes, deterministic `doc_id`/`chunk_id`/`point_id` derivation, upsert, list-by-doc, delete-by-doc, `semantic_search` with optional tag filter |
| `EmbeddingService` | `embedding.py` | Titan v2 embed (256-dim, normalised) with retry/backoff on throttling; sliding-window text chunking (size 512, overlap 64) |
| `ConversationService` | `conversation.py` | All DynamoDB writes: `write_turn`, `write_human_turn`, `write_user_turn_hitl`, status transitions (`mark_complete`, `mark_hitl_pending`, `mark_approval_pending`, `mark_session_active`), HITL writes/resolves, cost rows |
| `S3Service` | `s3.py` | Parse S3 event records, read PDF (via `pypdf`) or text, return `(text, metadata)` |
| `PromptService` | `prompt.py` | Langfuse-managed prompts with local `DEFAULT_PROMPTS` fallback; auto-creates Langfuse prompts on first miss; warmup at startup if `ENABLE_LANGFUSE` |
| `MCPService` | `mcp.py` | Optional `MultiServerMCPClient` wrapper for federated MCP tool servers (env-driven; not wired into the default graph) |

### `BedrockService` — methods at a glance

```
converse(user_message, system_prompt, messages, ...) → full Bedrock response dict
converse_text(...)            → plain string
converse_stream(...)          → generator of text deltas
converse_structured(...)      → dict matching json_schema (tool-use forced)
create_agent(tool_defs, system_prompt) → langchain agent
invoke_agent(user_query, tool_defs, system_prompt, messages, callbacks) → dict
```

Errors from `boto3` are wrapped in `RuntimeError` with the model id and the upstream message.

## Tools (`src/tools/`)

`semantic_document_search` (`src/tools/rag.py`) is the single retrieval tool exposed to the agent. It calls `EmbeddingService.embed_query()` then `QdrantService.semantic_search()` with optional tag filtering and returns the top-k hits with id, score, payload fields, and source URI.
