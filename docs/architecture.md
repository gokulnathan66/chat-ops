# Architecture

## Request Flow

```
POST /api/chat
  │
  ├─ FastAPI route handler (src/api/routes.py)
  │   └─ Langfuse @observe() trace starts
  │
  ├─ LangGraph graph.invoke() (src/graph/builder.py)
  │   │
  │   ├─ intent_node (src/nodes/intent.py)
  │   │   └─ BedrockService.converse_structured()
  │   │       └─ Tool-use forced call → {intent, route, confidence, reason}
  │   │
  │   ├─ [route == "general"] general_node (src/nodes/general.py)
  │   │   └─ BedrockService.converse() → text response
  │   │
  │   └─ [route == "tools"] tools_node (src/nodes/tools.py)
  │       └─ BedrockService.invoke_agent()
  │           └─ LangChain agent loop
  │               └─ semantic_document_search tool (src/tools/rag.py)
  │                   ├─ EmbeddingService.embed_query() → Titan Embed v2
  │                   └─ QdrantService.semantic_search() → top-k chunks
  │
  ├─ ConversationService.write_turn() → DynamoDB
  │   ├─ turn#NNN item (query, response, route, docs, tokens, latency)
  │   └─ metadata item (status=active, last_updated_at, turn_count)
  │
  └─ Langfuse trace flushed
```

## Evaluation Pipeline

```
EventBridge (every 15 min)
  └─ eval_runner Lambda (evaluations/eval_runner.py)
      ├─ get_stale_sessions()
      │   └─ DynamoDB GSI: status=active, last_updated_at < now-15min
      │
      └─ for each stale session:
          ├─ mark_complete() → DynamoDB
          │
          ├─ rag_evaluator.evaluate_session()
          │   ├─ embed query + retrieved docs → cosine similarity (rag_score)
          │   ├─ LLM judge → faithfulness + relevance
          │   ├─ if rag_score < RAG_THRESHOLD: re-retrieve top-k×2
          │   ├─ if still < HITL_THRESHOLD: write hitl_queue
          │   └─ write evaluations table (eval_type=rag)
          │
          └─ pca.analyze_conversation()
              ├─ LLM structured output → topics, sentiment, unresolved
              └─ write evaluations table (eval_type=pca)

EventBridge (every 1 hr)
  └─ golden_dataset_runner Lambda (evaluations/golden_dataset_runner.py)
      ├─ load golden.json from S3
      └─ for each Q&A pair:
          ├─ semantic_document_search → retrieve context
          ├─ converse_text → generate answer
          ├─ converse_structured → LLM judge scores
          └─ write golden_results table
```

## Service Layer

| Service | File | Responsibility |
|---------|------|----------------|
| `BedrockService` | `src/services/bedrock.py` | `converse`, `converse_text`, `converse_stream`, `converse_structured` (tool-use), `invoke_agent` |
| `EmbeddingService` | `src/services/embedding.py` | Titan Embed v2 via Bedrock, sliding-window chunking |
| `QdrantService` | `src/services/qdrant.py` | Collection management, UUID point IDs, semantic search |
| `ConversationService` | `src/services/conversation.py` | DynamoDB turns + metadata + HITL queue |
| `PromptService` | `src/services/prompt.py` | Langfuse prompt versioning with local fallbacks |
| `S3Service` | `src/services/s3.py` | PDF + CSV document reading |

## DynamoDB Schema

### conversations table
| PK | SK | Attributes |
|----|----|-----------|
| `session_id` | `metadata` | status, last_updated_at, turn_count, created_at |
| `session_id` | `turn#001` | user_query, ai_response, intent, route, retrieved_docs, token_usage, latency_ms |

GSI: `status-last_updated_at-index` (for stale session queries)

### evaluations table
| PK | SK | Attributes |
|----|----|-----------|
| `session_id` | `eval#rag#<timestamp>` | eval_type, rag_score, faithfulness, relevance, hitl_flagged |
| `session_id` | `eval#pca#<timestamp>` | eval_type, pca_topics, pca_sentiment, pca_unresolved |

GSI: `eval_type-created_at-index`

### hitl_queue table
| PK | SK | Attributes |
|----|----|-----------|
| `HITL` | `<timestamp>#<session_id>` | queue_status, trigger, conversation_summary, rag_score |

GSI: `queue_status-sk-index`

### golden_results table
| PK | SK | Attributes |
|----|----|-----------|
| `run_id` | `question_id` | question, expected_answer, generated_answer, faithfulness, relevance, avg_score, pass |
