from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # llm
    MODEL_ID: str = "gpt-3.5-turbo"

    # qdrant settings
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = "my_qdrant_api_key"
    QDRANT_COLLECTION: str = "llmops-rag"

    # storage settings
    S3_BUCKET_NAME: str = "my-llmops-bucket"


    #feature flags 


    # general configs 
    AWS_REGION: str = "us-east-1"
settings = Settings()