# LLMOps — End-to-End Design Spec

**Date:** 2026-04-19  
**Status:** Approved

---

## Overview

Full LLMOps platform built on the existing LangGraph + AWS Bedrock + Qdrant backend. Adds conversation persistence, async evaluation (RAG quality, cost, post-conversation analysis), HITL escalation, golden dataset monitoring, and two Next.js dashboards.

---

## Architecture

### Option: Lambda-Native Pipeline (chosen)

All evaluation is decoupled from chat latency via scheduled Lambdas. FastAPI handles chat and dashboard API. DynamoDB is the single store for conversations, evaluations, HITL queue, and golden results.

### Component Map

```
User
 ├── AI Interface Dashboard (Next.js)   dashboard/ai-interface/
 └── Monitoring Dashboard (Next.js)     dashboard/realtime-monitoring/
         ↕ REST (FastAPI)
FastAPI
 ├── POST /api/chat → LangGraph → Bedrock / Qdrant → DynamoDB (write turn)
 ├── GET/POST /api/conversations, /api/evaluations, /api/hitl, /api/golden-results
 └── POST /api/ingestion/start → triggers qdrant_ingestion Lambda

DynamoDB (4 tables)
 └── fed by: LangGraph nodes (turns), eval Lambdas (results), HITL resolution (dashboard)

Scheduled Lambdas (cron, interval configurable via Terraform vars)
 ├── eval_runner         — scans idle/complete sessions, orchestrates eval
 ├── rag_evaluator       — embedding similarity + LLM-as-judge + re-retrieve + HITL flag
 ├── pca                 — Bedrock structured analysis (topics, sentiment, unresolved)
 └── golden_dataset_runner — replays golden.json through LangGraph, scores with LLM-as-judge

Existing (unchanged interface)
 ├── qdrant_ingestion Lambda  — S3 → Qdrant vector ingestion
 ├── Qdrant                   — vector search
 ├── S3                       — document storage + golden.json
 └── Langfuse                 — trace observability
```

---

## Data Model (DynamoDB)

### `conversations`

Two item shapes share the same table:

**Session metadata item** (SK=`metadata`):
| Key | Type | Notes |
|-----|------|-------|
| PK: `session_id` | String | Client-generated or assigned by FastAPI |
| SK: `metadata` | String | Literal string |
| `status` | String | `active` → `complete` → `evaluated` |
| `last_updated_at` | String | ISO 8601, updated on every turn write |
| `created_at` | String | ISO 8601 |
| `turn_count` | Number | Incremented per turn |

**Turn item** (SK=`turn#<n>`):
| Key | Type | Notes |
|-----|------|-------|
| PK: `session_id` | String | |
| SK: `turn#<n>` | String | Zero-padded (e.g. `turn#001`) |
| `user_query` | String | |
| `ai_response` | String | |
| `intent` | String | `general` or `tools` |
| `route` | String | Node that handled the turn |
| `retrieved_docs` | List | `[{doc_id, title, score, text_snippet}]` |
| `token_usage` | Map | `{input, output}` |
| `latency_ms` | Number | |
| `created_at` | String | ISO 8601 |

**GSI:** `status-last_updated_at-index` on the metadata item — eval Lambda queries `status=complete` ordered by `last_updated_at` to find sessions idle beyond threshold.

### `evaluations`
| Key | Type | Notes |
|-----|------|-------|
| PK: `session_id` | String | |
| SK: `eval#<type>#<timestamp>` | String | type: `rag`, `llm_judge`, `cost`, `pca`, `golden` |
| `eval_type` | String | |
| `rag_score` | Number | Embedding similarity: query vs retrieved docs |
| `faithfulness` | Number | LLM-as-judge 0–1 |
| `relevance` | Number | LLM-as-judge 0–1 |
| `cost_usd` | Number | Derived from token_usage + Bedrock pricing |
| `pca_topics` | List | Extracted topic strings |
| `pca_sentiment` | String | `positive`, `neutral`, `negative` |
| `pca_unresolved` | List | Unresolved question strings |
| `llm_judge_score` | Number | Overall 0–1 |
| `llm_judge_reason` | String | |
| `re_retrieved` | Boolean | Whether re-retrieval was triggered |
| `hitl_flagged` | Boolean | |
| `eval_model` | String | Model ID used for eval |
| `created_at` | String | |

**GSI:** `eval_type-created_at-index` — monitoring dashboard queries by type and time.

### `hitl_queue`
| Key | Type | Notes |
|-----|------|-------|
| PK: `queue_status` | String | `pending`, `in_review`, `resolved` |
| SK: `<created_at>#<session_id>` | String | Enables time-ordered queue per status |
| `session_id` | String | |
| `trigger` | String | `rag_eval`, `llm_judge`, `user_escalation` |
| `conversation_summary` | String | Last 5 turns concatenated (user_query + ai_response) |
| `rag_score` | Number | Score that triggered flag |
| `llm_judge_score` | Number | |
| `assigned_to` | String | Human agent identifier |
| `human_response` | String | |
| `resolved_at` | String | |

### `golden_results`
| Key | Type | Notes |
|-----|------|-------|
| PK: `run_id` | String | UUID per scheduled run |
| SK: `question_id` | String | Matches ID in `golden.json` |
| `question` | String | |
| `expected_answer` | String | |
| `actual_answer` | String | |
| `llm_judge_score` | Number | |
| `faithfulness` | Number | |
| `relevance` | Number | |
| `pass` | Boolean | score ≥ threshold (default 0.7) |
| `run_at` | String | |

**GSI:** `run_at-index` — trending pass rate over time on monitoring dashboard.

---

## Conversation Lifecycle

```
active  →  (idle > threshold)  →  complete  →  (eval Lambda)  →  evaluated
                                                                       ↓
                                                           if score < threshold
                                                                       ↓
                                                           hitl_queue: pending
                                                                       ↓
                                                    human responds via dashboard
                                                                       ↓
                                                           hitl_queue: resolved
```

---

## Backend Changes

### New: `src/services/conversation.py` — `ConversationService`

```
write_turn(session_id, turn_n, data) → None
mark_complete(session_id) → None
get_conversation(session_id) → list[dict]
list_conversations(status, limit) → list[dict]
write_hitl(session_id, trigger, scores) → None
resolve_hitl(queue_id, human_response) → None
```

Wraps all DynamoDB reads/writes. Used by both graph nodes and eval Lambdas.

### New: `src/api/dashboard.py`

```
GET  /api/conversations                   list with status filter
GET  /api/conversations/{session_id}      full turn history
GET  /api/evaluations?type=&limit=        eval records
GET  /api/hitl?status=pending             HITL queue
POST /api/hitl/{id}/respond               human agent response
GET  /api/golden-results?run_id=          golden run detail
GET  /api/metrics/summary                 KPI aggregates for dashboard header
POST /api/ingestion/start                 trigger qdrant_ingestion Lambda
```

### Modified: `src/states/config.py`

Add to `GraphState`:
```python
session_id: str
turn: int
retrieved_docs: NotRequired[list[dict]]
token_usage: NotRequired[dict]
latency_ms: NotRequired[float]
```

### Modified: `src/nodes/tools.py` and `src/nodes/general.py`

After node execution, call `ConversationService.write_turn()` with query, response, retrieved docs (tools node only), token usage, and latency. `session_id` and `turn` flow through `GraphState`.

### Modified: `src/api/routes.py`

Accept optional `session_id` in `GraphInvokeRequest`. If absent, generate a UUID. Pass through to graph state.

---

## Lambda Pipeline

### `eval_runner.py` (new — cron entrypoint)

- Triggered on configurable cron (Terraform var, default every 15 min)
- Queries `conversations` GSI for sessions with `status=complete` not yet evaluated
- Also marks sessions `active` → `complete` if `last_updated > inactivity_threshold`
- For each session: invokes `rag_evaluator` + `pca` (parallel where possible)
- Writes cost evaluation (sum token_usage × Bedrock pricing per model)
- Updates session `status=evaluated`

### `rag_evaluator.py` (fill stub)

1. Fetch all turns for session from `conversations`
2. For each tools-node turn:
   - Compute embedding similarity: `embed(user_query)` dot `embed(retrieved_doc_text)` → `rag_score`
3. Call Bedrock LLM-as-judge with prompt:
   - Input: question + retrieved docs + answer
   - Output: `{faithfulness: float, relevance: float, reason: str}`
4. If `rag_score < RAG_THRESHOLD` (default 0.6):
   - Re-query Qdrant with `top_k * 2`
   - Re-score
   - If still below threshold: set `hitl_flagged=True`, write to `hitl_queue`
5. Write eval record to `evaluations` table

### `pca.py` (fill stub)

1. Fetch all turns for session, concatenate into conversation text
2. Call Bedrock with structured prompt:
   ```
   Analyze this conversation. Return JSON:
   { "topics": [...], "sentiment": "positive|neutral|negative",
     "unresolved_questions": [...] }
   ```
3. Write to `evaluations` with `eval_type=pca`

### `golden_dataset_runner.py` (new)

1. Load `golden.json` from S3 (`[{id, question, expected_answer}]`)
2. For each entry: invoke LangGraph directly (import graph, call `graph.invoke()`)
3. Score with LLM-as-judge (same prompt as rag_evaluator)
4. Batch-write to `golden_results` with shared `run_id = uuid + timestamp`

---

## Dashboard Specs

### `dashboard/ai-interface` (Next.js)

**Pages:**
- `/` — session list (left sidebar) + chat thread view (main)
- `/hitl` — HITL queue: pending → in_review → resolved pipeline
- `/ingestion` — ingestion job status table + start ingestion form

**Chat thread view features:**
- Shows all turns per session with: node used, latency, cost per turn, retrieved docs (collapsible)
- "Escalate to Human" button per session → POST `/api/hitl` with `trigger=user_escalation`

**HITL queue features:**
- Columns: session summary, trigger reason, RAG score, LLM-judge score, created at
- Click → expand full conversation + text area for human response
- Submit → POST `/api/hitl/{id}/respond` → moves to resolved

**Ingestion features:**
- Table: filename, status (processing/indexed/failed), chunk count, indexed at
- "Start Ingestion" → POST `/api/ingestion/start` with S3 key

### `dashboard/realtime-monitoring` (Next.js)

**Pages:**
- `/` — overview: KPI cards + recent evals table + latest PCA strip
- `/evals` — full RAG evaluations table with filters (date, score range, HITL flagged)
- `/golden` — golden dataset run history: pass rate trend chart + per-question drill-down
- `/pca` — PCA results: topics frequency, sentiment distribution, unresolved questions list

**KPI cards (header row):**
- Golden pass rate (%), avg RAG score, avg faithfulness, cost today ($), HITL pending count

**Auto-refresh:** poll `/api/metrics/summary` every 30 seconds.

---

## Terraform Changes (`iac/terraform-aws/`)

- `dynamodb.tf` — define 4 tables with GSIs
- `lambda.tf` — add `eval_runner`, `rag_evaluator`, `pca`, `golden_dataset_runner` functions
- `cloudwatch.tf` — EventBridge cron rules for eval_runner and golden_dataset_runner
- `variables.tf` — `eval_cron_schedule` (default `rate(15 minutes)`), `golden_cron_schedule` (default `rate(1 hour)`), `rag_threshold` (default `0.6`), `hitl_threshold` (default `0.6`)

---

## Golden Dataset Format (`golden.json` in S3)

```json
[
  {
    "id": "q1",
    "question": "What is the Q4 pricing for product X?",
    "expected_answer": "Product X is priced at $49/month in Q4 2024."
  }
]
```

---

## Key Thresholds (configurable via env/Terraform vars)

| Variable | Default | Used by |
|----------|---------|---------|
| `INACTIVITY_MINUTES` | 15 | eval_runner: active→complete |
| `RAG_THRESHOLD` | 0.6 | rag_evaluator: triggers re-retrieve |
| `HITL_THRESHOLD` | 0.6 | rag_evaluator: triggers HITL flag after re-retrieve |
| `GOLDEN_PASS_THRESHOLD` | 0.7 | golden_dataset_runner: pass/fail per question |
| `RAG_RERANK_TOP_K_MULTIPLIER` | 2 | rag_evaluator: re-retrieve with top_k × multiplier |

---

## Out of Scope

- Authentication/authorization for dashboards (assumed internal tool)
- Real-time WebSocket streaming of eval results (polling is sufficient)
- Email/Slack notifications for HITL (dashboard queue only)
- Editing golden dataset through the dashboard UI (managed via git)
