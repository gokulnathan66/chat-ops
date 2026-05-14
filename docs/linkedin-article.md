# LLMOps End-to-End RAG Platform

This repository contains a production-grade RAG assistant for financial documents with an LLMOps layer: intent routing, RAG evaluation, Langfuse-based observability, and human-in-the-loop (HITL) workflows.

If you've ever shipped a RAG demo and then wondered "is this actually working in production?", this project shows one way to answer that with code, infra, and dashboards.

**Who is this for:**
- AI / backend engineers working on RAG systems
- MLOps/LLMOps folks looking for evaluation and observability patterns
- Infra engineers interested in Terraform-based LLM deployments

**What you'll learn:**
- How to design a LangGraph-based pipeline with intent routing
- How to measure RAG and answer quality continuously
- How to add HITL + monitoring from day one

For the full architecture diagram, see [`llmops-architecture.drawio`](../llmops-architecture.drawio) (open with [draw.io](https://app.diagrams.net/)).

---

## Quickstart

### Prerequisites

- Python 3.13 and `uv` (or `pip`) for backend
- Node.js 18+ and `npm` for Next.js dashboards
- Docker for running Qdrant locally (or a managed Qdrant instance)
- AWS account with:
  - Bedrock enabled (Claude Haiku 4.5, Titan Embed Text v2) in your chosen region
  - DynamoDB, Lambda, S3, CloudWatch, Secrets Manager
- Terraform 1.6+ for infrastructure stacks

### Clone and configure

```bash
git clone https://github.com/gokulnathan66/llmops.git
cd llmops
cp .env.example .env
```

Edit `.env` and set:
- `AWS_REGION`, `MODEL_ID`, `embedding_model`
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY` (if remote)
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`

> **Note:** On EC2, `userdata.sh` pulls secrets from Secrets Manager and writes `.env`, so `.env` values must match secret names in the `security` stack.

### Run services locally

**1. Backend (FastAPI + LangGraph)**

```bash
uv sync
docker compose up -d          # local Qdrant on :6333
make ingest                   # ingest knowledge base into Qdrant
make dev                      # FastAPI with hot reload on :8000
```

**2. Monitoring dashboard**

```bash
cd dashboard/realtime-monitoring
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev -- -p 3000   # http://localhost:3000
```

**3. AI interface**

```bash
cd dashboard/ai-interface
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev -- -p 3001   # http://localhost:3001
```

Both dashboards expect the backend to be reachable at the configured `NEXT_PUBLIC_API_URL`.

### Deploy infrastructure (optional)

Infra is split into five Terraform stacks, each with its own state:

```bash
cd iac
make apply-all ENV=dev
```

Or apply individually in dependency order:

```bash
cd iac/stacks/data && terraform init && terraform apply -var-file=env/dev.tfvars
cd ../security && terraform init && terraform apply -var-file=env/dev.tfvars
cd ../evaluations && terraform init && terraform apply -var-file=env/dev.tfvars
cd ../app && terraform init && terraform apply -var-file=env/dev.tfvars
cd ../monitoring && terraform init && terraform apply -var-file=env/dev.tfvars
```

Before applying `evaluations`, build the Lambda zip:

```bash
bash scripts/build_lambda_zip.sh   # outputs iac/dist/lambdas.zip
```

---

## Architecture Overview

At a high level:

- **AI Interface (Next.js, port 3001)** — customer-facing chat UI with session list, route badges (`GENERAL`, `TOOLS`, `ESCALATED`, `APPROVAL REQUIRED`), latency + token metrics, and source snippets for RAG responses.
- **Monitoring Dashboard (Next.js, port 3000)** — operator-facing overview of RAG quality, evaluators, PCA, HITL queue, and ingestion.
- **FastAPI Backend (port 8000)** — hosts the LangGraph pipeline, LangChain agent, cost tracker, and dashboard APIs.
- **LangGraph Pipeline** — intent-routing state machine with `intent`, `general`, `tools`, `escalate`, and `approval_required` nodes.
- **Data layer** — Qdrant for vector search, DynamoDB tables for evaluations and HITL queue, S3 for document storage.
- **Evaluation stack** — LLM-based RAG evaluation and post-conversation analysis via Lambda and SQS.
- **Observability** — Langfuse for traces, prompt versioning, and LLM-as-judge metrics.

See [`llmops-architecture.drawio`](../llmops-architecture.drawio) for the full diagram.

---

## Project Structure

```
llmops/
├── src/                                    # FastAPI + LangGraph application
│   ├── main.py                             # FastAPI app entry point (CORS, routers, /health)
│   ├── api/
│   │   ├── routes.py                       # POST /api/chat — LangGraph pipeline endpoint
│   │   └── dashboard.py                    # Dashboard, HITL, ingestion, golden query, metrics endpoints
│   ├── graph/
│   │   └── builder.py                      # LangGraph state machine (5 nodes, conditional edges)
│   ├── nodes/
│   │   ├── intent.py                       # Intent router → "general" | "tools" | "escalate" | "approval_required"
│   │   ├── general.py                      # Direct LLM response node · writes cost record per turn
│   │   ├── tools.py                        # RAG agent node (LangChain + Qdrant) · writes cost record per turn
│   │   ├── hitl_escalate.py                # Escalation node: marks session hitl_pending, creates HITL queue item
│   │   └── approval_gate.py               # Approval node: marks session approval_pending, creates approval item
│   ├── services/
│   │   ├── bedrock.py                      # AWS Bedrock: converse(), structured_output(), invoke_agent()
│   │   ├── conversation.py                 # DynamoDB: turns, metadata, HITL queue, human turns, cost records
│   │   ├── embedding.py                    # Titan Embed v2 via Bedrock + exponential backoff retry
│   │   ├── prompt.py                       # Langfuse prompt versioning + hardcoded fallbacks
│   │   ├── qdrant.py                       # Qdrant: collection, upsert, semantic search, list_documents, delete
│   │   ├── s3.py                           # S3: PDF + CSV document reader
│   │   └── mcp.py                          # MCP server client
│   ├── tools/
│   │   └── rag.py                          # semantic_document_search LangChain tool
│   ├── schema/
│   │   └── config.py                       # Pydantic request/response models
│   ├── states/
│   │   └── config.py                       # GraphState TypedDict (route, messages, metadata, flags)
│   └── setting/
│       └── config.py                       # Pydantic Settings (all env-based config, thresholds, model IDs)
│
├── evaluations/                            # Evaluation pipeline (Lambda handlers)
│   ├── rag_evaluator.py                    # Golden queries → semantic search → cosine sim + LLM judge
│   ├── eval_runner.py                      # Lambda entry point: invoked after ingestion, runs RAG evals
│   └── pca.py                              # Post-conversation analysis: topics, sentiment, unresolved questions
│
├── data/                                   # Knowledge base + ingestion Lambda
│   ├── qdrant_ingestion.py                 # Lambda: SQS (S3 event) → chunk → embed → Qdrant
│   ├── csv/                                # Financial CSV data
│   │   ├── big_tech_company_profiles.csv
│   │   ├── big_tech_financials_summary.csv
│   │   └── big_tech_segment_revenue.csv
│   └── pdfs/
│       ├── annual_reports/                 # Apple, Google, Microsoft 10-K 2025
│       └── news_articles/                  # AI features, cloud growth, advertising
│
├── dashboard/                              # Next.js frontend applications
│   ├── realtime-monitoring/                # Monitoring + ops dashboard (port 3000)
│   │   └── src/
│   │       ├── app/
│   │       │   ├── page.tsx                # Overview: KPI cards, eval table, PCA strip
│   │       │   ├── evals/page.tsx          # Golden queries + RAG/faithfulness/relevance scores
│   │       │   ├── pca/page.tsx            # Sentiment, topics, unresolved questions
│   │       │   ├── hitl/page.tsx           # HITL queue: escalation + approval workflows
│   │       │   └── ingestion/page.tsx      # Upload, job status, doc list, delete
│   │       ├── components/
│   │       │   ├── KpiCards.tsx            # Avg RAG, Avg Faithfulness, Cost Today, HITL Pending
│   │       │   ├── HitlQueue.tsx           # Escalation/approval queue with live conversation
│   │       │   ├── IngestionPanel.tsx      # Upload + doc list + cascaded delete
│   │       │   ├── NavSidebar.tsx          # Navigation sidebar
│   │       │   └── ThemeProvider.tsx       # Dark mode support
│   │       └── lib/api.ts                  # API client (calls FastAPI backend)
│   └── ai-interface/                       # Chat interface (port 3001)
│       └── src/
│           ├── app/page.tsx                # Chat interface with session list
│           ├── components/
│           │   ├── ChatThread.tsx           # Message thread with route badges, latency, sources
│           │   ├── SessionList.tsx          # Session list with status badges
│           │   ├── NavSidebar.tsx           # Navigation sidebar
│           │   └── ThemeProvider.tsx        # Dark mode support
│           └── lib/api.ts                  # API client (calls FastAPI backend)
│
├── iac/                                    # Infrastructure as Code
│   ├── Makefile                            # Orchestrated Terraform targets (init, plan, apply per stack)
│   ├── envs/                               # Per-environment tfvars (dev/, prod/)
│   └── stacks/                             # 5 independent Terraform stacks
│       ├── app/                            # EC2, ECR, IAM, user_data.sh
│       │   ├── main.tf                     # Provider + backend config
│       │   ├── ec2.tf                      # EC2 instance (Docker host)
│       │   ├── ecr.tf                      # ECR repository for API image
│       │   ├── iam.tf                      # IAM roles + policies
│       │   ├── user_data.sh                # EC2 bootstrap (pulls secrets, runs container)
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── data/                           # DynamoDB tables + S3 bucket
│       │   ├── main.tf
│       │   ├── dynamodb.tf                 # conversations, evaluations, hitl_queue tables + GSIs
│       │   ├── s3.tf                       # Documents bucket with event notifications
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── evaluations/                    # Lambdas + SQS + EventBridge
│       │   ├── main.tf
│       │   ├── lambda.tf                   # eval_runner, pca_runner, qdrant_ingestion
│       │   ├── sqs.tf                      # Ingestion queue + S3 event notification
│       │   ├── eventbridge.tf              # Cron: pca_runner every 15 min
│       │   ├── iam.tf                      # Lambda execution roles
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── monitoring/                     # CloudWatch
│       │   ├── main.tf
│       │   ├── cloudwatch.tf               # Dashboard + alarms
│       │   ├── variables.tf
│       │   └── outputs.tf
│       └── security/                       # Secrets Manager
│           ├── main.tf
│           ├── secrets.tf                  # Secret entries (API keys, DB creds)
│           ├── variables.tf
│           └── outputs.tf
│
├── scripts/                                # Automation scripts
│   ├── build_lambda_zip.sh                 # Docker-based Lambda zip (linux/amd64, includes .dist-info)
│   ├── deploy.sh                           # Full deployment script (build + push + apply)
│   └── local_e2e_test.sh                   # Local end-to-end test runner
│
├── tests/                                  # Test suite
│   ├── api/
│   │   └── test_dashboard.py              # Dashboard endpoint tests
│   ├── services/
│   │   └── test_conversation.py           # DynamoDB conversation service tests (moto)
│   └── lambdas/
│       ├── test_eval_runner.py            # Eval runner Lambda tests
│       ├── test_rag_evaluator.py          # RAG evaluator tests
│       ├── test_pca.py                    # PCA runner tests
│       ├── test_eval_pipeline.py          # Full eval pipeline integration tests
│       └── test_golden_dataset_runner.py  # Golden dataset tests
│
├── .github/                                # GitHub configuration
│   ├── workflows/ci.yml                    # CI: lint (ruff) → test (pytest) → build (Docker)
│   ├── ISSUE_TEMPLATE/                     # Bug report, feature request, question templates
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── dependabot.yml                      # Automated dependency updates
│
├── docs/                                   # Documentation
│   ├── screenshots/                        # UI screenshots for docs
│   ├── architecture/                       # Architecture diagrams
│   ├── end-to-end-architecture.md          # Detailed architecture walkthrough
│   └── linkedin-article.md                 # This article
│
├── Dockerfile                              # Multi-stage build (Python 3.13-slim, non-root user)
├── docker-compose.yaml                     # Local Qdrant (ports 6333, 6334)
├── pyproject.toml                          # Project metadata + dependencies (uv/pip)
├── makefile                                # Dev commands: run, dev, test, e2e, ingest
├── .env.example                            # Environment variable template
├── CONTRIBUTING.md                         # Contribution guidelines
├── SECURITY.md                             # Vulnerability reporting process
├── CHANGELOG.md                            # Release history
├── CODE_OF_CONDUCT.md
└── LICENSE                                 # MIT
```

---

## Directory Deep Dive

### `src/` — FastAPI + LangGraph Application

The core backend. Entry point is `src/main.py` which mounts two routers:

- **`api/routes.py`** — The `/api/chat` endpoint that invokes the LangGraph pipeline. Handles session state detection (blocks AI when `hitl_pending`), invokes the graph, and returns the response with route metadata, latency, and token counts.
- **`api/dashboard.py`** — All operator-facing endpoints: conversations, evaluations, metrics summary, HITL queue operations (respond, resolve, approve), ingestion (upload, start, status, docs, delete), and golden query CRUD.

The **`graph/builder.py`** wires the state machine:
```
intent → (conditional) → general | tools | escalate | approval_required
```

The **`nodes/`** directory contains one file per graph node. Each node is decorated with `@observe()` for Langfuse tracing and writes cost records to DynamoDB after each LLM call.

The **`services/`** layer abstracts all external integrations:
- `bedrock.py` — AWS Bedrock client (converse API, structured output with JSON schema, LangChain agent invocation)
- `conversation.py` — DynamoDB operations for the conversations and HITL tables
- `embedding.py` — Titan Embed v2 with chunking and exponential backoff
- `qdrant.py` — Vector store operations (create collection, upsert, search, list docs, delete by doc_id)
- `prompt.py` — Langfuse prompt fetching with version pinning and hardcoded fallbacks
- `s3.py` — S3 document reader (PDF via pypdf, CSV)

### `evaluations/` — Lambda Handlers

Three Lambda functions that run asynchronously:

| Lambda | Trigger | What it does |
|--------|---------|--------------|
| `eval_runner.py` | Invoked by `qdrant_ingestion` after ingest completes | Runs golden queries against Qdrant, computes RAG score + LLM judge (faithfulness, relevance), flags low-quality sessions for HITL |
| `rag_evaluator.py` | Called by `eval_runner` | Core evaluation logic: embed query, search Qdrant, compute cosine sim, call Bedrock structured output for faithfulness/relevance scoring |
| `pca.py` | EventBridge every 15 min | Scans stale sessions, extracts topics/sentiment/unresolved via Bedrock structured output, raises degradation alerts |

### `data/` — Knowledge Base + Ingestion Lambda

- **`qdrant_ingestion.py`** — Lambda triggered by SQS (S3 ObjectCreated events). Extracts `job_id` from the S3 key path, URL-decodes keys, chunks documents, embeds via Titan, upserts to Qdrant, updates job status in DynamoDB, and async-invokes `eval_runner` on completion.
- **`csv/`** — Financial data: company profiles, financials summary, segment revenue for Apple, Google, Microsoft.
- **`pdfs/`** — Annual reports (10-K filings) and news articles used as the RAG knowledge base.

### `iac/` — Infrastructure as Code

Five independent Terraform stacks with S3 remote backend. The `iac/Makefile` provides orchestrated targets:

```bash
# Apply a single stack
make apply ENV=dev STACK=evaluations

# Apply all stacks in dependency order
make apply-all ENV=dev

# Plan without applying
make plan ENV=dev STACK=app
```

State is stored in S3 (`llmops-langgraph-terraform` bucket) keyed by `{env}/{stack}/terraform.tfstate`. Each stack uses per-environment tfvars from `iac/envs/{env}/`.

| Stack | Key resources |
|-------|---------------|
| `data` | 3 DynamoDB tables (conversations, evaluations, hitl_queue) with GSIs + S3 documents bucket |
| `security` | Secrets Manager entries for API keys, Langfuse credentials, Qdrant API key |
| `evaluations` | 3 Lambda functions + SQS queue + S3→SQS event notification + EventBridge cron (pca_runner every 15 min) + IAM execution roles |
| `app` | EC2 instance (Docker host) + ECR repository + IAM roles + user_data.sh bootstrap |
| `monitoring` | CloudWatch dashboard (Lambda metrics, API latency, error rates) + alarms |

### `scripts/` — Automation

| Script | Purpose |
|--------|---------|
| `build_lambda_zip.sh` | Builds Lambda deployment package using Docker (linux/amd64). Installs dependencies with `.dist-info` metadata. Outputs `iac/dist/lambdas.zip` |
| `deploy.sh` | Full deployment: builds Docker image, pushes to ECR, applies Terraform stacks |
| `local_e2e_test.sh` | Runs end-to-end tests locally (requires AWS credentials + Docker running) |

### `tests/` — Test Suite

Tests use `pytest` with `moto` for DynamoDB mocking and standard mocks for Bedrock:

| Directory | Coverage |
|-----------|----------|
| `tests/api/` | Dashboard endpoint tests (FastAPI TestClient) |
| `tests/services/` | Conversation service DynamoDB operations |
| `tests/lambdas/` | Eval runner, RAG evaluator, PCA, golden dataset, full pipeline integration |

Run with:
```bash
make test                    # quick run
uv run pytest tests/ --cov=src --cov=evaluations --cov-report=term-missing  # with coverage
```

### `dashboard/` — Next.js Frontends

Two independent Next.js apps, both with dark mode support via ThemeProvider:

**`realtime-monitoring/`** (port 3000) — Operator dashboard with 5 pages: Overview, RAG Evals, PCA, HITL Queue, Ingestion. Polls the backend at configurable intervals (3–30s depending on the page).

**`ai-interface/`** (port 3001) — Customer-facing chat. Adapts UI state based on session status (active → normal chat, hitl_pending → human-only mode, approval_pending → input disabled).

### `.github/` — CI/CD + Community

- **`workflows/ci.yml`** — Three-job pipeline: Lint (ruff) → Test (pytest) → Build (Docker image). Runs on push to `main` and `feature/**` branches, and on PRs to `main`.
- **`ISSUE_TEMPLATE/`** — Bug report, feature request, and question templates.
- **`PULL_REQUEST_TEMPLATE.md`** — PR checklist (description, testing, breaking changes).
- **`dependabot.yml`** — Automated dependency update PRs.

### Root Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build: builder (uv sync) → runtime (Python 3.13-slim, non-root `appuser`, healthcheck) |
| `docker-compose.yaml` | Local Qdrant instance (ports 6333/6334, persistent volume) |
| `pyproject.toml` | Project metadata, dependencies (boto3, fastapi, langchain, langgraph, langfuse, qdrant-client, etc.), dev tools (ruff, pytest, moto), coverage config |
| `makefile` | Dev shortcuts: `make run`, `make dev`, `make test`, `make e2e`, `make ingest` |
| `.env.example` | Template for all environment variables |

---

## The Request Pipeline: LangGraph with Intent Routing

Every customer message enters through the `intent` node, which calls Claude Haiku via structured output (a JSON schema, not free-text parsing) to classify the query into one of four routes:

### Intent classes

| Intent              | Route               | Description                                            |
|---------------------|---------------------|--------------------------------------------------------|
| `general`           | `general`           | Purely conversational, no retrieval needed.            |
| `tools`             | `tools`             | Requires semantic document search via Qdrant.          |
| `escalate`          | `escalate`          | Ambiguous / low-confidence → human takeover.           |
| `approval_required` | `approval_required` | Sensitive actions needing supervisor approval.         |

This means the system is not a monolithic prompt. Each path has its own node, its own prompt, its own cost profile, and its own observable trace in Langfuse.

```python
class Intent(Enum):
    GENERAL = "general"
    TOOLS = "tools"
    ESCALATE = "escalate"
    APPROVAL_REQUIRED = "approval_required"
```

Each node is decorated with `@observe()` so that Langfuse records spans for the node and any nested LangChain tools.

### Implementation

- Graph definition: [`src/graph/builder.py`](../src/graph/builder.py) — defines nodes and edges
- State schema: [`src/states/config.py`](../src/states/config.py) — conversation/session state including route, flags, metadata
- Intent classifier: [`src/nodes/intent.py`](../src/nodes/intent.py) — structured JSON output via Bedrock
- General node: [`src/nodes/general.py`](../src/nodes/general.py) — direct LLM response
- Tools node: [`src/nodes/tools.py`](../src/nodes/tools.py) — LangChain agent with Qdrant
- Escalation node: [`src/nodes/hitl_escalate.py`](../src/nodes/hitl_escalate.py)
- Approval node: [`src/nodes/approval_gate.py`](../src/nodes/approval_gate.py)

![AI Interface — General and RAG routing in action](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/ai-interface2.png)

---

## RAG: Not Just Retrieval, But Evaluation

The `tools` node does more than search. When a query arrives:

1. Embeds the query using AWS Bedrock Titan Embed Text v2 (256 dimensions)
2. Performs cosine similarity search in Qdrant (top_k = 5)
3. Computes a **RAG score** — the max dot product between the query embedding and the retrieved document embeddings
4. If RAG score < 0.6, re-retrieves with top_k doubled
5. If still < 0.6 after re-retrieval, auto-flags the session for HITL review
6. The LangChain agent synthesizes a response using the retrieved chunks, with source snippets and scores returned to the UI

### RAG evaluation metrics

| Metric       | Source                   | What it measures                            |
|--------------|--------------------------|---------------------------------------------|
| RAG score    | Cosine similarity in Qdrant | Quality of retrieval (right chunks?)     |
| Faithfulness | LLM-as-judge (Bedrock)   | Is the answer grounded in retrieved text?   |
| Relevance    | LLM-as-judge (Bedrock)   | Does the answer address the question?       |

You can tune `RAG_THRESHOLD`, `HITL_THRESHOLD`, and `top_k` via environment variables (see [`src/setting/config.py`](../src/setting/config.py)).

### Implementation

- RAG tool: [`src/tools/rag.py`](../src/tools/rag.py) — `semantic_document_search` LangChain tool
- Qdrant service: [`src/services/qdrant.py`](../src/services/qdrant.py) — collection, upsert, semantic search
- Embedding service: [`src/services/embedding.py`](../src/services/embedding.py) — Titan Embed v2 with retry backoff
- Bedrock service: [`src/services/bedrock.py`](../src/services/bedrock.py) — converse, structured output, agent

---

## Evaluation Pipeline: Continuous Quality Monitoring

Demos skip this part. Production systems can't.

After every document ingest, the `eval_runner` Lambda is invoked asynchronously. It runs each "golden query" — test questions you define in the dashboard — against the freshly updated Qdrant index and records RAG score, faithfulness, and relevance per query.

These results appear in the RAG Evals dashboard, which refreshes every 15 seconds. You can add, edit, or delete golden queries from the UI — no code change, no redeployment.

![RAG Evaluations — Golden queries with per-question scores](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/evals.png)

### How to extend

Add new golden queries from the monitoring dashboard's **RAG Evals** page; they are persisted in DynamoDB and picked up by the runner automatically. To add a new eval metric, extend the evaluator in `evaluations/rag_evaluator.py`.

### Implementation

- RAG evaluator: [`evaluations/rag_evaluator.py`](../evaluations/rag_evaluator.py) — golden queries → cosine sim + LLM judge
- Eval runner: [`evaluations/eval_runner.py`](../evaluations/eval_runner.py) — Lambda entry point
- Terraform: [`iac/stacks/evaluations/`](../iac/stacks/evaluations/) — Lambda, SQS queue, EventBridge schedule
- DynamoDB table: `evaluations` with GSI `eval_type-created_at`

---

## Post-Conversation Analysis (PCA)

Every 15 minutes, the `pca_runner` Lambda scans for sessions idle for ≥ 15 minutes and extracts:

- **Topics** discussed
- **Sentiment** (positive / neutral / negative)
- **Unresolved questions** — things the customer asked that the AI couldn't answer

If negative sentiment reaches 60% or average unresolved questions per session reaches 3, the system raises a degradation alert and automatically creates a HITL item for review.

![Post-Conversation Analysis — Topics, sentiment, and unresolved questions](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/pca.png)
![PCA continued — Unresolved questions list](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/pca2.png)

### Implementation

- PCA runner: [`evaluations/pca.py`](../evaluations/pca.py) — post-conversation analysis
- EventBridge rule: `iac/stacks/evaluations/eventbridge.tf` — schedule every 15 minutes
- The monitoring dashboard's PCA page pulls from the same DynamoDB table

---

## Human-in-the-Loop (HITL)

The HITL system handles two distinct situations:

### Data model

- DynamoDB table `hitl_queue` with key schema `pk=HITL` / `sk=timestamp#session_id`
- GSI on `queue_status` for filtering pending vs resolved items
- HITL items track `hitl_type` (escalation or approval), session context, and resolution

### Mode 1: Escalation (mid-conversation handoff)

When a query is classified as `escalate` — or when the eval pipeline flags a session for low RAG quality — the session is marked `hitl_pending`:

- Customer UI switches into human-only mode; messages bypass AI entirely
- A blue banner appears: "Connected to a human agent — type below to reply."
- Operator uses the HITL Queue page to pick up, respond (multi-turn), and resolve items
- On resolve, session returns to `active` and AI processing resumes

The risk classifier lives in the `intent` node — it uses the same structured output call that routes queries.

![HITL Queue — Pending escalations and resolved items](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/hitl.png)
![HITL Queue — Live conversation thread with human agent response](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/hitl2.png)

### Mode 2: Approval Gate (pre-action supervisor sign-off)

Sensitive actions (`approval_required`) create approval items with risk badges (low / medium / high) and supervisor Approve/Reject controls. Approvals write a human turn into the conversation, then resume AI.

![Approval Gate — User sees "Awaiting supervisor approval" with disabled input](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/ai-interface3.png)
![Approval Gate — Supervisor Approve/Reject view in HITL Queue](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/hitl3.png)
![Approval Gate — Approval item with action details and risk badge](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/hitl4.png)
![Approval Gate — Multi-item pending queue with escalation and approval](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/hitl5.png)
![Approval Gate — User sees approval confirmation from human agent](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/ai-interface4.png)

### Implementation

- HITL escalation node: [`src/nodes/hitl_escalate.py`](../src/nodes/hitl_escalate.py)
- Approval gate node: [`src/nodes/approval_gate.py`](../src/nodes/approval_gate.py)
- Conversation service: [`src/services/conversation.py`](../src/services/conversation.py) — DynamoDB + HITL queue operations
- Dashboard API routes: [`src/api/dashboard.py`](../src/api/dashboard.py) — `/api/hitl/*` endpoints
- HITL Queue UI: [`dashboard/realtime-monitoring/src/app/hitl/page.tsx`](../dashboard/realtime-monitoring/src/app/hitl/page.tsx)

---

## The Monitoring Dashboard

The monitoring app (Next.js, port 3000) communicates with the backend via:

| Endpoint | Returns |
|----------|---------|
| `/api/metrics/summary` | Avg RAG score, Avg Faithfulness, Cost Today, HITL pending count |
| `/api/evaluations` | RAG eval results per golden query |
| `/api/hitl` | HITL queue operations (list, resolve, approve, reject) |
| `/api/ingestion/docs` | Ingested document list with chunk counts |

### Dashboard pages

| Tab | Description |
|-----|-------------|
| **Overview** | KPI cards (avg RAG score, avg faithfulness, HITL pending, cost today), recent eval table |
| **RAG Evals** | Golden query list with add/edit/delete + latest evaluation results per query |
| **PCA** | Topic distribution, sentiment breakdown, unresolved questions list |
| **HITL Queue** | Pending escalation/approval items with live conversation thread + resolved history |
| **Ingestion** | Upload file or provide S3 key, live job status, ingested documents with cascade-delete |

![Monitoring Dashboard — Overview with KPI cards and recent evaluations](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/overview.png)
![Document Ingestion — Upload form and ingested documents](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/doc.png)
![Document Ingestion — Job history with completion status](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/doc2.png)

### Implementation

- Dashboard app: [`dashboard/realtime-monitoring/`](../dashboard/realtime-monitoring/)
- KPI cards: [`dashboard/realtime-monitoring/src/components/KpiCards.tsx`](../dashboard/realtime-monitoring/src/components/KpiCards.tsx)
- HITL Queue component: [`dashboard/realtime-monitoring/src/components/HitlQueue.tsx`](../dashboard/realtime-monitoring/src/components/HitlQueue.tsx)
- Ingestion panel: [`dashboard/realtime-monitoring/src/components/IngestionPanel.tsx`](../dashboard/realtime-monitoring/src/components/IngestionPanel.tsx)
- API client: [`dashboard/realtime-monitoring/src/lib/api.ts`](../dashboard/realtime-monitoring/src/lib/api.ts)
- CloudWatch Terraform: [`iac/stacks/monitoring/`](../iac/stacks/monitoring/)

---

## The AI Interface

The ai-interface Next.js app (port 3001) is the customer-facing side with a two-pane layout:

**Left sidebar** — Session list showing all conversations with turn count and status badge (active / complete / hitl_pending / approval_pending).

**Main pane** — The chat thread, with each AI response showing:
- A route badge (`GENERAL`, `TOOLS`, `ESCALATED`, or `APPROVAL REQUIRED`)
- Latency in milliseconds and token count
- For TOOLS responses: expandable source documents with text snippets and cosine scores

The interface adapts its state based on session status:
- `hitl_pending` → blue banner, "Reply to human agent…" placeholder, no AI invocation
- `approval_pending` → amber banner, input disabled
- `active` → normal input with "Message LLMOps AI…" placeholder

![AI Interface — Session list and new chat landing](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/ai-interface.png)

### Implementation

- Chat interface: [`dashboard/ai-interface/`](../dashboard/ai-interface/)
- Chat thread: [`dashboard/ai-interface/src/components/ChatThread.tsx`](../dashboard/ai-interface/src/components/ChatThread.tsx)
- Session list: [`dashboard/ai-interface/src/components/SessionList.tsx`](../dashboard/ai-interface/src/components/SessionList.tsx)
- API client: [`dashboard/ai-interface/src/lib/api.ts`](../dashboard/ai-interface/src/lib/api.ts)

---

## Observability with Langfuse

All LLM calls and tool invocations are traced to Langfuse:

- **Root span**: LangGraph graph execution
- **Child spans**: `intent`, `general`, `tools`, `escalate`, `approval_required`
- **Nested spans**: Qdrant searches via LangChain tools, Bedrock eval calls

Prompts (`intent_router`, `general_assistant`, `rag_assistant`) are versioned in Langfuse and fetched at startup. You can update a prompt in Langfuse and the next request picks up the new version — no redeployment required. If Langfuse is unreachable at startup, the app falls back to hardcoded prompts.

![Langfuse Tracing — Full graph execution with nested tool calls and costs](https://raw.githubusercontent.com/gokulnathan66/chat-ops/feature/llmops/docs/screenshots/langfuse.png)

### Implementation

- Prompt service: [`src/services/prompt.py`](../src/services/prompt.py) — Langfuse prompt versioning + fallbacks
- Settings: [`src/setting/config.py`](../src/setting/config.py) — `ENABLE_LANGFUSE` toggle
- Node decorators: all nodes use `@observe()` from Langfuse

---

## Cost Tracking

Per-turn cost is computed using Claude Haiku 4.5 pricing:

- Input: $0.80 per 1M tokens
- Output: $4.00 per 1M tokens

Each response stores:
- Token counts (input, output)
- Cost per turn (`cost_usd`)
- Written as `eval_type=cost` records in the evaluations table

`/api/metrics/summary` aggregates these into the "Cost Today (USD)" KPI shown on the Overview dashboard. Date comparison uses UTC so records always match regardless of server timezone.

---

## Infrastructure: Five Terraform Stacks

| Stack | Path | Manages |
|-------|------|---------|
| `data` | [`iac/stacks/data/`](../iac/stacks/data/) | DynamoDB tables, S3 documents bucket |
| `security` | [`iac/stacks/security/`](../iac/stacks/security/) | Secrets Manager |
| `evaluations` | [`iac/stacks/evaluations/`](../iac/stacks/evaluations/) | Lambda functions, SQS queue, EventBridge schedules |
| `app` | [`iac/stacks/app/`](../iac/stacks/app/) | EC2 instance, ECR repository, IAM roles |
| `monitoring` | [`iac/stacks/monitoring/`](../iac/stacks/monitoring/) | CloudWatch dashboard and alarms |

Cross-stack dependencies are injected via tfvars — no workspace coupling, no shared state files. Each stack can be deployed or updated independently.

---

## Engineering Principles: Clean Code, Clean Deploys

This project was built with a deliberate focus on maintainability, separation of concerns, and reproducible deployments. Here's how that manifests across every layer.

### Clean Code in `src/`

**Single-responsibility nodes.** Each LangGraph node is one file, one function, one job. The `general_node` converses. The `tools_node` retrieves and synthesizes. The `intent_node` classifies. No node knows about another node's internals — they communicate only through the typed `GraphState`:

```python
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

**The graph builder is 25 lines.** No business logic lives in the wiring — it's purely structural:

```python
@observe()
def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("intent", intent_node, ends=["general", "tools", "escalate", "approval_required"])
    builder.add_node("general", general_node)
    builder.add_node("tools", tools_node)
    builder.add_node("escalate", hitl_escalate_node)
    builder.add_node("approval_required", approval_gate_node)
    builder.add_edge(START, "intent")
    builder.add_edge("general", END)
    builder.add_edge("tools", END)
    builder.add_edge("escalate", END)
    builder.add_edge("approval_required", END)
    return builder.compile()
```

**Services abstract all external calls.** No node directly calls boto3, Qdrant, or DynamoDB. Every external integration is behind a service class with explicit error handling and retry logic:

```python
# embedding.py — exponential backoff on transient Bedrock errors
for attempt in range(_MAX_EMBED_RETRIES):
    try:
        response = self._client.invoke_model(...)
        return json.loads(response["body"].read())["embedding"]
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("ThrottlingException", "ServiceUnavailableException"):
            time.sleep(_EMBED_BACKOFF_BASE * (2 ** attempt))
        else:
            raise
```

**Structured output everywhere.** Intent classification, LLM-as-judge evaluation, and PCA extraction all use JSON schema-constrained output — no regex parsing, no string splitting, no "hope the model formats it right":

```python
INTENT_ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["general", "tools", "escalate", "approval_required"]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        ...
    },
    "required": ["intent", "route", "confidence", "reason"],
}
```

**Prompt versioning with graceful fallback.** Every node has a hardcoded `_FALLBACK_SYSTEM_PROMPT`. If Langfuse is down, the system still works. If Langfuse is up, prompts are fetched and versioned remotely. Zero-downtime prompt updates without redeployment.

**Pydantic Settings for configuration.** All 30+ config values flow through a single `Settings` class with typed defaults, `.env` file loading, and environment variable override. No scattered `os.getenv()` calls, no magic strings:

```python
class Settings(BaseSettings):
    MODEL_ID: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    RAG_THRESHOLD: float = 0.6
    HITL_THRESHOLD: float = 0.6
    INACTIVITY_MINUTES: int = 15
    ...
```

### Clean Code in `evaluations/`

Each Lambda handler is a focused module:
- `eval_runner.py` — 30 lines. Receives an event, calls the evaluator, writes results.
- `rag_evaluator.py` — the evaluation logic: embed, search, score, judge. Testable in isolation.
- `pca.py` — scans stale sessions, extracts structured analysis, detects degradation.

No shared mutable state between Lambdas. Each reads from DynamoDB, does its work, writes back. Idempotent by design.

### Clean Terraform in `iac/`

**Five independent stacks, zero coupling.** Each stack has its own `main.tf`, `variables.tf`, `outputs.tf`, and remote state. You can `terraform destroy` the monitoring stack without touching data or app. You can redeploy evaluations without restarting the API.

**Consistent naming convention.** Every resource uses `${var.project}-${var.env}-` prefix:

```hcl
resource "aws_dynamodb_table" "conversations" {
  name = "${var.project}-${var.env}-${var.conversations_table}"
  ...
  tags = {
    Environment = var.env
    Project     = var.project
  }
}
```

**Cross-stack values via tfvars, not data sources.** Stacks don't read each other's remote state. The Makefile injects values from `iac/envs/{env}/` — explicit, auditable, no hidden dependencies.

**Makefile-orchestrated deploys.** One command applies everything in the right order:

```bash
make apply-all ENV=dev    # data → security → evaluations → app → monitoring
```

Or target a single stack:

```bash
make apply ENV=dev STACK=evaluations
```

The Makefile handles `terraform init` with the correct backend config, var-file selection, and state key — developers never need to remember bucket names or key paths.

**EventBridge schedules are parameterized.** Cron expressions come from tfvars, not hardcoded in `.tf` files. Changing PCA frequency from 15 min to 5 min is a one-line tfvars change, not a code change.

### Clean Deployment Pipeline

**Multi-stage Dockerfile.** Builder stage installs dependencies with `uv sync --frozen --no-dev`. Runtime stage copies only the venv and source — no build tools, no dev dependencies, no package manager in the final image. Non-root `appuser`. Built-in healthcheck.

**Lambda zip built in Docker.** `scripts/build_lambda_zip.sh` uses a `linux/amd64` Docker container to install dependencies — guaranteeing the zip works on Lambda's runtime regardless of the developer's OS (macOS ARM, Linux x86, etc.).

**CI pipeline gates deployment.** The GitHub Actions workflow enforces: lint (ruff) → test (pytest) → build (Docker) — in that order. A formatting issue blocks tests. A test failure blocks the image build. No broken code reaches ECR.

**EC2 bootstrap via user_data.sh.** The instance pulls secrets from Secrets Manager, writes `.env`, pulls the latest image from ECR, and starts the container. No SSH, no manual config, no snowflake servers. Terminate and recreate for a clean deploy.

### The Result

Every file has one job. Every service has explicit error handling. Every Terraform resource is tagged and parameterized. Every deploy is reproducible from a single command. The codebase reads top-to-bottom without needing tribal knowledge — a new contributor can trace a request from `POST /api/chat` through the graph to DynamoDB in under 5 minutes by following the imports.

---

## What I Learned

**Structure your evals before you ship.** The golden query framework only works if you've thought about what "good" looks like before going to production. Add your test questions when you first set up the system, not after you notice it's wrong.

**HITL is not a fallback — it's a feature.** The most useful insight from building this is that the escalation path is part of the product. An AI that knows when to hand off is more trustworthy than one that confidently answers everything.

**Structured output changes everything.** Using JSON schema-constrained output for intent classification, LLM judging, and PCA extraction means you're working with typed data, not parsing free text. The reliability difference is significant.

**Observability at the node level, not just the request level.** Tracing the full LangGraph execution — including nested LangChain tool calls — gives you a completely different debugging experience than logging the final response.

---

## Roadmap

Planned or suggested next steps:

- **Answer correctness evaluator** — score generated answers against ground-truth answers, not just retrieved chunks
- **Team-based HITL routing** — route escalations to the right team (finance vs support), with per-queue SLAs and prioritization
- **End-to-end task success metrics** — measure whether the user's actual goal was achieved, beyond RAG/faithfulness scores
- **Streaming responses** — SSE/WebSocket streaming to improve perceived latency
- **Export/import for golden queries** — bulk management of eval datasets

---

## Development and Contributing

### Local dev

- Use `uv` to manage Python dependencies and virtualenv
- Run `ruff check .` and `ruff format .` before opening a PR
- Use Docker for Qdrant locally if not connecting to a remote instance

### Tests

```bash
make test                    # unit tests (moto for DynamoDB, mocks for Bedrock)
make e2e                     # full local E2E (requires AWS credentials + Docker)
uv run pytest tests/ --cov=src --cov=evaluations --cov-report=term-missing
```

### Pull requests

- Follow Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `infra:`
- Branch names like `feat/short-description` or `infra/evaluations-stack`

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for full guidelines.

To discuss the eval pipeline, the HITL architecture, or the LangGraph routing patterns — [open an issue](https://github.com/gokulnathan66/llmops/issues) or [start a discussion](https://github.com/gokulnathan66/llmops/discussions).

---

## License

MIT — see [`LICENSE`](../LICENSE).
