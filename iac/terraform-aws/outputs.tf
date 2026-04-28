output "ec2_public_ip" {
  description = "Public IP of the API server"
  value       = aws_instance.api_server.public_ip
}

output "ec2_public_dns" {
  description = "Public DNS of the API server"
  value       = aws_instance.api_server.public_dns
}

output "api_endpoint" {
  description = "API base URL"
  value       = "http://${aws_instance.api_server.public_ip}:8000"
}

output "ecr_repository_url" {
  description = "ECR repository URL for docker push/pull"
  value       = aws_ecr_repository.api.repository_url
}

output "sqs_ingestion_url" {
  description = "SQS queue URL for document ingestion"
  value       = aws_sqs_queue.ingestion.url
}

output "sqs_ingestion_arn" {
  description = "SQS queue ARN"
  value       = aws_sqs_queue.ingestion.arn
}

output "s3_documents_bucket" {
  description = "S3 bucket for document storage"
  value       = aws_s3_bucket.documents.id
}

output "app_secret_arn" {
  description = "Secrets Manager ARN for application config"
  value       = aws_secretsmanager_secret.app_secrets.arn
  sensitive   = true
}

output "account_id" {
  description = "AWS account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "Deployed AWS region"
  value       = data.aws_region.current.name
}

output "ecr_push_commands" {
  description = "Commands to build and push the Docker image to ECR"
  value       = <<-EOT
    aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.api.repository_url}
    docker build -t ${aws_ecr_repository.api.repository_url}:${var.app_image_tag} .
    docker push ${aws_ecr_repository.api.repository_url}:${var.app_image_tag}
  EOT
}
