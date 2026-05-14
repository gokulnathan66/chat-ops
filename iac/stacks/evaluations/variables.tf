variable "aws_region" { type = string }
variable "env" { type = string }
variable "project" { type = string }

variable "s3_bucket_name" { type = string }
variable "s3_bucket_arn" { type = string }

variable "conversations_table" { type = string }
variable "evaluations_table" { type = string }
variable "hitl_table" { type = string }

# LLM
variable "model_id" {
  type    = string
  default = "anthropic.claude-3-haiku-20240307-v1:0"
}

# Qdrant
variable "qdrant_host" { type = string }
variable "qdrant_port" {
  type    = number
  default = 6333
}
variable "qdrant_api_key" {
  type      = string
  sensitive = true
  default   = ""
}
variable "qdrant_collection" {
  type    = string
  default = "llmops-rag"
}

# Embedding / chunking
variable "embedding_model" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}
variable "embedding_size" {
  type    = number
  default = 256
}
variable "chunk_size" {
  type    = number
  default = 512
}
variable "chunk_overlap" {
  type    = number
  default = 64
}
variable "top_k" {
  type    = number
  default = 5
}

# Eval thresholds
variable "inactivity_minutes" {
  type    = number
  default = 15
}
variable "rag_threshold" {
  type    = number
  default = 0.6
}
variable "hitl_threshold" {
  type    = number
  default = 0.6
}
variable "rag_rerank_top_k_multiplier" {
  type    = number
  default = 2
}

# EventBridge schedules
variable "eval_schedule" {
  type    = string
  default = "rate(1 hour)"
}
variable "pca_schedule" {
  type    = string
  default = "rate(6 hours)"
}
