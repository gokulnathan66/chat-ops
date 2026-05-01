variable "aws_region" { type = string }
variable "env" { type = string }
variable "project" { type = string }

variable "s3_bucket_name" {
  type = string
}

variable "app_secret_arn" {
  type      = string
  sensitive = true
}

variable "app_secret_name" {
  type = string
}

variable "ec2_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "app_image_tag" {
  type    = string
  default = "latest"
}

variable "ssh_cidr_blocks" {
  type    = list(string)
  default = ["0.0.0.0/0"]
}
