variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "model_id" {
  type    = string
  default = "anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "qdrant_host" {
  type    = string
  default = "localhost"
}

variable "qdrant_port" {
  type    = number
  default = 6333
}

variable "qdrant_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "qdrant_collection" {
  type    = string
  default = "llmops-rag"
}

variable "s3_bucket_name" {
  type    = string
  default = ""
}

variable "langfuse_public_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "langfuse_secret_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "langfuse_host" {
  type    = string
  default = "https://cloud.langfuse.com"
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
