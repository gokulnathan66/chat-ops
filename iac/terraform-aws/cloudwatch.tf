resource "aws_cloudwatch_event_rule" "eval_runner_schedule" {
  name                = "eval-runner-schedule"
  description         = "Triggers eval_runner Lambda on a configurable schedule"
  schedule_expression = var.eval_cron_schedule
}

resource "aws_cloudwatch_event_target" "eval_runner_target" {
  rule      = aws_cloudwatch_event_rule.eval_runner_schedule.name
  target_id = "eval_runner"
  arn       = aws_lambda_function.eval_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_eval" {
  statement_id  = "AllowEventBridgeEvalRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.eval_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.eval_runner_schedule.arn
}

resource "aws_cloudwatch_event_rule" "golden_runner_schedule" {
  name                = "golden-runner-schedule"
  description         = "Triggers golden_dataset_runner Lambda on a configurable schedule"
  schedule_expression = var.golden_cron_schedule
}

resource "aws_cloudwatch_event_target" "golden_runner_target" {
  rule      = aws_cloudwatch_event_rule.golden_runner_schedule.name
  target_id = "golden_dataset_runner"
  arn       = aws_lambda_function.golden_dataset_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_golden" {
  statement_id  = "AllowEventBridgeGoldenRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.golden_dataset_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.golden_runner_schedule.arn
}
