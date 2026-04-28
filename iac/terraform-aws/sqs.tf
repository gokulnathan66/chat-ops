resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "llmops-ingestion-dlq"
  message_retention_seconds = 1209600

  tags = {
    Name    = "llmops-ingestion-dlq"
    Project = "llmops"
  }
}

resource "aws_sqs_queue" "ingestion" {
  name                       = "llmops-ingestion"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 86400

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Name    = "llmops-ingestion"
    Project = "llmops"
  }
}

resource "aws_sqs_queue_policy" "ingestion" {
  queue_url = aws_sqs_queue.ingestion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowS3SendMessage"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.ingestion.arn
      Condition = {
        ArnLike = { "aws:SourceArn" = aws_s3_bucket.documents.arn }
      }
    }]
  })
}

resource "aws_s3_bucket_notification" "documents_to_sqs" {
  bucket = aws_s3_bucket.documents.id

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".pdf"
  }

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".txt"
  }

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".csv"
  }

  depends_on = [aws_sqs_queue_policy.ingestion]
}

resource "aws_lambda_function" "qdrant_ingestion" {
  function_name = "qdrant_ingestion"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "qdrant_ingestion.lambda_handler"
  runtime       = "python3.13"
  timeout       = 300
  memory_size   = 1024

  filename         = "dist/lambdas.zip"
  source_code_hash = filebase64sha256("dist/lambdas.zip")

  environment {
    variables = {
      QDRANT_HOST       = var.qdrant_host
      QDRANT_PORT       = tostring(var.qdrant_port)
      QDRANT_API_KEY    = var.qdrant_api_key
      QDRANT_COLLECTION = var.qdrant_collection
      S3_BUCKET_NAME    = aws_s3_bucket.documents.id
    }
  }

  tags = { Project = "llmops" }
}

resource "aws_lambda_permission" "allow_sqs_ingestion" {
  statement_id  = "AllowSQSTrigger"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.qdrant_ingestion.function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = aws_sqs_queue.ingestion.arn
}

resource "aws_lambda_event_source_mapping" "sqs_to_ingestion" {
  event_source_arn = aws_sqs_queue.ingestion.arn
  function_name    = aws_lambda_function.qdrant_ingestion.arn
  batch_size       = 1
}
