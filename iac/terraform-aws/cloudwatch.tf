resource "aws_cloudwatch_log_group" "eval_runner" {
  name              = "/aws/lambda/eval_runner"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "golden_dataset_runner" {
  name              = "/aws/lambda/golden_dataset_runner"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "pca_runner" {
  name              = "/aws/lambda/pca_runner"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "qdrant_ingestion" {
  name              = "/aws/lambda/qdrant_ingestion"
  retention_in_days = 14
}

resource "aws_cloudwatch_metric_alarm" "eval_runner_errors" {
  alarm_name          = "eval-runner-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "eval_runner Lambda error rate exceeded 5 in 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.eval_runner.function_name
  }
}

resource "aws_cloudwatch_metric_alarm" "ingestion_dlq_depth" {
  alarm_name          = "ingestion-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Messages in ingestion DLQ — documents failed to index into Qdrant"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.ingestion_dlq.name
  }
}

resource "aws_cloudwatch_metric_alarm" "golden_runner_errors" {
  alarm_name          = "golden-runner-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 3600
  statistic           = "Sum"
  threshold           = 3
  alarm_description   = "golden_dataset_runner Lambda error rate exceeded 3 in 1 hour"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.golden_dataset_runner.function_name
  }
}
