variable "aws_region" { type = string }
variable "env" { type = string }
variable "project" { type = string }

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
variable "s3_bucket_name" {
  description = "Bucket name; auto-generated from account ID if empty"
  type        = string
  default     = ""
}
