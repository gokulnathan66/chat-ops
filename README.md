# LLMOps — End-to-End RAG Application

A production-grade LangGraph RAG API with full LLMOps tooling: observability, prompt versioning, evaluation pipelines, HITL, real-time monitoring, and one-command infrastructure.

---

## Architecture Overview

```
POST /api/chat
  → Intent Node  (Bedrock structured output → "general" | "tools")
  → Router
      ├── General Node  → converse_text() → response
      └── Tools Node    → LangChain agent + semantic_document_search (Qdrant) → response
  → DynamoDB (conversation turn written)
  → Langfuse (trace flushed)
```

### Stack

| Layer | Technology |
|---|---|
| API | FastAPI + LangGraph |
| LLM | AWS Bedrock (Claude Haiku 4.5) |
| Vector store | Qdrant |
| Embeddings | Sentence Transformers |
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
├── src/
│   ├── api/routes.py            # FastAPI endpoints
│   ├── graph/builder.py         # LangGraph state machine
│   ├── nodes/
│   │   ├── intent.py            # Intent router node
│   │   ├── general.py           # General response node
│   │   └── tools.py             # RAG agent node
│   ├── services/
│   │   ├── bedrock.py           # AWS Bedrock wrapper
│   │   ├── conversation.py      # DynamoDB conversation store
│   │   ├── embedding.py         # Sentence Transformers
│   │   ├── prompt.py            # Langfuse prompt versioning
│   │   ├── qdrant.py            # Qdrant vector store
│   │   ├── s3.py                # S3 document reader
│   │   └── mcp.py               # MCP server client
│   ├── tools/rag.py             # semantic_document_search tool
│   ├── states/config.py         # GraphState TypedDict
│   ├── schema/config.py         # Pydantic request/response models
│   └── setting/config.py        # Pydantic Settings (env-based)
├── evaluations/
│   ├── rag_evaluator.py         # RAG faithfulness + relevance scoring
│   ├── eval_runner.py           # Stale session eval orchestrator
│   ├── golden_dataset_runner.py # Golden Q&A regression tests
│   └── pca.py                   # Post-conversation analysis (topics, sentiment)
├── data/
│   ├── golden.json              # Golden Q&A dataset (Apple, Google, Microsoft)
│   ├── csv/                     # Big tech financial summary CSVs
│   └── pdfs/
│       ├── annual_reports/      # Apple, Google, Microsoft 10-K 2025
│       └── news_articles/       # AI strategy and earnings news
├── iac/terraform-aws/
│   ├── main.tf                  # Provider, S3 backend, documents bucket
│   ├── ec2.tf                   # API server (t3.medium, ECR pull on boot)
│   ├── ecr.tf                   # Docker image registry
│   ├── sqs.tf                   # Ingestion queue + Lambda trigger
│   ├── secrets.tf               # Secrets Manager (all env vars)
│   ├── lambda.tf                # eval_runner, golden_dataset_runner, pca_runner
│   ├── event_bridge.tf          # Cron schedules for all Lambdas
│   ├── cloudwatch.tf            # Log groups + alarms
│   ├── iam.tf                   # Lambda and EC2 IAM roles
│   ├── variables.tf             # All input variables
│   ├── outputs.tf               # EC2 IP, ECR URL, SQS ARN, etc.
│   ├── user_data.sh             # EC2 bootstrap (Docker + ECR pull)
│   ├── terraform.tfvars.example # Example values
│   ├── data_managment/          # Module: DynamoDB tables
│   ├── evaluations/             # Module: eval Lambdas + EventBridge
│   ├── monitoring/              # Module: CloudWatch dashboard + alarms
│   └── security/                # Module: Secrets Manager
├── dashboard/realtime-monitoring/  # Next.js monitoring dashboard
├── scripts/deploy.sh            # Full deploy script
├── Dockerfile                   # Container image
└── docker-compose.yaml          # Local dev stack
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
- Lambda chunks text, embeds with Sentence Transformers, upserts to Qdrant
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
Next.js app at `dashboard/realtime-monitoring`:
- Overview page: KPI cards, recent eval scores, PCA sentiment strip
- Evaluations page: session-level RAG + faithfulness scores, HITL flag status
- Golden Dataset page: pass rate trend, per-question breakdown
- PCA page: topic distribution, sentiment over time, unresolved question list

---

## Quick Start

### Local development

```bash
# Install dependencies
uv sync

# Start Qdrant locally
docker run -p 6333:6333 qdrant/qdrant

# Copy and fill environment variables
cp .env.example .env

# Run with hot reload
make dev
# or
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `GET /health`

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
| `MODEL_ID` | `gpt-3.5-turbo` | AWS Bedrock model ARN |
| `AWS_REGION` | `us-east-1` | AWS region |
| `QDRANT_HOST` | `localhost` | Qdrant hostname |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `QDRANT_API_KEY` | — | Qdrant API key |
| `QDRANT_COLLECTION` | `llmops-rag` | Qdrant collection name |
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

State bucket: `llmops-terraform-state` (create this bucket manually before first `terraform init`).

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
                                                