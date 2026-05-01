output "eval_runner_name" {
  value = aws_lambda_function.eval_runner.function_name
}

output "golden_dataset_runner_name" {
  value = aws_lambda_function.golden_dataset_runner.function_name
}

output "pca_runner_name" {
  value = aws_lambda_function.pca_runner.function_name
}

output "qdrant_ingestion_name" {
  value = aws_lambda_function.qdrant_ingestion.function_name
}

output "ingestion_queue_url" {
  value = aws_sqs_queue.ingestion.url
}

output "ingestion_queue_arn" {
  value = aws_sqs_queue.ingestion.arn
}
