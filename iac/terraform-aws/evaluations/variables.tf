variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "conversations_table" {
  type    = string
  default = "conversations"
}

variable "evaluations_table" {
  type    = string
  default = "evaluations"
}

variable "hitl_table" {
  type    = string
  default = "hitl_queue"
}

variable "golden_results_table" {
  type    = string
  default = "golden_results"
}

variable "s3_bucket_name" {
  type    = string
  default = ""
}

variable "eval_cron_schedule" {
  type    = string
  default = "rate(15 minutes)"
}

variable "golden_cron_schedule" {
  type    = string
  default = "rate(1 hour)"
}

variable "rag_threshold" {
  type    = number
  default = 0.6
}

variable "hitl_threshold" {
  type    = number
  default = 0.6
}

variable "inactivity_minutes" {
  type    = number
  default = 15
}

variable "golden_pass_threshold" {
  type    = number
  default = 0.7
}
