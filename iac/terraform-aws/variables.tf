variable "conversations_table" {
  description = "DynamoDB table name for conversations"
  type        = string
  default     = "conversations"
}

variable "evaluations_table" {
  description = "DynamoDB table name for evaluations"
  type        = string
  default     = "evaluations"
}

variable "hitl_table" {
  description = "DynamoDB table name for HITL queue"
  type        = string
  default     = "hitl_queue"
}

variable "golden_results_table" {
  description = "DynamoDB table name for golden dataset results"
  type        = string
  default     = "golden_results"
}

variable "eval_cron_schedule" {
  description = "EventBridge cron schedule for evaluation Lambda"
  type        = string
  default     = "rate(15 minutes)"
}

variable "golden_cron_schedule" {
  description = "EventBridge cron schedule for golden dataset runner"
  type        = string
  default     = "rate(1 hour)"
}

variable "rag_threshold" {
  description = "RAG score below which re-retrieval is triggered"
  type        = number
  default     = 0.6
}

variable "hitl_threshold" {
  description = "Score below which HITL flagging is triggered after re-retrieval"
  type        = number
  default     = 0.6
}

variable "inactivity_minutes" {
  description = "Minutes of inactivity before a session is marked complete"
  type        = number
  default     = 15
}

variable "golden_pass_threshold" {
  description = "Minimum LLM judge score for a golden dataset question to pass"
  type        = number
  default     = 0.7
}

variable "s3_bucket_name" {
  description = "S3 bucket name for document storage and golden.json"
  type        = string
  default     = ""
}
