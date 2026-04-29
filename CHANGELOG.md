# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2025-04-29

### Added
- Evaluation pipeline: `rag_evaluator`, `pca`, `golden_dataset_runner`, `eval_runner` in `evaluations/`
- AWS Bedrock Titan Embed Text v2 (`amazon.titan-embed-text-v2:0`, 256-dim) replacing SentenceTransformers
- Qdrant UUID point IDs (SHA-256 digest → UUID bytes)
- Langfuse-managed prompts for `rag_assistant`, `general_assistant`, `intent_router` with hardcoded fallbacks
- DynamoDB tables fully defined in Terraform (`data_managment` module)
- Terraform submodules: `data_managment`, `evaluations`, `monitoring`, `security`
- S3 Terraform state backend (`llmops-terraform-state-<account_id>`)
- EC2, ECR, SQS ingestion queue, CloudWatch alarms, Secrets Manager IaC
- `docker-compose.yaml` for local Qdrant
- Golden dataset with 15 Q&A pairs covering Apple, Google/Alphabet, Microsoft
- Dashboard APIs: `/api/conversations`, `/api/evaluations`, `/api/hitl`, `/api/metrics/summary`, `/api/golden-results`
- Local E2E test script (`scripts/local_e2e_test.sh`) with 13 test sections
- `make e2e`, `make test`, `make ingest` targets

### Changed
- `converse_structured` rewritten to use Bedrock tool-use (`toolConfig`) instead of `outputConfig` — works on all Claude models
- `QDRANT_COLLECTION` casing aligned across all service references
- `dashboard.py` module-level singleton replaced with per-request factory to fix moto test isolation

### Fixed
- Duplicate `extract_text` static method in `BedrockService` (silent override)
- Missing `reason` field in `GraphState` TypedDict
- `golden_dataset_runner` used `text_snippet` instead of `text` for retrieved doc context
- 3 failing dashboard tests caused by pre-moto singleton instantiation

## [0.1.0] - 2025-04-21

### Added
- LangGraph RAG API with FastAPI, intent routing (`general` | `tools`), AWS Bedrock Claude Haiku
- Qdrant vector store integration with semantic search and payload indexing
- Langfuse observability with `@observe()` decorators on all graph nodes
- `ConversationService` with DynamoDB persistence (turns + metadata + HITL queue)
- `BedrockService` with `converse`, `converse_text`, `converse_stream`, `converse_structured`, `invoke_agent`
- `EmbeddingService` with sliding-window chunking
- `S3Service` with PDF and CSV document reading
- LangChain `semantic_document_search` tool wired into tools node
- Pydantic Settings with env-file support
- Dashboard Next.js app scaffold (monitoring overview, evals, golden dataset, PCA pages)

[Unreleased]: https://github.com/gokulnathan66/llmops/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/gokulnathan66/llmops/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/gokulnathan66/llmops/releases/tag/v0.1.0
