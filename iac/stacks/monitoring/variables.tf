variable "aws_region" { type = string }
variable "env" { type = string }
variable "project" { type = string }

variable "log_retention_days" {
  type    = number
  default = 14
}

variable "eval_runner_name" {
  type = string
}

variable "pca_runner_name" {
  type = string
}

variable "qdrant_ingestion_name" {
  type = string
}

variable "ec2_instance_id" {
  type = string
}

variable "lambda_error_threshold" {
  type    = number
  default = 5
}
