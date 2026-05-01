variable "aws_region" { type = string }
variable "env" { type = string }
variable "project" { type = string }

variable "s3_bucket_name" {
  type = string
}

variable "s3_bucket_arn" {
  type = string
}

variable "conversations_table" {
  type = string
}

variable "evaluations_table" {
  type = string
}

variable "hitl_table" {
  type = string
}

variable "golden_results_table" {
  type = string
}

variable "eval_schedule" {
  type    = string
  default = "rate(1 hour)"
}

variable "golden_schedule" {
  type    = string
  default = "rate(24 hours)"
}

variable "pca_schedule" {
  type    = string
  default = "rate(6 hours)"
}
