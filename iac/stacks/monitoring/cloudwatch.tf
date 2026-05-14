resource "aws_cloudwatch_log_group" "eval_runner" {
  name              = "/aws/lambda/${var.eval_runner_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_cloudwatch_log_group" "pca_runner" {
  name              = "/aws/lambda/${var.pca_runner_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_cloudwatch_log_group" "qdrant_ingestion" {
  name              = "/aws/lambda/${var.qdrant_ingestion_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_cloudwatch_dashboard" "llmops" {
  dashboard_name = "${var.project}-${var.env}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          title  = "Lambda Errors"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", var.eval_runner_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.pca_runner_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.qdrant_ingestion_name]
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "Lambda Duration (ms)"
          period = 300
          stat   = "Average"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.eval_runner_name],
            ["AWS/Lambda", "Duration", "FunctionName", var.pca_runner_name],
            ["AWS/Lambda", "Duration", "FunctionName", var.qdrant_ingestion_name]
          ]
        }
      },
      {
        type = "metric"
        properties = {
          title  = "EC2 CPU Utilization"
          period = 300
          stat   = "Average"
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceId", var.ec2_instance_id]
          ]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "eval_runner_errors" {
  alarm_name          = "${var.project}-${var.env}-eval-runner-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.lambda_error_threshold

  dimensions = {
    FunctionName = var.eval_runner_name
  }

  alarm_description = "Eval runner Lambda error rate too high"

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_cloudwatch_metric_alarm" "qdrant_ingestion_errors" {
  alarm_name          = "${var.project}-${var.env}-qdrant-ingestion-errors"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.lambda_error_threshold

  dimensions = {
    FunctionName = var.qdrant_ingestion_name
  }

  alarm_description = "Qdrant ingestion Lambda error rate too high"

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_cloudwatch_metric_alarm" "ec2_cpu" {
  alarm_name          = "${var.project}-${var.env}-ec2-cpu-high"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80

  dimensions = {
    InstanceId = var.ec2_instance_id
  }

  alarm_description = "EC2 CPU utilization above 80%"

  tags = {
    Environment = var.env
    Project     = var.project
  }
}
