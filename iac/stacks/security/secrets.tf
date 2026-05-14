resource "aws_secretsmanager_secret" "app" {
  name                    = "${var.project}/app-secrets"
  recovery_window_in_days = 0

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    MODEL_ID             = var.model_id
    QDRANT_HOST          = var.qdrant_host
    QDRANT_PORT          = var.qdrant_port
    QDRANT_API_KEY       = var.qdrant_api_key
    QDRANT_COLLECTION    = var.qdrant_collection
    LANGFUSE_PUBLIC_KEY  = var.langfuse_public_key
    LANGFUSE_SECRET_KEY  = var.langfuse_secret_key
    LANGFUSE_HOST        = var.langfuse_host
    S3_BUCKET_NAME       = var.s3_bucket_name
    CONVERSATIONS_TABLE       = var.conversations_table
    EVALUATIONS_TABLE         = var.evaluations_table
    HITL_TABLE                = var.hitl_table
    LAMBDA_INGESTION_FUNCTION = "${var.project}-${var.env}-qdrant-ingestion"
  })
}
