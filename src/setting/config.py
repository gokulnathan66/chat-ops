import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # llm
    MODEL_ID: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
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
    RAG_RERANK_TOP_K_MULTIPLIER: int = 2

    # Lambda references
    LAMBDA_EVAL_RUNNER_FUNCTION: str = "llmops-dev-eval-runner"

    # PCA degradation detection
    PCA_DEGRADATION_WINDOW: int = 10
    PCA_DEGRADATION_THRESHOLD: float = 0.6
    PCA_UNRESOLVED_THRESHOLD: int = 3

settings = Settings()


if settings.ENABLE_LANGFUSE:
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    if settings.LANGFUSE_SECRET_KEY:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
    os.environ["LANGFUSE_DEBUG"] = "true" if settings.LANGFUSE_DEBUG else "false"