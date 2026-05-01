resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "${var.project}-${var.env}-ingestion-dlq"
  message_retention_seconds = 1209600

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_sqs_queue" "ingestion" {
  name                       = "${var.project}-${var.env}-ingestion"
  visibility_timeout_seconds = 300

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_sqs_queue_policy" "ingestion" {
  queue_url = aws_sqs_queue.ingestion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.ingestion.arn
      Condition = {
        ArnLike = { "aws:SourceArn" = var.s3_bucket_arn }
      }
    }]
  })
}

resource "aws_s3_bucket_notification" "ingestion" {
  bucket = var.s3_bucket_name

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "documents/"
  }

  depends_on = [aws_sqs_queue_policy.ingestion]
}

resource "aws_lambda_permission" "sqs_invoke_ingestion" {
  statement_id  = "AllowSQSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.qdrant_ingestion.function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = aws_sqs_queue.ingestion.arn
}

resource "aws_lambda_event_source_mapping" "ingestion" {
  event_source_arn = aws_sqs_queue.ingestion.arn
  function_name    = aws_lambda_function.qdrant_ingestion.arn
  batch_size       = 10
}
