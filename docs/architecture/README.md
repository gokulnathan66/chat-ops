# LLMOps — End-to-End Architecture

This folder describes the architecture of the LLMOps RAG application end-to-end. The legacy `docs/architecture.md` covers the chat request flow only; the files here extend that with the rest of the system.

## What this application is

A **LangGraph-based RAG API** for a financial assistant that can answer questions about Apple, Google/Alphabet, and Microsoft 10-K filings, with:

- **Bedrock** (Claude Haiku 4.5) as the LLM and **Titan Embed v2** for embeddings
- **Qdrant** as the vector store
- **DynamoDB** for sessions, evaluations, and a HITL queue
- **S3** for source documents and Lambda deployment artifacts
- **Async ingestion** (S3 → SQS → Lambda → Qdrant → eval Lambda)
- **Scheduled post-conversation analysis** (EventBridge → PCA Lambda → degradation alerts)
- **Human-in-the-loop** (low-confidence escalation + sensitive-action approval gating)
- **Langfuse** tracing and externalized prompt management
- **Two Next.js dashboards** — one for chat, one for live monitoring

## System map

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
                  │   LangGraph state machine │    │   AWS services   │
                  │   intent → general/tools/ │    │  DynamoDB · S3   │
                  │   escalate/approval       │    │  Bedrock         │
                  └──────────────┬────────────┘    │  Lambda · SQS    │
                                 │                 │  EventBridge     │
                                 ▼                 │  Secrets · CW    │
                          ┌─────────────┐          └────────┬─────────┘
                          │   Bedrock   │                   │
                          │  Claude 4.5 │                   │
                          │   Titan v2  │                   │
                          └─────────────┘                   │
                                                            │
                          ┌─────────────┐                   │
                          │   Qdrant    │◄──────────────────┘
                          │  vector DB  │  upserts from ingestion Lambda
                          └─────────────┘
```

## Document index

| File | Topic |
|------|-------|
| [01-runtime.md](01-runtime.md) | FastAPI tier, LangGraph state machine, nodes, services |
| [02-storage.md](02-storage.md) | DynamoDB tables/GSIs, Qdrant payload, S3 layout |
| [03-pipelines.md](03-pipelines.md) | Async ingestion, RAG evaluation, PCA degradation loop |
| [04-hitl.md](04-hitl.md) | HITL escalation and approval flows |
| [05-infrastructure.md](05-infrastructure.md) | Terraform stacks, EC2, ECR, CloudWatch, secrets |
| [06-dashboards.md](06-dashboards.md) | The two Next.js apps and their backends |
| [07-configuration.md](07-configuration.md) | Settings, env vars, prompts, observability |

## Reading order

If you want the shortest tour: read `01-runtime.md`, then `03-pipelines.md`, then `02-storage.md`. Everything else is reference.
