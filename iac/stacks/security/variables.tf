variable "aws_region" { type = string }
variable "env" { type = string }
variable "project" { type = string }

variable "model_id" {
  type    = string
  default = ""
}

variable "qdrant_host" {
  type    = string
  default = ""
}

variable "qdrant_port" {
  type    = string
  default = "6333"
}

variable "qdrant_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "qdrant_collection" {
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
  default = ""
}

variable "s3_bucket_name" {
  type    = string
  default = ""
}

variable "conversations_table" {
  type    = string
  default = ""
}

variable "evaluations_table" {
  type    = string
  default = ""
}

variable "hitl_table" {
  type    = string
  default = ""
}
