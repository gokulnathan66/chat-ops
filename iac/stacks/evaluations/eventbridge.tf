resource "aws_cloudwatch_event_rule" "eval_runner" {
  name                = "${var.project}-${var.env}-eval-runner"
  description         = "Trigger eval runner on schedule"
  schedule_expression = var.eval_schedule

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_cloudwatch_event_target" "eval_runner" {
  rule      = aws_cloudwatch_event_rule.eval_runner.name
  target_id = "eval-runner"
  arn       = aws_lambda_function.eval_runner.arn
}

resource "aws_lambda_permission" "eventbridge_eval_runner" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.eval_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.eval_runner.arn
}

resource "aws_cloudwatch_event_rule" "pca_runner" {
  name                = "${var.project}-${var.env}-pca-runner"
  description         = "Trigger PCA runner on schedule"
  schedule_expression = var.pca_schedule

  tags = {
    Environment = var.env
    Project     = var.project
  }
}

resource "aws_cloudwatch_event_target" "pca_runner" {
  rule      = aws_cloudwatch_event_rule.pca_runner.name
  target_id = "pca-runner"
  arn       = aws_lambda_function.pca_runner.arn
}

resource "aws_lambda_permission" "eventbridge_pca_runner" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pca_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pca_runner.arn
}
