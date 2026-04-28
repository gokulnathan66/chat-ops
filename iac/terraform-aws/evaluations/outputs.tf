output "eval_runner_arn" {
  description = "ARN of the eval_runner Lambda"
  value       = aws_lambda_function.eval_runner.arn
}

output "golden_dataset_runner_arn" {
  description = "ARN of the golden_dataset_runner Lambda"
  value       = aws_lambda_function.golden_dataset_runner.arn
}

output "pca_runner_arn" {
  description = "ARN of the pca_runner Lambda"
  value       = aws_lambda_function.pca_runner.arn
}
