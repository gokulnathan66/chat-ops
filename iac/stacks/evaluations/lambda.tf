locals {
  lambda_zip     = "${path.module}/../../dist/lambdas.zip"
  lambda_s3_key  = "lambda-deployments/${var.project}-${var.env}-lambdas.zip"

  common_env = {
    ENV     = var.env
    PROJECT = var.project
    # AWS_REGION is reserved by Lambda — it is injected automatically

    # LLM
    MODEL_ID = var.model_id

    # Qdrant
    QDRANT_HOST       = var.qdrant_host
    QDRANT_PORT       = tostring(var.qdrant_port)
    QDRANT_API_KEY    = var.qdrant_api_key
    QDRANT_COLLECTION = var.qdrant_collection

    # Embedding
    embedding_model = var.embedding_model
    embedding_size  = tostring(var.embedding_size)
    chunk_size      = tostring(var.chunk_size)
    chunk_overlap   = tostring(var.chunk_overlap)
    top_k           = tostring(var.top_k)

    # DynamoDB tables
    CONVERSATIONS_TABLE  = var.conversations_table
    EVALUATIONS_TABLE    = var.evaluations_table
    HITL_TABLE           = var.hitl_table

    # S3
    S3_BUCKET_NAME = var.s3_bucket_name

    # Lambda references
    LAMBDA_INGESTION_FUNCTION = "${var.project}-${var.env}-qdrant-ingestion"
    LAMBDA_EVAL_RUNNER_FUNCTION = "${var.project}-${var.env}-eval-runner"

    # Eval thresholds
    INACTIVITY_MINUTES          = tostring(var.inactivity_minutes)
    RAG_THRESHOLD               = tostring(var.rag_threshold)
    HITL_THRESHOLD              = tostring(var.hitl_threshold)
    RAG_RERANK_TOP_K_MULTIPLIER = tostring(var.rag_rerank_top_k_multiplier)
  }
}

# Upload zip to S3 — avoids the 50 MB direct-upload limit for large dependency sets
resource "aws_s3_object" "lambda_zip" {
  bucket = var.s3_bucket_name
  key    = local.lambda_s3_key
  source = local.lambda_zip
  etag   = filemd5(local.lambda_zip)
}

resource "aws_lambda_function" "eval_runner" {
  function_name    = "${var.project}-${var.env}-eval-runner"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "eval_runner.handler"
  runtime          = "python3.12"
  s3_bucket        = aws_s3_object.lambda_zip.bucket
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = 300
  memory_size      = 512

  environment {
    variables = local.common_env
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_lambda_function" "pca_runner" {
  function_name    = "${var.project}-${var.env}-pca-runner"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "pca.handler"
  runtime          = "python3.12"
  s3_bucket        = aws_s3_object.lambda_zip.bucket
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = 300
  memory_size      = 512

  environment {
    variables = local.common_env
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_lambda_function" "qdrant_ingestion" {
  function_name    = "${var.project}-${var.env}-qdrant-ingestion"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "qdrant_ingestion.lambda_handler"
  runtime          = "python3.12"
  s3_bucket        = aws_s3_object.lambda_zip.bucket
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = filebase64sha256(local.lambda_zip)
  timeout          = 300
  memory_size      = 512

  environment {
    variables = local.common_env
  }

  tags = {
    Environment = var.env
    Project     = var.project
  }
}
