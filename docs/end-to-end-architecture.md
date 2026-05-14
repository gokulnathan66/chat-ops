# End-to-End Architecture

A single-file walkthrough of the LLMOps RAG application — every layer, every flow, every store. The legacy `docs/architecture.md` covers the chat request flow only; this document is the complete picture.

## 1. What this application is

A **LangGraph-based RAG API** for a financial assistant that answers questions about Apple, Google/Alphabet, and Microsoft 10-K filings. It combines:

- **AWS Bedrock — Claude Haiku 4.5** as the LLM, **Titan Embed v2** (256-dim, normalised) for embeddings
- **Qdrant** as the vector store
- **DynamoDB** for sessions, evaluations, cost rows, and the HITL queue
- **S3** for source documents and Lambda zip artifacts
- **Async ingestion pipeline** (S3 → SQS → Lambda → Qdrant → eval Lambda)
- **Scheduled post-conversation analysis** (EventBridge → PCA Lambda → degradation alerts)
- **Human-in-the-loop** — low-confidence escalation + sensitive-action approval gating
- **Langfuse** tracing and externalized prompt management
- **Two Next.js dashboards** — `ai-interface` (chat) and `realtime-monitoring` (ops view)

```
                 ┌────────────────────────────────────────────────────┐
                 │                  Next.js dashboards                │
                 │  ai-interface (chat)   realtime-monitoring (ops)   │
                 └───────────────┬───────────────────────┬────────────┘
                                 │                       │
                                 ▼                       ▼
                 ┌────────────────────────────────────────────────────┐
                 │       FastAPI on EC2  (src/main.py, port 8000)     │
                 │    /api/chat   /api/conversations   /api/hitl/*    │
                 │    /api/ingestion/*   /api/evaluations   /api/...  │
                 └───────────────┬─────────────────────────┬──────────┘
                                 │                         │
                                 ▼                         ▼
                  ┌──────────────────────────┐    ┌──────────────────┐
                  │  LangGraph state machine │    │   AWS services   │
                  │  intent → general/tools/ │    │  DynamoDB · S3   │
                  │  escalate/approval       │    │  Bedrock         │
                  └──────────────┬───────────┘    │  Lambda · SQS    │
                                 │                │  EventBridge     │
                                 ▼                │  Secrets · CW    │
                          ┌─────────────┐         └────────┬─────────┘
                          │   Bedrock   │                  │
                          │  Claude 4.5 │                  │
                          │   Titan v2  │                  │
                          └─────────────┘                  │
                                                           │
                          ┌─────────────┐                  │
                          │   Qdrant    │◄─────────────────┘
                          │  vector DB  │  upserts from ingestion Lambda
                          └─────────────┘
```

---

## 2. Repository layout

```
src/
  main.py                  FastAPI app + CORS + health
  api/
    routes.py              POST /api/chat, conversation reads
    dashboard.py           HITL, ingestion, golden queries, metrics
  graph/builder.py         LangGraph state machine (5 nodes)
  nodes/
    intent.py              4-way structured router (general/tools/escalate/approval_required)
    general.py             plain Bedrock chat
    tools.py               LangChain agent with semantic_document_search
    hitl_escalate.py       low-confidence → human handoff
    approval_gate.py       sensitive action → reviewer gate
  services/
    bedrock.py             Bedrock wrappers (converse, structured, agent)
    qdrant.py              vector store CRUD + payload indexes
    embedding.py           Titan embed + chunking
    conversation.py        DynamoDB writes for sessions/turns/HITL/cost
    prompt.py              Langfuse-managed prompts with local fallback
    s3.py                  S3 read + PDF parsing
    mcp.py                 optional MCP federation client
  tools/rag.py             semantic_document_search LangChain tool
  schema/config.py         Pydantic request/response models
  setting/config.py        pydantic-settings (env-driven)
  states/config.py         GraphState TypedDict

data/
  qdrant_ingestion.py      S3→SQS→Lambda handler

evaluations/
  eval_runner.py           Lambda handler — runs golden queries after ingestion
  rag_evaluator.py         RAG score + LLM-as-judge logic
  pca.py                   PCA scheduled Lambda + degradation detector

iac/
  Makefile                 wires Terraform stacks together (passes outputs)
  envs/{dev,prod}/*.tfvars per-env variables
  stacks/
    data/                  S3 bucket, 3 DynamoDB tables
    security/              Secrets Manager
    evaluations/           3 Lambdas, SQS, EventBridge schedules, IAM
    app/                   ECR, EC2, IAM instance profile, security group
    monitoring/            CloudWatch log groups, dashboard, alarms

dashboard/
  ai-interface/            Next.js chat UI
  realtime-monitoring/     Next.js ops UI (KPIs, evals, HITL, PCA, ingestion)
```

---

## 3. Chat request flow (FastAPI → LangGraph → Bedrock)

`POST /api/chat` is wrapped in Langfuse `@observe()`, so the entire request becomes a single trace.

```
POST /api/chat {user_query, session_id?, turn, ...}
  │
  ├─ Generate session_id if missing (uuid4)
  │
  ├─ Read session metadata from DynamoDB (conversations table)
  │   └─ if status == "hitl_pending":
  │        write user turn (intent="hitl_user_reply"), DO NOT invoke graph
  │        return immediately — a human owns the session
  │
  ├─ graph.invoke({name, user_query, session_id, turn, messages, message})
  │
  │   START
  │     │
  │     ▼
  │   intent_node
  │     ├─ Bedrock converse_structured (forced tool-use schema)
  │     ├─ Returns {intent, route, confidence, reason, action_payload?}
  │     └─ Command(update=..., goto=route)
  │
  │   ├─ route = "general"  → general_node  → END
  │   ├─ route = "tools"    → tools_node    → END
  │   ├─ route = "escalate" → hitl_escalate → END
  │   └─ route = "approval_required" → approval_gate → END
  │
  └─ Return GraphInvokeResponse(result=<final state>)
```

### `GraphState` (`src/states/config.py`)

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
    action_payload:  NotRequired[dict]  # only on approval_required
```

### Intent routing schema

The intent node calls `BedrockService.converse_structured()` with a forced tool-use schema:

```json
{
  "intent": "general | tools | escalate | approval_required",
  "route":  "general | tools | escalate | approval_required",
  "confidence": <number>,
  "reason": "<string>",
  "action_payload": {
    "action_type": "<string>",
    "action_description": "<string>",
    "risk_level": "low | medium | high"
  }
}
```

Routing policy (from the `intent_router` prompt):

| Route | Trigger |
|-------|---------|
| `tools` | User wants specific data — financials, filings, document lookup |
| `general` | Conversational, no retrieval, no sensitive action |
| `escalate` | Ambiguous, out-of-scope, or `confidence < 0.5` → human agent |
| `approval_required` | Any export/share/send/disclose request, regardless of phrasing |

### Per-leaf-node behaviour

| Node | LLM call | Side effects |
|------|----------|--------------|
| `general_node` | `BedrockService.converse()` with `general_assistant` prompt, temp 0.3, max_tokens 1024 | Writes `turn#NNN` + cost row |
| `tools_node` | `BedrockService.invoke_agent()` — LangChain agent over `[semantic_document_search]` with `rag_assistant` prompt and a Langfuse callback handler | Extracts retrieved docs from `ToolMessage`s and token usage from the last `AIMessage`; writes turn + cost row |
| `hitl_escalate_node` | None | Writes a fixed escalation message as the AI turn, sets session status `hitl_pending`, inserts HITL row (`hitl_type=escalation`, includes `reason`) |
| `approval_gate_node` | None | Writes a "supervisor authorization required" message, sets status `approval_pending`, inserts HITL row (`hitl_type=approval`, with `action_type`/`action_description`/`risk_level`) |

---

## 4. Services

| Service | File | Responsibility |
|---------|------|----------------|
| `BedrockService` | `services/bedrock.py` | `converse`, `converse_text`, `converse_stream`, `converse_structured` (forced tool-use), `create_agent`/`invoke_agent` (LangChain via `ChatBedrockConverse`) |
| `QdrantService` | `services/qdrant.py` | Collection bootstrap with payload indexes, deterministic `doc_id`/`chunk_id`/`point_id` derivation (sha256), upsert, scroll-list-by-doc, delete-by-doc, `semantic_search` with optional tag filter |
| `EmbeddingService` | `services/embedding.py` | Titan v2 embed (256-dim, normalised) with retry/backoff on throttling and `ServiceUnavailable`; sliding-window chunking (size 512, overlap 64) |
| `ConversationService` | `services/conversation.py` | All DynamoDB writes: `write_turn`, `write_human_turn`, `write_user_turn_hitl`, status transitions, HITL writes/resolves, cost rows |
| `S3Service` | `services/s3.py` | Parse S3 event records, read PDF (via `pypdf`) or text, return `(text, metadata)` |
| `PromptService` | `services/prompt.py` | Langfuse-managed prompts with local `DEFAULT_PROMPTS` fallback; auto-creates Langfuse prompts on first miss; warmup at startup if `ENABLE_LANGFUSE` |
| `MCPService` | `services/mcp.py` | Optional `MultiServerMCPClient` wrapper for federated MCP servers (env-driven; not wired into the default graph) |

### `BedrockService` API surface

```
converse(user_message, system_prompt, messages, ...) → full Bedrock response dict
converse_text(...)            → plain string
converse_stream(...)          → generator of text deltas
converse_structured(...)      → dict matching json_schema (tool-use forced)
create_agent(tool_defs, system_prompt) → langchain agent
invoke_agent(user_query, tool_defs, system_prompt, messages, callbacks) → dict
```

`boto3.ClientError` is wrapped in `RuntimeError` with the model id and the upstream message.

### The single retrieval tool

`semantic_document_search` (`src/tools/rag.py`) is the only tool exposed to the LangChain agent in `tools_node`. It embeds the query (Titan v2) and calls `QdrantService.semantic_search(top_k, tags?)`, returning each hit with id, score, payload fields, and source URI.

---

## 5. Storage

### 5.1 DynamoDB (3 tables)

All three are `PAY_PER_REQUEST`. Names are interpolated as `${project}-${env}-${tableName}`.

#### `conversations` — chat history

```
hash:  session_id (S)
range: sk         (S)        -- "metadata" | "turn#001", "turn#002", ...
GSI:   status-last_updated_at-index   (status, last_updated_at)
```

`metadata` rows hold `status` (`active` | `hitl_pending` | `approval_pending` | `complete`), `last_updated_at`, `turn_count`, `created_at`. `turn#NNN` rows hold `user_query`, `ai_response`, `intent`, `route`, `retrieved_docs`, `token_usage`, `latency_ms`, `created_at`. The status GSI powers `/api/conversations?status=...`.

#### `evaluations` — RAG scores, costs, PCA, golden queries, ingestion jobs

```
hash:  session_id (S)
range: sk         (S)
GSI:   eval_type-created_at-index     (eval_type, created_at)
```

Multi-tenant by `eval_type` discriminator on the GSI:

| `eval_type` | Written by | Contents |
|-------------|------------|----------|
| `rag` | `evaluations/rag_evaluator.py` | per golden-query: `rag_score`, `faithfulness`, `relevance`, `query` |
| `cost` | `ConversationService.write_cost` | per turn: `input_tokens`, `output_tokens`, `cost_usd`, `model_id` |
| `pca` | `evaluations/pca.py:analyze_conversation` | per stale session: `pca_topics`, `pca_sentiment`, `pca_unresolved` |
| `pca_alert` | `evaluations/pca.py:_write_degradation_alert` | sliding-window alert row |
| `golden_query` | `dashboard.py` POST `/api/golden-queries` | curated test questions |
| `ingestion_job` | `dashboard.py` + `qdrant_ingestion.py` | per upload: `status` (started → running → completed/error), counts, timestamps |

#### `hitl_queue` — human review queue

```
hash:  pk         (S)   -- always "HITL"
range: sk         (S)   -- "{ISO_TIMESTAMP}#{session_id}" or "{ISO}#pca_degradation"
GSI:   queue_status-sk-index          (queue_status, sk)
```

Items carry `hitl_type` (`escalation` | `approval`), `trigger`, `conversation_summary` (last 5 turns), score fields, and (for approvals) `turn_n`, `action_type`, `action_description`, `risk_level`. The GSI lets the dashboard list pending items with one query.

### 5.2 Qdrant — vectors + payload

- Collection: `settings.QDRANT_COLLECTION` (default `llmops-rag`), cosine distance, vector size = `settings.embedding_size` (256).
- Payload indexes auto-created at first write: `doc_id`, `chunk_id`, `text`, `source`, `title`, `url_or_file_path`, `tags`, `created_at`, `section`.
- Point ids are deterministic UUIDs derived from `chunk_id` (`sha256(chunk_id)[:16]` → UUID), so re-ingestion idempotently overwrites.
- `doc_id = sha256(f"{url_or_file_path}:{full_text}")` — full-text fingerprint, so any byte change yields a new doc.
- `delete_by_doc_id` cascades all chunk points for a logical document.

### 5.3 S3

- Single bucket per env: `${project}-documents-${account_id}` (versioning + AES256 + public access block).
- Document layout: `documents/{job_id}/{filename}`. The `job_id` is embedded in the key so the ingestion Lambda can extract it for status tracking, and so the `documents/` prefix filter on the S3 → SQS notification matches.
- Lambda zip is also stored here under `lambda-deployments/${project}-${env}-lambdas.zip` to bypass the 50 MB direct-upload limit.

---

## 6. Async ingestion pipeline

```
Dashboard upload  ─────────►  POST /api/ingestion/upload (FastAPI)
                                  │
                                  ├─ duplicate check vs Qdrant.list_documents()
                                  │
                                  ├─ S3 PutObject  documents/{job_id}/{filename}
                                  │   │
                                  │   ▼
                                  │  S3 Event Notification  (prefix=documents/, ObjectCreated:*)
                                  │   │
                                  │   ▼
                                  │  SQS  llmops-{env}-ingestion  (DLQ, maxReceiveCount=3)
                                  │   │
                                  │   ▼
                                  │  Lambda  qdrant_ingestion.lambda_handler
                                  │     ├─ unwrap SQS-wrapped S3 records (URL-decode keys)
                                  │     ├─ extract job_id from documents/{job_id}/...
                                  │     ├─ DDB UPDATE evaluations  status=running, started_at
                                  │     ├─ for each S3 record:
                                  │     │     S3Service.read_document   → text + metadata
                                  │     │     EmbeddingService.chunk_text + embed_texts
                                  │     │     QdrantService.build_points + upsert_points
                                  │     ├─ DDB UPDATE evaluations
                                  │     │     status=completed/error, chunks_indexed, files_*, completed_at
                                  │     └─ if completed:
                                  │           Lambda invoke (Event)  eval_runner   → see §7
                                  │
                                  └─ FastAPI returns {job_id, status: "started", s3_key, filename}
```

Re-ingestion (`POST /api/ingestion/start`) calls `s3.copy_object` source==dest with `MetadataDirective=REPLACE`, which re-fires the S3 event without any client uploading bytes again.

---

## 7. Evaluation pipelines

Two separate Lambdas, both writing to the `evaluations` table.

### 7.1 `eval_runner` — fires after every successful ingestion

`evaluations/eval_runner.py` → `evaluations/rag_evaluator.py`:

```
event = {"job_id": "..."}
  │
  ├─ load_golden_queries()  -- DDB query eval_type=golden_query
  │
  ├─ for each golden query:
  │     1. rag_tool_service.search(query, top_k)         -- embed + Qdrant search
  │     2. embedding_service.embed_query(query)
  │        embedding_service.embed_texts(retrieved chunks)
  │        rag_score = max(cosine(query_emb, doc_emb))   -- best-hit similarity
  │     3. run_llm_judge(question, retrieved_docs, top_answer)
  │        -- Bedrock converse_structured against LLM_JUDGE_SCHEMA
  │        -- returns {faithfulness, relevance, reason} on [0,1]
  │     4. DDB put_item evaluations
  │        eval_type="rag", session_id=job_id, sk="eval#rag#{ts}"
  │        rag_score, faithfulness, relevance, query, created_at
  │
  └─ return {job_id, queries_evaluated, results}
```

Cost rows live in the same table with `eval_type=cost` and pricing baked into `ConversationService.write_cost` (Claude Haiku 4.5: $0.80/M input, $4.00/M output).

### 7.2 `pca_runner` — scheduled post-conversation analysis

`evaluations/pca.py`, triggered by EventBridge (`pca_schedule`):

```
handler:
  ├─ get_stale_sessions()
  │   -- DDB query GSI status-last_updated_at-index where status="active"
  │      and last_updated_at < (now − INACTIVITY_MINUTES)
  │
  ├─ for each stale session:
  │     mark_complete(session_id)         -- conversations metadata.status=complete
  │     analyze_conversation(session_id)  -- Bedrock converse_structured against PCA_SCHEMA
  │       returns {topics[], sentiment in {pos,neutral,neg}, unresolved_questions[]}
  │     DDB put_item evaluations
  │       eval_type="pca", sk="eval#pca#{ts}", pca_*, created_at
  │
  └─ if any results:
        detect_degradation()
          -- query last PCA_DEGRADATION_WINDOW pca rows
          -- if neg_ratio ≥ PCA_DEGRADATION_THRESHOLD
             OR avg_unresolved ≥ PCA_UNRESOLVED_THRESHOLD:
               dedup vs recent pca_alert rows
               write HITL row (sk="{ts}#pca_degradation", trigger="pca_degradation")
               write evaluations row (eval_type="pca_alert", summary, ratios)
```

This is what closes the LLMOps loop: the system flags itself when sentiment drops or unresolved questions accumulate, surfacing system-level degradation as a HITL ticket.

---

## 8. Human-in-the-loop (HITL)

Two distinct flows share the same queue table but use `hitl_type` to disambiguate.

### 8.1 Escalation (low confidence / out-of-scope)

```
intent_node (route=escalate)
  └─ hitl_escalate_node
        write turn:    intent=escalate, ai_response=<fixed escalation message>
        mark session:  hitl_pending
        write HITL:    hitl_type=escalation, trigger="bot_escalation",
                       conversation_summary=<last 5 turns>, reason=<router reason>

POST /api/chat while hitl_pending:
  └─ user message is APPENDED to conversation, AI does not run
     (write_user_turn_hitl, intent="hitl_user_reply")

POST /api/hitl/{queue_id}/respond {human_response}
  └─ writes human turn (intent=human, route=human)
     -- session stays hitl_pending — user and human keep chatting

POST /api/hitl/{queue_id}/resolve
  └─ resolve_hitl(queue_id, "resolved by human agent")
     mark_session_active(session_id)   -- AI takes over again
```

### 8.2 Approval (sensitive action)

```
intent_node (route=approval_required, requires action_payload)
  └─ approval_gate_node
        write turn:    intent=approval_required, ai_response=<auth-required message>
        mark session:  approval_pending
        write HITL:    hitl_type=approval, action_type, action_description,
                       risk_level, turn_n=<original turn>

POST /api/hitl/{queue_id}/approve {decision: "approve"|"reject", note: ""}
  └─ format outcome message:
        approve → "Your request to '<X>' has been approved. <note>"
        reject  → "Your request to '<X>' was not approved. <note>"
     write_human_turn(turn_n+1, outcome)
     resolve_hitl, mark_session_active
```

### 8.3 PCA degradation alerts

The PCA runner can emit synthetic HITL rows with `session_id="system"`, `trigger="pca_degradation"`. Operators see them in the same queue alongside per-session escalations.

---

## 9. Infrastructure (Terraform, 5 stacks)

`iac/Makefile` is the orchestration layer. Each stack uses the S3 backend at `s3://llmops-langgraph-terraform/<env>/<stack>/terraform.tfstate` in `ap-south-1`. The Makefile pipes `terraform output` from upstream stacks into downstream stack variables (e.g. `data` outputs feed into `evaluations` and `app`; `app` and `evaluations` feed into `monitoring`). `make apply-all` walks them in order: `data → security → evaluations → app → monitoring`.

### 9.1 `data` stack

- S3 documents bucket (versioning, AES256, public access block)
- 3 DynamoDB tables (see §5.1)

### 9.2 `security` stack

- Secrets Manager secret `${project}/app-secrets` containing `MODEL_ID`, Qdrant + Langfuse + S3 + table refs. EC2 reads it at boot via `user_data.sh`.

### 9.3 `evaluations` stack

- 3 Lambdas (`eval_runner`, `pca_runner`, `qdrant_ingestion`) — Python 3.12, 512 MB, 300s, all sharing the same S3-hosted zip and a common env block.
- SQS `ingestion` queue (visibility 300s) + DLQ (14-day retention, maxReceiveCount=3).
- S3 → SQS notification with `prefix=documents/` and `s3:ObjectCreated:*`.
- `aws_lambda_event_source_mapping` ties SQS → `qdrant_ingestion` (batch_size=10).
- EventBridge schedules: `eval_schedule` → `eval_runner`, `pca_schedule` → `pca_runner`.
- IAM role with permissions for the 3 DDB tables, S3 bucket, Bedrock invoke, Lambda invoke (for the `eval_runner` async fan-out).

### 9.4 `app` stack

- ECR repository (mutable tags, scan-on-push, lifecycle: keep last 10 images).
- EC2 (Amazon Linux 2023, instance profile with `secretsmanager:GetSecretValue`, ports 22/443/8000 open). `user_data.sh` reads the secret, logs into ECR, pulls the tagged image, runs the container.
- Security group (8000 + 443 world-open, SSH restricted by `var.ssh_cidr_blocks`).

### 9.5 `monitoring` stack

- CloudWatch log groups for each Lambda (retention configurable).
- One CloudWatch dashboard (`llmops-${env}`) with widgets for Lambda Errors, Lambda Duration, EC2 CPU.
- Alarms: per-Lambda error count ≥ threshold; EC2 CPU > 80% for 2 evaluation periods.

---

## 10. Dashboards (`dashboard/`)

Both apps are Next.js with `app/`, `components/`, and `lib/api.ts` for the FastAPI client.

### `ai-interface/` — chat UI

- `app/page.tsx` — main chat surface
- `components/SessionList.tsx` — session sidebar (calls `/api/conversations?status=...`)
- `components/ChatThread.tsx` — message thread + `POST /api/chat` invocation, with HITL-aware behaviour (renders human turns differently, disables input while approval pending)

### `realtime-monitoring/` — operations UI

- `app/page.tsx` — KPIs from `/api/metrics/summary` (avg RAG score, avg faithfulness, today's cost, HITL pending count) via `components/KpiCards.tsx`
- `app/evals/page.tsx` — RAG evaluations list (`GET /api/evaluations?type=rag`)
- `app/pca/page.tsx` — PCA results (sentiment timeline, unresolved questions, degradation alerts)
- `app/hitl/page.tsx` + `components/HitlQueue.tsx` — pending escalations and approvals; respond/resolve/approve actions
- `app/ingestion/` + `components/IngestionPanel.tsx` — upload, history, document list, delete-by-doc

---

## 11. Configuration

All runtime config is environment-driven via `src/setting/config.py` (`pydantic-settings`). Values default safely for local dev and are overridden by the EC2 secret in production.

| Group | Variables |
|-------|-----------|
| LLM | `MODEL_ID` (default `us.anthropic.claude-haiku-4-5-20251001-v1:0`), `TEMPERATURE`, `MAX_TOKENS` |
| Qdrant | `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`, `QDRANT_COLLECTION` |
| Storage | `S3_BUCKET_NAME` |
| Langfuse | `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL`, `LANGFUSE_DEBUG`, `ENABLE_LANGFUSE` |
| AWS | `AWS_REGION` (default `us-east-1`) |
| DynamoDB | `CONVERSATIONS_TABLE`, `EVALUATIONS_TABLE`, `HITL_TABLE` |
| Embedding | `embedding_model` (`amazon.titan-embed-text-v2:0`), `embedding_size` (256), `chunk_size` (512), `chunk_overlap` (64), `top_k` (5) |
| Eval thresholds | `INACTIVITY_MINUTES` (15), `RAG_THRESHOLD` (0.6), `HITL_THRESHOLD` (0.6), `RAG_RERANK_TOP_K_MULTIPLIER` (2) |
| PCA | `PCA_DEGRADATION_WINDOW` (10), `PCA_DEGRADATION_THRESHOLD` (0.6), `PCA_UNRESOLVED_THRESHOLD` (3) |
| Lambda refs | `LAMBDA_EVAL_RUNNER_FUNCTION` |

When `ENABLE_LANGFUSE=true`, the relevant env vars are mirrored into `os.environ` so the Langfuse SDK picks them up, and `prompt_service.warmup()` ensures every default prompt exists in Langfuse with a `production` label.

### Prompts

Three prompts are managed in Langfuse with local fallbacks in `services/prompt.py`:

- `rag_assistant` — financial-analyst system prompt for the agent (tool-use, citations, no fabrication)
- `general_assistant` — conversational assistant, no retrieval
- `intent_router` — 4-way routing rules (the source of truth for routing policy lives here, not in code)

---

## 12. Observability

- **Langfuse** — every `@observe()` decorator wraps a span. The chat endpoint, the graph build, and each node are traced; `tools_node` additionally attaches a `langfuse.langchain.CallbackHandler` to catch agent-internal tool calls.
- **Cost telemetry** — every successful turn writes a row to `evaluations` with `eval_type=cost` (input/output tokens, computed USD). `/api/metrics/summary` aggregates today's cost.
- **CloudWatch** — Lambda log groups, dashboard widgets (errors, duration, EC2 CPU), and alarms.
- **PCA degradation** — sliding-window negative-sentiment / unresolved-question detection, deduped against recent `pca_alert` rows, surfaces as a HITL ticket.

---

## 13. End-to-end happy path (one trace)

1. Frontend calls `POST /api/chat {user_query: "What was Microsoft's FY2025 revenue?"}` against the EC2-hosted FastAPI.
2. Langfuse opens a trace. `intent_node` → Bedrock (forced tool-use) → `route="tools"`, `confidence=0.92`.
3. `tools_node` builds a LangChain agent over `[semantic_document_search]`. Agent loop: think → call `semantic_document_search` → Titan v2 embeds query → Qdrant returns top-5 chunks → agent composes the cited answer.
4. `ConversationService.write_turn` writes `turn#001` to `conversations`. `ConversationService.write_cost` writes a `cost` row to `evaluations`.
5. Response returns to the dashboard. Langfuse trace shows: route call · agent loop · tool call · final answer · token counts.
6. After 15 minutes of inactivity, the EventBridge schedule fires `pca_runner`. The session is marked `complete`, analysed, and stored as an `eval_type=pca` row. If aggregate sentiment degrades across the window, a `pca_alert` is written and a HITL row is queued.
