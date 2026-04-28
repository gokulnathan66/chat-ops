# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run development server (hot reload)
make dev
# or
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Run production server
make run
# or
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000

# Install dependencies
uv sync
```

No test infrastructure exists yet. Health check endpoint: `GET /health`.

## Architecture

This is a **LangGraph-based RAG API** using AWS Bedrock as the LLM backend and Qdrant as the vector store.

### Request Flow

```
POST /api/chat
  → Intent Node (Bedrock structured output: "general" | "tools")
  → Router
      ├── General Node → direct converse_text() response
      └── Tools Node  → LangChain agent with semantic_document_search tool (Qdrant)
  → GraphInvokeResponse
```

### Key Layers

| Layer | Path | Responsibility |
|-------|------|---------------|
| API | `src/api/routes.py` | FastAPI endpoints |
| Graph | `src/graph/builder.py` | LangGraph state machine (3 nodes) |
| Nodes | `src/nodes/` | intent.py, general.py, tools.py |
| State | `src/states/config.py` | `GraphState` TypedDict |
| Services | `src/services/` | Bedrock, Qdrant, Embedding, S3 wrappers |
| Tools | `src/tools/rag.py` | `semantic_document_search` LangChain tool |
| Schema | `src/schema/config.py` | Pydantic request/response models |
| Settings | `src/setting/config.py` | Pydantic Settings (env-based config) |
| Lambdas | `src/lambdas/` | Async S3→Qdrant ingestion; eval stubs |

### BedrockService Methods

- `converse_text()` — simple text generation
- `converse_structured()` — JSON structured output (used by intent router)
- `converse_stream()` — streaming
- `invoke_agent()` — LangChain tool-use agent (used by Tools node)

### Configuration

All config is environment-variable driven via `src/setting/config.py`. Key vars:
- `MODEL_ID` — Bedrock model ARN (Claude Haiku 4.5)
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`
- `S3_BUCKET_NAME`
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`, `ENABLE_LANGFUSE`
- `AWS_REGION` (default: us-east-1)

### Observability

Langfuse tracing is integrated and toggled by `ENABLE_LANGFUSE`. Traces wrap graph execution. `src/lambdas/rag_evaluator.py` is an empty stub for future evaluation logic.

### Infrastructure

Terraform IaC scaffolding lives in `iac/terraform-aws/` (most `.tf` files are empty stubs). `src/lambdas/qdrant_ingestion.py` handles async document ingestion from S3 into Qdrant. Dashboard UIs in `dashboard/` are not yet implemented.
