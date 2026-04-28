resource "aws_cloudwatch_event_rule" "eval_runner_schedule" {
  name                = "eval-runner-schedule"
  description         = "Trigger eval_runner Lambda on a schedule"
  schedule_expression = var.eval_cron_schedule
}

resource "aws_cloudwatch_event_target" "eval_runner_target" {
  rule      = aws_cloudwatch_event_rule.eval_runner_schedule.name
  target_id = "eval_runner"
  arn       = aws_lambda_function.eval_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_eval_runner" {
  statement_id  = "AllowEventBridgeEvalRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.eval_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.eval_runner_schedule.arn
}

resource "aws_cloudwatch_event_rule" "golden_runner_schedule" {
  name                = "golden-runner-schedule"
  description         = "Trigger golden_dataset_runner Lambda on a schedule"
  schedule_expression = var.golden_cron_schedule
}

resource "aws_cloudwatch_event_target" "golden_runner_target" {
  rule      = aws_cloudwatch_event_rule.golden_runner_schedule.name
  target_id = "golden_dataset_runner"
  arn       = aws_lambda_function.golden_dataset_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_golden_runner" {
  statement_id  = "AllowEventBridgeGoldenRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.golden_dataset_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.golden_runner_schedule.arn
}

resource "aws_cloudwatch_event_rule" "pca_runner_schedule" {
  name                = "pca-runner-schedule"
  description         = "Trigger pca_runner Lambda every 15 minutes for post-conversation analysis"
  schedule_expression = "rate(15 minutes)"
}

resource "aws_cloudwatch_event_target" "pca_runner_target" {
  rule      = aws_cloudwatch_event_rule.pca_runner_schedule.name
  target_id = "pca_runner"
  arn       = aws_lambda_function.pca_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_pca_runner" {
  statement_id  = "AllowEventBridgePcaRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pca_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pca_runner_schedule.arn
}
