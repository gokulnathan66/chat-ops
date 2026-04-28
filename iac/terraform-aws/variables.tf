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
  description = "S3 bucket name for document storage and golden.json (auto-generated if empty)"
  type        = string
  default     = ""
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "ap-south-1"
}

variable "ec2_instance_type" {
  description = "EC2 instance type for the API server"
  type        = string
  default     = "t3.medium"
}

variable "ec2_key_name" {
  description = "EC2 key pair name for SSH access (leave empty to skip)"
  type        = string
  default     = ""
}

variable "ecr_repo_name" {
  description = "ECR repository name for the API Docker image"
  type        = string
  default     = "llmops-api"
}

variable "app_image_tag" {
  description = "Docker image tag to deploy on EC2"
  type        = string
  default     = "latest"
}

variable "qdrant_host" {
  description = "Qdrant server hostname or IP"
  type        = string
  default     = "localhost"
}

variable "qdrant_port" {
  description = "Qdrant server port"
  type        = number
  default     = 6333
}

variable "qdrant_api_key" {
  description = "Qdrant API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "qdrant_collection" {
  description = "Qdrant collection name"
  type        = string
  default     = "llmops-rag"
}

variable "langfuse_public_key" {
  description = "Langfuse public key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "langfuse_secret_key" {
  description = "Langfuse secret key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "langfuse_host" {
  description = "Langfuse host URL"
  type        = string
  default     = "https://cloud.langfuse.com"
}

variable "model_id" {
  description = "AWS Bedrock model ID"
  type        = string
  default     = "anthropic.claude-haiku-4-5-20251001-v1:0"
}
