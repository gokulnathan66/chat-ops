variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "conversations_table" {
  description = "DynamoDB table for conversation turns and metadata"
  type        = string
  default     = "conversations"
}

variable "evaluations_table" {
  description = "DynamoDB table for RAG and PCA evaluation results"
  type        = string
  default     = "evaluations"
}

variable "hitl_table" {
  description = "DynamoDB table for HITL queue items"
  type        = string
  default     = "hitl_queue"
}

variable "golden_results_table" {
  description = "DynamoDB table for golden dataset run results"
  type        = string
  default     = "golden_results"
}
