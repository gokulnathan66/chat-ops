from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # llm
    MODEL_ID: str = "gpt-3.5-turbo"
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 2048
    # qdrant settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = "my_qdrant_api_key"
    QDRANT_COLLECTION: str = "llmops-rag"

    # storage settings
    S3_BUCKET_NAME: str = "my-llmops-bucket"

    #Langfuse settings
  
    LANGFUSE_SECRET_KEY:  str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_BASE_URL: str = "https://api.langfuse.com"
    LANGFUSE_DEBUG: bool = True

    #feature flags 
    ENABLE_LANGFUSE: bool = False

    # general configs
    AWS_REGION: str = "us-east-1"

    # DynamoDB table names
    CONVERSATIONS_TABLE: str = "conversations"
    EVALUATIONS_TABLE: str = "evaluations"
    HITL_TABLE: str = "hitl_queue"
    GOLDEN_RESULTS_TABLE: str = "golden_results"

    # Embedding / chunking
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    embedding_size: int = 256
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k: int = 5

    # Evaluation thresholds
    INACTIVITY_MINUTES: int = 15
    RAG_THRESHOLD: float = 0.6
    HITL_THRESHOLD: float = 0.6
    GOLDEN_PASS_THRESHOLD: float = 0.7
    RAG_RERANK_TOP_K_MULTIPLIER: int = 2

settings = Settings()


if settings.ENABLE_LANGFUSE:
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    if settings.LANGFUSE_SECRET_KEY:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
    os.environ["LANGFUSE_DEBUG"] = "true" if settings.LANGFUSE_DEBUG else "false"