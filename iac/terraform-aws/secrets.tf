resource "aws_secretsmanager_secret" "app_secrets" {
  name        = "llmops/app-secrets"
  description = "LLMOps application config — Langfuse, Qdrant, and runtime settings"

  recovery_window_in_days = 7

  tags = {
    Name    = "llmops-app-secrets"
    Project = "llmops"
  }
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id

  secret_string = jsonencode({
    MODEL_ID             = var.model_id
    AWS_REGION           = var.aws_region
    QDRANT_HOST          = var.qdrant_host
    QDRANT_PORT          = tostring(var.qdrant_port)
    QDRANT_API_KEY       = var.qdrant_api_key
    QDRANT_COLLECTION    = var.qdrant_collection
    S3_BUCKET_NAME       = aws_s3_bucket.documents.id
    LANGFUSE_PUBLIC_KEY  = var.langfuse_public_key
    LANGFUSE_SECRET_KEY  = var.langfuse_secret_key
    LANGFUSE_HOST        = var.langfuse_host
    ENABLE_LANGFUSE      = "true"
    CONVERSATIONS_TABLE  = var.conversations_table
    EVALUATIONS_TABLE    = var.evaluations_table
    HITL_TABLE           = var.hitl_table
    GOLDEN_RESULTS_TABLE = var.golden_results_table
  })
}
