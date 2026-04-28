output "conversations_table_arn" {
  description = "ARN of the conversations DynamoDB table"
  value       = aws_dynamodb_table.conversations.arn
}

output "evaluations_table_arn" {
  description = "ARN of the evaluations DynamoDB table"
  value       = aws_dynamodb_table.evaluations.arn
}

output "hitl_table_arn" {
  description = "ARN of the HITL queue DynamoDB table"
  value       = aws_dynamodb_table.hitl_queue.arn
}

output "golden_results_table_arn" {
  description = "ARN of the golden results DynamoDB table"
  value       = aws_dynamodb_table.golden_results.arn
}

output "conversations_table_name" {
  value = aws_dynamodb_table.conversations.name
}

output "evaluations_table_name" {
  value = aws_dynamodb_table.evaluations.name
}
