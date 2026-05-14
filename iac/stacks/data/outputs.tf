output "s3_documents_bucket" {
  value = aws_s3_bucket.documents.bucket
}

output "s3_documents_bucket_arn" {
  value = aws_s3_bucket.documents.arn
}

output "conversations_table" {
  value = aws_dynamodb_table.conversations.name
}

output "evaluations_table" {
  value = aws_dynamodb_table.evaluations.name
}

output "hitl_table" {
  value = aws_dynamodb_table.hitl_queue.name
}
