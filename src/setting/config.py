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

settings = Settings()


if settings.ENABLE_LANGFUSE:
    if settings.LANGFUSE_PUBLIC_KEY:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY
    if settings.LANGFUSE_SECRET_KEY:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
    os.environ["LANGFUSE_DEBUG"] = "true" if settings.LANGFUSE_DEBUG else "false"