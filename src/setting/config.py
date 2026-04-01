from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    #llm
    MODEL_ID = os.getenv("MODEL", "gpt-3.5-turbo") 

    #qdrant settings
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "my_qdrant_api_key")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "llmops-rag")

    #storage settings
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "my-llmops-bucket")
    
    #embedding settings

    #feature flags





settings = Settings()
