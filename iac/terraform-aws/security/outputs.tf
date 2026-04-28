output "app_secret_arn" {
  description = "Secrets Manager ARN for application config"
  value       = aws_secretsmanager_secret.app_secrets.arn
  sensitive   = true
}

output "app_secret_name" {
  description = "Secrets Manager secret name (for EC2 user_data)"
  value       = aws_secretsmanager_secret.app_secrets.name
}
