resource "aws_cloudwatch_log_group" "eval_runner" {
  name              = "/aws/lambda/eval_runner"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "golden_dataset_runner" {
  name              = "/aws/lambda/golden_dataset_runner"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "pca_runner" {
  name              = "/aws/lambda/pca_runner"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "qdrant_ingestion" {
  name              = "/aws/lambda/qdrant_ingestion"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_dashboard" "llmops" {
  dashboard_name = "llmops-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0; y = 0; width = 12; height = 6
        properties = {
          title  = "Lambda Invocations"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "eval_runner"],
            ["AWS/Lambda", "Invocations", "FunctionName", "golden_dataset_runner"],
            ["AWS/Lambda", "Invocations", "FunctionName", "pca_runner"],
            ["AWS/Lambda", "Invocations", "FunctionName", "qdrant_ingestion"]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12; y = 0; width = 12; height = 6
        properties = {
          title  = "Lambda Errors"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", "eval_runner"],
            ["AWS/Lambda", "Errors", "FunctionName", "golden_dataset_runner"],
            ["AWS/Lambda", "Errors", "FunctionName", "pca_runner"],
            ["AWS/Lambda", "Errors", "FunctionName", "qdrant_ingestion"]
          ]
        }
      },
      {
        type   = "metric"
        x      = 0; y = 6; width = 12; height = 6
        properties = {
          title  = "Lambda Duration (ms)"
          period = 300
          stat   = "Average"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", "eval_runner"],
            ["AWS/Lambda", "Duration", "FunctionName", "pca_runner"]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12; y = 6; width = 12; height = 6
        properties = {
          title  = "Ingestion Queue Depth"
          period = 300
          stat   = "Average"
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "llmops-ingestion"],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "llmops-ingestion-dlq"]
          ]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "eval_runner_errors" {
  alarm_name          = "eval-runner-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"

  dimensions = { FunctionName = "eval_runner" }
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
  treat_missing_data  = "notBreaching"

  dimensions = { QueueName = "llmops-ingestion-dlq" }
}
