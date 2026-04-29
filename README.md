# LLMOps — End-to-End RAG Application

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/gokulnathan66/llmops/actions/workflows/ci.yml/badge.svg)](https://github.com/gokulnathan66/llmops/actions/workflows/ci.yml)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

A production-grade LangGraph RAG API with full LLMOps tooling: observability, prompt versioning, evaluation pipelines, HITL, real-time monitoring, and one-command infrastructure.

---

## Architecture Overview

```
POST /api/chat
  → Intent Node  (Bedrock structured output → "general" | "tools")
  → Router
      ├── General Node  → converse() → response
      └── Tools Node    → LangChain agent + semantic_document_search (Qdrant) → response
  → DynamoDB (conversation turn written)
  → Langfuse (trace flushed)
```

### Stack

| Layer | Technology |
|---|---|
| API | FastAPI + LangGraph |
| LLM | AWS Bedrock (Claude Haiku — `anthropic.claude-3-haiku-20240307-v1:0`) |
| Vector store | Qdrant |
| Embeddings | AWS Bedrock Titan Embed Text v2 (256-dim) |
| Observability | Langfuse (traces + prompt versioning) |
| Data store | DynamoDB (conversations, evaluations, HITL, golden results) |
| Document storage | S3 |
| Ingestion | SQS → Lambda → Qdrant |
| Evaluation | Lambda (eval_runner, golden_dataset_runner, pca_runner) |
| Infrastructure | Terraform (ap-south-1), Docker, ECR, EC2 |

---

## Project Structure

```
llmops/
├── src/                                    # API + LangGraph application
│   ├── main.py                             # FastAPI app entry point
│   ├── api/
│   │   ├── routes.py                       # POST /api/chat endpoint
│   │   └── dashboard.py                    # Dashboard + HITL REST endpoints
│   ├── graph/
│   │   └── builder.py                      # LangGraph state machine (3 nodes)
│   ├── nodes/
│   │   ├── intent.py                       # Intent router → "general" | "tools"
│   │   ├── general.py                      # Direct LLM response node
│   │   └── tools.py                        # RAG agent node (LangChain + Qdrant)
│   ├── services/
│   │   ├── bedrock.py                      # Bedrock: converse, structured output, agent
│   │   ├── conversation.py                 # DynamoDB: turns, metadata, HITL queue
│   │   ├── embedding.py                    # Titan Embed v2 via Bedrock + chunking
│   │   ├── prompt.py                       # Langfuse prompt versioning + fallbacks
│   │   ├── qdrant.py                       # Qdrant: collection, upsert, semantic search
│   │   ├── s3.py                           # S3: PDF + CSV document reader
│   │   └── mcp.py                          # MCP server client
│   ├── tools/
│   │   └── rag.py                          # semantic_document_search LangChain tool
│   ├── schema/
│   │   └── config.py                       # Pydantic request/response models
│   ├── states/
│   │   └── config.py                       # GraphState TypedDict
│   └── setting/
│       └── config.py                       # Pydantic Settings (env-based config)
│
├── evaluations/                            # Evaluation pipeline (Lambda handlers)
│   ├── rag_evaluator.py                    # Cosine sim + LLM judge (faithfulness, relevance)
│   ├── eval_runner.py                      # Stale session detection + eval orchestration
│   ├── golden_dataset_runner.py            # Golden Q&A regression runner
│   └── pca.py                              # Post-conversation analysis (topics, sentiment)
│
├── data/                                   # Knowledge base + evaluation data
│   ├── golden.json                         # 15 Q&A pairs (Apple, Google, Microsoft)
│   ├── qdrant_ingestion.py                 # Local ingestion script (S3 event format)
│   ├── csv/
│   │   ├── big_tech_company_profiles.csv
│   │   ├── big_tech_financials_summary.csv
│   │   └── big_tech_segment_revenue.csv
│   └── pdfs/
│       ├── annual_reports/                 # Apple, Google, Microsoft 10-K 2025
│       └── news_articles/                  # AI features, cloud growth, advertising
│
├── dashboard/                              # Next.js frontend applications
│   ├── realtime-monitoring/                # Monitoring dashboard (port 3000)
│   │   └── src/app/
│   │       ├── page.tsx                    # Overview: KPI cards, eval table, PCA strip
│   │       ├── evals/page.tsx              # RAG + faithfulness scores per session
│   │       ├── golden/page.tsx             # Golden dataset pass rate + per-question breakdown
│   │       └── pca/page.tsx                # Topic distribution, sentiment, unresolved questions
│   └── ai-interface/                       # Chat + HITL interface (port 3001)
│       └── src/
│           ├── app/
│           │   ├── page.tsx                # Chat interface
│           │   ├── hitl/page.tsx           # HITL queue review + human response
│           │   └── ingestion/page.tsx      # Document ingestion trigger
│           ├── components/
│           │   ├── ChatThread.tsx
│           │   ├── HitlQueue.tsx
│           │   ├── IngestionPanel.tsx
│           │   └── SessionList.tsx
│           └── lib/api.ts                  # API client (calls FastAPI backend)
│
├── iac/terraform-aws/                      # Infrastructure as Code (ap-south-1)
│   ├── main.tf                             # Provider, S3 backend, documents bucket
│   ├── ec2.tf                              # API server (t3.medium, ECR pull on boot)
│   ├── ecr.tf                              # Docker image registry
│   ├── sqs.tf                              # Ingestion queue + qdrant_ingestion Lambda
│   ├── lambda.tf                           # eval_runner, golden_dataset_runner, pca_runner
│   ├── event_bridge.tf                     # EventBridge cron schedules
│   ├── cloudwatch.tf                       # Log groups + error alarms
│   ├── iam.tf                              # Lambda + EC2 IAM roles and policies
│   ├── secrets.tf                          # Secrets Manager (all env vars)
│   ├── variables.tf                        # All input variables
│   ├── outputs.tf                          # EC2 IP, ECR URL, SQS ARN, etc.
│   ├── user_data.sh                        # EC2 bootstrap: Docker install + ECR pull
│   ├── terraform.tfvars.example            # Example variable values
│   ├── data_managment/                     # Module: 4 DynamoDB tables
│   │   ├── dynamodb.tf
│   │   ├── main.tf                         # S3 backend: data/terraform.tfstate
│   │   ├── outputs.tf
│   │   └── variables.tf
│   ├── evaluations/                        # Module: eval Lambdas + EventBridge
│   │   ├── lambda.tf
│   │   ├── eventbridge.tf
│   │   ├── iam.tf
│   │   ├── main.tf                         # S3 backend: evaluations/terraform.tfstate
│   │   ├── outputs.tf
│   │   └── variables.tf
│   ├── monitoring/                         # Module: CloudWatch dashboard + alarms
│   │   ├── cloudwatch.tf
│   │   ├── main.tf                         # S3 backend: monitoring/terraform.tfstate
│   │   └── variables.tf
│   └── security/                           # Module: Secrets Manager
│       ├── secrets.tf
│       ├── main.tf                         # S3 backend: security/terraform.tfstate
│       ├── outputs.tf
│       └── variables.tf
│
├── tests/                                  # Test suite (34 tests, moto for DynamoDB)
│   ├── api/
│   │   └── test_dashboard.py               # Dashboard endpoint tests
│   ├── lambdas/
│   │   ├── test_eval_pipeline.py           # Integration: full eval pipeline
│   │   ├── test_eval_runner.py
│   │   ├── test_golden_dataset_runner.py
│   │   ├── test_pca.py
│   │   └── test_rag_evaluator.py
│   └── services/
│       └── test_conversation.py            # DynamoDB conversation service
│
├── docs/
│   └── architecture.md                     # Request flow, eval pipeline, DynamoDB schema
│
├── scripts/
│   ├── deploy.sh                           # Full Terraform + Docker build/push pipeline
│   └── local_e2e_test.sh                   # 13-section local E2E test (38 checks)
│
├── .github/
│   ├── workflows/ci.yml                    # CI: lint → test → docker build
│   ├── dependabot.yml                      # Weekly pip + github-actions updates
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── ISSUE_TEMPLATE/                     # bug_report, feature_request, question, config
│
├── Dockerfile                              # Multi-stage build, non-root user, HEALTHCHECK
├── docker-compose.yaml                     # Local Qdrant (port 6333)
├── pyproject.toml                          # v0.2.0, ruff + pytest config
├── makefile                                # dev, run, test, e2e, ingest
├── .env.example                            # All env vars with values redacted
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── LICENSE
├── README.md
└── SECURITY.md
```

---

## Features

### Observability — Langfuse
- Every graph execution is wrapped with `@observe()` — intent, general, and tools nodes all emit traces
- Traces are linked per `session_id` for full conversation replay in the Langfuse UI
- Toggled by `ENABLE_LANGFUSE=true`

### Prompt Versioning — Langfuse
Prompts are managed via `src/services/prompt.py`. Three versioned prompts:

| Prompt name | Used by | Purpose |
|---|---|---|
| `rag_assistant` | tools node | Financial analyst persona; instructs tool use and source citation |
| `general_assistant` | general node | Conversational assistant; defers data questions to document search |
| `intent_router` | intent node | Routes queries to `tools` (financial data) or `general` (chat) |

Prompts are fetched from Langfuse at startup (with local fallbacks if Langfuse is unreachable). Edit and version them in the Langfuse UI without redeploying.

### Data Management — DynamoDB
Four tables managed by the `data_managment/` Terraform module:

| Table | Key schema | Purpose |
|---|---|---|
| `conversations` | `session_id` / `sk` (turn#NNN or metadata) | Every chat turn + session metadata |
| `evaluations` | `session_id` / `sk` (eval#rag#ts or eval#pca#ts) | RAG scores and PCA results per session |
| `hitl_queue` | `pk=HITL` / `sk=timestamp#session_id` | Sessions flagged for human review |
| `golden_results` | `run_id` / `question_id` | Golden dataset evaluation run history |

Conversations have a GSI on `status` + `last_updated_at` for efficient stale-session queries.

### RAG Pipeline
- Documents (PDF, TXT, CSV) uploaded to S3 → SQS message → `qdrant_ingestion` Lambda
- Lambda chunks text, embeds with **AWS Bedrock Titan Embed Text v2**, upserts to Qdrant
- `semantic_document_search` tool performs cosine similarity search at query time
- Knowledge base: Apple, Google/Alphabet, Microsoft 2025 annual reports and news articles

### Evaluation

#### RAG Evaluator (`eval_runner` — every 15 min)
1. Finds sessions inactive for `INACTIVITY_MINUTES` (default 15)
2. Marks them complete
3. For each RAG turn: computes cosine similarity (query embedding vs doc embeddings) and LLM-as-judge faithfulness/relevance scores
4. If RAG score < `RAG_THRESHOLD` (0.6): re-retrieves with top-k × 2
5. If still < `HITL_THRESHOLD` (0.6): flags session → writes to `hitl_queue` table

#### Golden Dataset Runner (`golden_dataset_runner` — every hour)
- Loads `golden.json` from S3 (15 Q&A pairs covering Apple, Google, Microsoft)
- For each question: retrieves docs, generates answer, LLM-judges faithfulness + relevance
- Writes pass/fail per question to `golden_results` table
- Pass threshold: `GOLDEN_PASS_THRESHOLD` (0.7)

#### Post-Conversation Analyzer (`pca_runner` — every 15 min)
- Analyzes completed conversations with LLM-as-judge
- Extracts: main topics, overall user sentiment (positive/neutral/negative), unresolved questions
- Writes to `evaluations` table with `eval_type=pca`

### HITL — Human-in-the-Loop
- Sessions with low RAG scores after re-retrieval are automatically written to `hitl_queue`
- Dashboard at `dashboard/realtime-monitoring` shows pending HITL items
- Human resolves via `conversation_service.resolve_hitl(queue_id, human_response)`

### Real-Time Monitoring Dashboard
Next.js app at `dashboard/realtime-monitoring` (port 3000):
- **Overview** — KPI cards (avg RAG score, HITL pending, golden pass rate, cost today), recent eval table, PCA sentiment strip
- **Evaluations** — session-level RAG score, faithfulness, relevance, HITL flag status
- **Golden Dataset** — pass rate per run, per-question breakdown with expected vs generated answers
- **PCA** — topic distribution, sentiment over time, unresolved question list

### AI Interface + HITL Dashboard
Next.js app at `dashboard/ai-interface` (port 3001):
- **Chat** — send queries, view intent routing, retrieved docs, and LLM responses in real time
- **HITL Queue** — review flagged sessions, read conversation summary, submit human responses
- **Ingestion** — trigger document ingestion by S3 key via the `/api/ingestion/start` endpoint
- **Session List** — browse active/complete sessions, drill into individual turns

---

## API Reference

All endpoints are served by the FastAPI backend at `http://localhost:8000`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/chat` | Send a query through the LangGraph pipeline |
| `GET` | `/api/conversations` | List conversations by status (`active`/`complete`) |
| `GET` | `/api/conversations/{session_id}` | Get all turns + metadata for a session |
| `GET` | `/api/evaluations` | List eval records by type (`rag`/`pca`) |
| `GET` | `/api/metrics/summary` | Aggregate KPIs (avg RAG, HITL count, golden pass rate) |
| `GET` | `/api/hitl` | List HITL queue items by status |
| `POST` | `/api/hitl` | Manually create a HITL queue item |
| `POST` | `/api/hitl/{queue_id}/respond` | Submit human response to a HITL item |
| `GET` | `/api/golden-results` | List golden dataset run results |
| `POST` | `/api/ingestion/start` | Trigger async document ingestion by S3 key |

---

## Quick Start

### 1. Backend API

```bash
# Install dependencies
uv sync

# Start Qdrant locally
docker compose up -d

# Copy and fill environment variables
cp .env.example .env
# Edit .env — set AWS_REGION, MODEL_ID, Langfuse keys

# Ingest knowledge base into Qdrant
make ingest

# Run with hot reload
make dev
```

Health check: `GET http://localhost:8000/health`

### 2. Monitoring Dashboard

```bash
cd dashboard/realtime-monitoring
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev   # http://localhost:3000
```

### 3. AI Interface + HITL Dashboard

```bash
cd dashboard/ai-interface
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev   # http://localhost:3001
```

### Ingest documents

Upload PDFs or text files to S3 — the SQS trigger will invoke `qdrant_ingestion` automatically.

To upload the bundled data locally:

```bash
uv run python data/qdrant_ingestion.py
```

### Chat

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "What was Apple revenue in fiscal year 2025?",
    "session_id": "session-001",
    "turn": 1,
    "messages": [],
    "message": ""
  }'
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `MODEL_ID` | `anthropic.claude-3-haiku-20240307-v1:0` | AWS Bedrock model ID or inference profile |
| `AWS_REGION` | `ap-south-1` | AWS region |
| `QDRANT_HOST` | `http://localhost:6333` | Qdrant URL |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `QDRANT_API_KEY` | — | Qdrant API key (empty for local) |
| `QDRANT_COLLECTION` | `llmops` | Qdrant collection name |
| `S3_BUCKET_NAME` | — | Document storage bucket |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | — | Langfuse secret key |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse host |
| `ENABLE_LANGFUSE` | `false` | Enable Langfuse tracing + prompt versioning |
| `CONVERSATIONS_TABLE` | `conversations` | DynamoDB table |
| `EVALUATIONS_TABLE` | `evaluations` | DynamoDB table |
| `HITL_TABLE` | `hitl_queue` | DynamoDB table |
| `GOLDEN_RESULTS_TABLE` | `golden_results` | DynamoDB table |
| `RAG_THRESHOLD` | `0.6` | Score below which re-retrieval is triggered |
| `HITL_THRESHOLD` | `0.6` | Score below which HITL is triggered |
| `INACTIVITY_MINUTES` | `15` | Session inactivity window for eval |
| `GOLDEN_PASS_THRESHOLD` | `0.7` | Minimum LLM judge score to pass |

---

## Infrastructure

All infrastructure is in `iac/terraform-aws/`, deployed to `ap-south-1`.

### Deploy (one command)

```bash
cd iac/terraform-aws
cp terraform.tfvars.example terraform.tfvars
# fill in terraform.tfvars with your values

terraform init
terraform apply
```

After apply, push the Docker image using the printed `ecr_push_commands` output:

```bash
terraform output -raw ecr_push_commands | bash
```

### Terraform Modules

Each subdirectory is a standalone module with its own S3 backend state. Apply them independently or via `scripts/deploy.sh`:

| Module | State key | Manages |
|---|---|---|
| root | `app/terraform.tfstate` | EC2, ECR, SQS, Lambda, IAM, EventBridge, Secrets, CloudWatch |
| `data_managment/` | `data/terraform.tfstate` | DynamoDB tables |
| `evaluations/` | `evaluations/terraform.tfstate` | Eval Lambdas + EventBridge schedules |
| `monitoring/` | `monitoring/terraform.tfstate` | CloudWatch dashboard + alarms |
| `security/` | `security/terraform.tfstate` | Secrets Manager |

State bucket: `llmops-terraform-state-<account_id>` (created automatically by `scripts/deploy.sh`, or manually: `aws s3 mb s3://llmops-terraform-state-$(aws sts get-caller-identity --query Account --output text) --region ap-south-1`).

### Key Outputs

```bash
terraform output api_endpoint        # http://<ec2-ip>:8000
terraform output ecr_repository_url  # ECR push/pull URL
terraform output s3_documents_bucket # S3 bucket for document uploads
terraform output sqs_ingestion_url   # SQS queue for manual ingestion trigger
```

---

## Data

### `data/golden.json`
15 curated Q&A pairs used by `golden_dataset_runner` to regression-test RAG quality:
- **Apple**: total revenue, Services segment growth, Apple Intelligence (iOS 18), iPhone performance, gross margin
- **Alphabet/Google**: total revenue, Google Cloud growth, Gemini AI strategy, advertising revenue, operating margin
- **Microsoft**: total revenue, Azure growth rate, Microsoft 365 Copilot, Intelligent Cloud segment, AI capex

### `data/pdfs/`
- `annual_reports/` — Apple, Google/Alphabet, Microsoft 10-K 2025
- `news_articles/` — AI features, cloud growth, advertising trends

### `data/csv/`
- `big_tech_company_profiles.csv`
- `big_tech_financials_summary.csv`
- `big_tech_segment_revenue.csv`

---

## Testing

```bash
# Unit tests (moto for DynamoDB, mocks for Bedrock)
make test

# Full local E2E (requires AWS credentials + Docker)
make e2e

# With coverage
uv run pytest tests/ --cov=src --cov=evaluations --cov-report=term-missing
```

---

## Development

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Ingest local CSV data into Qdrant
make ingest
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions, code standards, branch naming, and PR process.

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability reporting process. Do not open public issues for security bugs.

## License

MIT — see [LICENSE](LICENSE).
