# Terraform Modular Stacks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `iac/terraform-aws/` layout with a clean two-layer structure: shared `stacks/` (TF resource files, written once) + `envs/` (only `.tfvars` per environment), orchestrated by a root `Makefile`.

**Architecture:** Five independent Terraform stacks (`data`, `security`, `evaluations`, `app`, `monitoring`) each with their own S3 remote state keyed as `{env}/{stack}/terraform.tfstate`. The Makefile injects the backend config at `init` time and wires cross-stack outputs as `-var` flags. No Terragrunt — pure Terraform `~> 6.0`.

**Tech Stack:** Terraform >= 1.6, AWS provider ~> 6.0, GNU Make, `jq` (for sensitive output extraction), AWS CLI.

---

## File Map

### Created
```
iac/Makefile
iac/stacks/data/main.tf
iac/stacks/data/variables.tf
iac/stacks/data/dynamodb.tf
iac/stacks/data/s3.tf
iac/stacks/data/outputs.tf
iac/stacks/security/main.tf
iac/stacks/security/variables.tf
iac/stacks/security/secrets.tf
iac/stacks/security/outputs.tf
iac/stacks/evaluations/main.tf
iac/stacks/evaluations/variables.tf
iac/stacks/evaluations/iam.tf
iac/stacks/evaluations/sqs.tf
iac/stacks/evaluations/lambda.tf
iac/stacks/evaluations/eventbridge.tf
iac/stacks/evaluations/outputs.tf
iac/stacks/app/main.tf
iac/stacks/app/variables.tf
iac/stacks/app/ecr.tf
iac/stacks/app/ec2.tf
iac/stacks/app/iam.tf
iac/stacks/app/user_data.sh
iac/stacks/app/outputs.tf
iac/stacks/monitoring/main.tf
iac/stacks/monitoring/variables.tf
iac/stacks/monitoring/cloudwatch.tf
iac/stacks/monitoring/outputs.tf
iac/envs/dev/common.tfvars
iac/envs/dev/data.tfvars
iac/envs/dev/security.tfvars
iac/envs/dev/evaluations.tfvars
iac/envs/dev/app.tfvars
iac/envs/dev/monitoring.tfvars
iac/envs/prod/common.tfvars
iac/envs/prod/data.tfvars
iac/envs/prod/security.tfvars
iac/envs/prod/evaluations.tfvars
iac/envs/prod/app.tfvars
iac/envs/prod/monitoring.tfvars
```

### Deleted
```
iac/terraform-aws/   (entire directory, including all subdirs)
```

---

## Task 1: Create directory skeleton and Makefile

**Files:**
- Create: `iac/Makefile`

- [ ] **Step 1: Create directories**

```bash
mkdir -p iac/stacks/data iac/stacks/security iac/stacks/evaluations \
         iac/stacks/app iac/stacks/monitoring \
         iac/envs/dev iac/envs/prod
```

- [ ] **Step 2: Write `iac/Makefile`**

```makefile
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
STATE_BUCKET := llmops-terraform-state-613884141368
STATE_REGION := ap-south-1

STACKS := data security evaluations app monitoring

VARFLAGS = -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
           -var-file=$(MAKEFILE_DIR)envs/$(ENV)/$(STACK).tfvars

.PHONY: init plan apply destroy output \
        apply-all plan-all destroy-all \
        apply-data apply-security apply-evaluations apply-app apply-monitoring

# ── per-stack targets ──────────────────────────────────────────────────
init:
	@test -n "$(ENV)"   || (echo "Usage: make init ENV=dev STACK=data" && exit 1)
	@test -n "$(STACK)" || (echo "Usage: make init ENV=dev STACK=data" && exit 1)
	terraform -chdir=$(MAKEFILE_DIR)stacks/$(STACK) init \
	  -reconfigure \
	  -backend-config="bucket=$(STATE_BUCKET)" \
	  -backend-config="key=$(ENV)/$(STACK)/terraform.tfstate" \
	  -backend-config="region=$(STATE_REGION)"

plan:
	@$(MAKE) -s init ENV=$(ENV) STACK=$(STACK)
	terraform -chdir=$(MAKEFILE_DIR)stacks/$(STACK) plan $(VARFLAGS)

apply:
	@$(MAKE) -s init ENV=$(ENV) STACK=$(STACK)
	terraform -chdir=$(MAKEFILE_DIR)stacks/$(STACK) apply $(VARFLAGS)

destroy:
	@$(MAKE) -s init ENV=$(ENV) STACK=$(STACK)
	terraform -chdir=$(MAKEFILE_DIR)stacks/$(STACK) destroy $(VARFLAGS)

output:
	@$(MAKE) -s init ENV=$(ENV) STACK=$(STACK)
	terraform -chdir=$(MAKEFILE_DIR)stacks/$(STACK) output -json

# ── orchestrated targets ───────────────────────────────────────────────
apply-data:
	@$(MAKE) -s init ENV=$(ENV) STACK=data
	terraform -chdir=$(MAKEFILE_DIR)stacks/data apply \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/data.tfvars

apply-security:
	@$(MAKE) -s init ENV=$(ENV) STACK=security
	terraform -chdir=$(MAKEFILE_DIR)stacks/security apply \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/security.tfvars

apply-evaluations:
	@$(MAKE) -s init ENV=$(ENV) STACK=data
	$(eval S3_BUCKET     := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket))
	$(eval S3_BUCKET_ARN := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket_arn))
	$(eval CONV_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw conversations_table))
	$(eval EVAL_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw evaluations_table))
	$(eval HITL_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw hitl_table))
	$(eval GOLDEN_TABLE  := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw golden_results_table))
	@$(MAKE) -s init ENV=$(ENV) STACK=evaluations
	terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations apply \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/evaluations.tfvars \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="s3_bucket_arn=$(S3_BUCKET_ARN)" \
	  -var="conversations_table=$(CONV_TABLE)" \
	  -var="evaluations_table=$(EVAL_TABLE)" \
	  -var="hitl_table=$(HITL_TABLE)" \
	  -var="golden_results_table=$(GOLDEN_TABLE)"

apply-app:
	@$(MAKE) -s init ENV=$(ENV) STACK=data
	$(eval S3_BUCKET  := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket))
	@$(MAKE) -s init ENV=$(ENV) STACK=security
	$(eval SECRET_ARN  := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/security output -json | jq -r '.app_secret_arn.value'))
	$(eval SECRET_NAME := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/security output -raw app_secret_name))
	@$(MAKE) -s init ENV=$(ENV) STACK=app
	terraform -chdir=$(MAKEFILE_DIR)stacks/app apply \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/app.tfvars \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="app_secret_arn=$(SECRET_ARN)" \
	  -var="app_secret_name=$(SECRET_NAME)"

apply-monitoring:
	@$(MAKE) -s init ENV=$(ENV) STACK=evaluations
	$(eval EVAL_FN   := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw eval_runner_name))
	$(eval GOLDEN_FN := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw golden_dataset_runner_name))
	$(eval PCA_FN    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw pca_runner_name))
	$(eval INGEST_FN := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw qdrant_ingestion_name))
	@$(MAKE) -s init ENV=$(ENV) STACK=app
	$(eval EC2_ID    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/app output -raw ec2_instance_id))
	@$(MAKE) -s init ENV=$(ENV) STACK=monitoring
	terraform -chdir=$(MAKEFILE_DIR)stacks/monitoring apply \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/monitoring.tfvars \
	  -var="eval_runner_name=$(EVAL_FN)" \
	  -var="golden_dataset_runner_name=$(GOLDEN_FN)" \
	  -var="pca_runner_name=$(PCA_FN)" \
	  -var="qdrant_ingestion_name=$(INGEST_FN)" \
	  -var="ec2_instance_id=$(EC2_ID)"

apply-all: apply-data apply-security apply-evaluations apply-app apply-monitoring

plan-all:
	@echo "NOTE: plan-all requires all stacks applied at least once (terraform output fails on empty state)"
	@$(MAKE) plan ENV=$(ENV) STACK=data
	@$(MAKE) plan ENV=$(ENV) STACK=security
	@$(MAKE) plan ENV=$(ENV) STACK=evaluations
	@$(MAKE) plan ENV=$(ENV) STACK=app
	@$(MAKE) plan ENV=$(ENV) STACK=monitoring

destroy-all:
	@$(MAKE) destroy ENV=$(ENV) STACK=monitoring
	@$(MAKE) destroy ENV=$(ENV) STACK=app
	@$(MAKE) destroy ENV=$(ENV) STACK=evaluations
	@$(MAKE) destroy ENV=$(ENV) STACK=security
	@$(MAKE) destroy ENV=$(ENV) STACK=data
```

- [ ] **Step 3: Verify Makefile parses without error**

```bash
cd iac && make --dry-run apply ENV=dev STACK=data 2>&1 | head -5
```

Expected: Shows terraform init + apply commands, no parse errors.

- [ ] **Step 4: Commit skeleton**

```bash
git add iac/Makefile
git commit -m "feat: add iac/Makefile for multi-stack orchestration"
```

---

## Task 2: Create `stacks/data/` stack

**Files:**
- Create: `iac/stacks/data/main.tf`
- Create: `iac/stacks/data/variables.tf`
- Create: `iac/stacks/data/dynamodb.tf`
- Create: `iac/stacks/data/s3.tf`
- Create: `iac/stacks/data/outputs.tf`

- [ ] **Step 1: Write `iac/stacks/data/main.tf`**

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
```

- [ ] **Step 2: Write `iac/stacks/data/variables.tf`**

```hcl
variable "aws_region" { type = string }
variable "env"        { type = string }
variable "project"    { type = string }

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
  description = "Bucket name; auto-generated from account ID if empty"
  type        = string
  default     = ""
}
```

- [ ] **Step 3: Write `iac/stacks/data/dynamodb.tf`**

```hcl
resource "aws_dynamodb_table" "conversations" {
  name         = var.conversations_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "sk"

  attribute { name = "session_id"; type = "S" }
  attribute { name = "sk";         type = "S" }
  attribute { name = "status";     type = "S" }
  attribute { name = "last_updated_at"; type = "S" }

  global_secondary_index {
    name            = "status-last_updated_at-index"
    hash_key        = "status"
    range_key       = "last_updated_at"
    projection_type = "ALL"
  }

  tags = { Name = var.conversations_table, Project = var.project, Env = var.env }
}

resource "aws_dynamodb_table" "evaluations" {
  name         = var.evaluations_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"
  range_key    = "sk"

  attribute { name = "session_id"; type = "S" }
  attribute { name = "sk";         type = "S" }
  attribute { name = "eval_type";  type = "S" }
  attribute { name = "created_at"; type = "S" }

  global_secondary_index {
    name            = "eval_type-created_at-index"
    hash_key        = "eval_type"
    range_key       = "created_at"
    projection_type = "ALL"
  }

  tags = { Name = var.evaluations_table, Project = var.project, Env = var.env }
}

resource "aws_dynamodb_table" "hitl_queue" {
  name         = var.hitl_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute { name = "pk";           type = "S" }
  attribute { name = "sk";           type = "S" }
  attribute { name = "queue_status"; type = "S" }

  global_secondary_index {
    name            = "queue_status-sk-index"
    hash_key        = "queue_status"
    range_key       = "sk"
    projection_type = "ALL"
  }

  tags = { Name = var.hitl_table, Project = var.project, Env = var.env }
}

resource "aws_dynamodb_table" "golden_results" {
  name         = var.golden_results_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"
  range_key    = "question_id"

  attribute { name = "run_id";      type = "S" }
  attribute { name = "question_id"; type = "S" }

  tags = { Name = var.golden_results_table, Project = var.project, Env = var.env }
}
```

- [ ] **Step 4: Write `iac/stacks/data/s3.tf`**

```hcl
resource "aws_s3_bucket" "documents" {
  bucket = var.s3_bucket_name != "" ? var.s3_bucket_name : "${var.project}-documents-${data.aws_caller_identity.current.account_id}"

  tags = { Name = "${var.project}-documents", Project = var.project, Env = var.env }
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

- [ ] **Step 5: Write `iac/stacks/data/outputs.tf`**

```hcl
output "s3_documents_bucket" {
  value = aws_s3_bucket.documents.id
}
output "s3_documents_bucket_arn" {
  value = aws_s3_bucket.documents.arn
}
output "conversations_table" {
  value = aws_dynamodb_table.conversations.name
}
output "evaluations_table" {
  value = aws_dynamodb_table.evaluations.name
}
output "hitl_table" {
  value = aws_dynamodb_table.hitl_queue.name
}
output "golden_results_table" {
  value = aws_dynamodb_table.golden_results.name
}
```

- [ ] **Step 6: Validate**

```bash
cd iac/stacks/data
terraform init -backend=false
terraform validate
```

Expected output: `Success! The configuration is valid.`

- [ ] **Step 7: Check formatting**

```bash
terraform fmt -check -recursive iac/stacks/data/
```

If it reports drift, fix with: `terraform fmt iac/stacks/data/`

- [ ] **Step 8: Commit**

```bash
git add iac/stacks/data/
git commit -m "feat: add stacks/data (DynamoDB + S3)"
```

---

## Task 3: Create `stacks/security/` stack

**Files:**
- Create: `iac/stacks/security/main.tf`
- Create: `iac/stacks/security/variables.tf`
- Create: `iac/stacks/security/secrets.tf`
- Create: `iac/stacks/security/outputs.tf`

- [ ] **Step 1: Write `iac/stacks/security/main.tf`**

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}
```

- [ ] **Step 2: Write `iac/stacks/security/variables.tf`**

```hcl
variable "aws_region" { type = string }
variable "env"        { type = string }
variable "project"    { type = string }

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
```

- [ ] **Step 3: Write `iac/stacks/security/secrets.tf`**

```hcl
resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.project}/app-secrets"
  description             = "LLMOps application config — Langfuse, Qdrant, and runtime settings"
  recovery_window_in_days = 7

  tags = { Name = "${var.project}-app-secrets", Project = var.project, Env = var.env }
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id

  secret_string = jsonencode({
    MODEL_ID             = var.model_id
    AWS_REGION           = var.aws_region
    QDRANT_HOST          = var.qdrant_host
    QDRANT_PORT          = tostring(var.qdrant_port)
    QDRANT_API_KEY       = var.qdrant_api_key
    QDRANT_COLLECTION    = var.qdrant_collection
    S3_BUCKET_NAME       = var.s3_bucket_name
    LANGFUSE_PUBLIC_KEY  = var.langfuse_public_key
    LANGFUSE_SECRET_KEY  = var.langfuse_secret_key
    LANGFUSE_HOST        = var.langfuse_host
    ENABLE_LANGFUSE      = "true"
    CONVERSATIONS_TABLE  = var.conversations_table
    EVALUATIONS_TABLE    = var.evaluations_table
    HITL_TABLE           = var.hitl_table
    GOLDEN_RESULTS_TABLE = var.golden_results_table
  })
}
```

- [ ] **Step 4: Write `iac/stacks/security/outputs.tf`**

```hcl
output "app_secret_arn" {
  description = "Secrets Manager ARN for app config"
  value       = aws_secretsmanager_secret.app_secrets.arn
  sensitive   = true
}

output "app_secret_name" {
  description = "Secrets Manager secret name (for EC2 user_data)"
  value       = aws_secretsmanager_secret.app_secrets.name
}
```

- [ ] **Step 5: Validate**

```bash
cd iac/stacks/security
terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 6: Commit**

```bash
git add iac/stacks/security/
git commit -m "feat: add stacks/security (Secrets Manager)"
```

---

## Task 4: Create `stacks/evaluations/` stack

**Files:**
- Create: `iac/stacks/evaluations/main.tf`
- Create: `iac/stacks/evaluations/variables.tf`
- Create: `iac/stacks/evaluations/iam.tf`
- Create: `iac/stacks/evaluations/sqs.tf`
- Create: `iac/stacks/evaluations/lambda.tf`
- Create: `iac/stacks/evaluations/eventbridge.tf`
- Create: `iac/stacks/evaluations/outputs.tf`

> **Note on `dist/lambdas.zip`:** Lambda resources reference `${path.module}/../../dist/lambdas.zip`. This resolves to `iac/dist/lambdas.zip` regardless of where `terraform` is invoked from. Ensure `iac/dist/lambdas.zip` exists before running `terraform plan/apply` (it is built by the CI/CD pipeline, not managed by Terraform).

- [ ] **Step 1: Write `iac/stacks/evaluations/main.tf`**

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
```

- [ ] **Step 2: Write `iac/stacks/evaluations/variables.tf`**

```hcl
variable "aws_region" { type = string }
variable "env"        { type = string }
variable "project"    { type = string }

# injected from data stack by Makefile
variable "s3_bucket_name" { type = string }
variable "s3_bucket_arn"  { type = string }
variable "conversations_table"  { type = string }
variable "evaluations_table"    { type = string }
variable "hitl_table"           { type = string }
variable "golden_results_table" { type = string }

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
```

- [ ] **Step 3: Write `iac/stacks/evaluations/iam.tf`**

```hcl
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project}-${var.env}-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = { Project = var.project, Env = var.env }
}

resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "${var.project}-${var.env}-lambda-dynamodb"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan",
        "dynamodb:UpdateItem", "dynamodb:PutItem"
      ]
      Resource = [
        "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.conversations_table}",
        "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.evaluations_table}",
        "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.hitl_table}",
        "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.golden_results_table}"
      ]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "${var.project}-${var.env}-lambda-s3"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket"]
      Resource = [var.s3_bucket_arn, "${var.s3_bucket_arn}/*"]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_sqs" {
  name = "${var.project}-${var.env}-lambda-sqs"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
      Resource = [
        aws_sqs_queue.ingestion.arn,
        aws_sqs_queue.ingestion_dlq.arn
      ]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_bedrock" {
  name = "${var.project}-${var.env}-lambda-bedrock"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
```

- [ ] **Step 4: Write `iac/stacks/evaluations/sqs.tf`**

```hcl
resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "${var.project}-ingestion-dlq"
  message_retention_seconds = 1209600
  tags = { Name = "${var.project}-ingestion-dlq", Project = var.project, Env = var.env }
}

resource "aws_sqs_queue" "ingestion" {
  name                       = "${var.project}-ingestion"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 86400

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 3
  })

  tags = { Name = "${var.project}-ingestion", Project = var.project, Env = var.env }
}

resource "aws_sqs_queue_policy" "ingestion" {
  queue_url = aws_sqs_queue.ingestion.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowS3SendMessage"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.ingestion.arn
      Condition = { ArnLike = { "aws:SourceArn" = var.s3_bucket_arn } }
    }]
  })
}

resource "aws_s3_bucket_notification" "documents_to_sqs" {
  bucket = var.s3_bucket_name

  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".pdf"
  }
  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".txt"
  }
  queue {
    queue_arn     = aws_sqs_queue.ingestion.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".csv"
  }

  depends_on = [aws_sqs_queue_policy.ingestion]
}

resource "aws_lambda_permission" "allow_sqs_ingestion" {
  statement_id  = "AllowSQSTrigger"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.qdrant_ingestion.function_name
  principal     = "sqs.amazonaws.com"
  source_arn    = aws_sqs_queue.ingestion.arn
}

resource "aws_lambda_event_source_mapping" "sqs_to_ingestion" {
  event_source_arn = aws_sqs_queue.ingestion.arn
  function_name    = aws_lambda_function.qdrant_ingestion.arn
  batch_size       = 1
}
```

- [ ] **Step 5: Write `iac/stacks/evaluations/lambda.tf`**

```hcl
locals {
  lambda_zip = "${path.module}/../../dist/lambdas.zip"
}

resource "aws_lambda_function" "eval_runner" {
  function_name    = "eval_runner"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "eval_runner.handler"
  runtime          = "python3.13"
  timeout          = 300
  memory_size      = 512
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)

  environment {
    variables = {
      CONVERSATIONS_TABLE = var.conversations_table
      EVALUATIONS_TABLE   = var.evaluations_table
      HITL_TABLE          = var.hitl_table
      INACTIVITY_MINUTES  = tostring(var.inactivity_minutes)
      RAG_THRESHOLD       = tostring(var.rag_threshold)
      HITL_THRESHOLD      = tostring(var.hitl_threshold)
    }
  }

  tags = { Project = var.project, Env = var.env }
}

resource "aws_lambda_function" "golden_dataset_runner" {
  function_name    = "golden_dataset_runner"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "golden_dataset_runner.handler"
  runtime          = "python3.13"
  timeout          = 600
  memory_size      = 1024
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)

  environment {
    variables = {
      GOLDEN_RESULTS_TABLE  = var.golden_results_table
      GOLDEN_PASS_THRESHOLD = tostring(var.golden_pass_threshold)
      S3_BUCKET_NAME        = var.s3_bucket_name
    }
  }

  tags = { Project = var.project, Env = var.env }
}

resource "aws_lambda_function" "pca_runner" {
  function_name    = "pca_runner"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "pca.handler"
  runtime          = "python3.13"
  timeout          = 300
  memory_size      = 512
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)

  environment {
    variables = {
      CONVERSATIONS_TABLE = var.conversations_table
      EVALUATIONS_TABLE   = var.evaluations_table
      INACTIVITY_MINUTES  = tostring(var.inactivity_minutes)
    }
  }

  tags = { Project = var.project, Env = var.env }
}

resource "aws_lambda_function" "qdrant_ingestion" {
  function_name    = "qdrant_ingestion"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "qdrant_ingestion.lambda_handler"
  runtime          = "python3.13"
  timeout          = 300
  memory_size      = 1024
  filename         = local.lambda_zip
  source_code_hash = filebase64sha256(local.lambda_zip)

  environment {
    variables = {
      QDRANT_HOST       = var.qdrant_host
      QDRANT_PORT       = tostring(var.qdrant_port)
      QDRANT_API_KEY    = var.qdrant_api_key
      QDRANT_COLLECTION = var.qdrant_collection
      S3_BUCKET_NAME    = var.s3_bucket_name
    }
  }

  tags = { Project = var.project, Env = var.env }
}
```

- [ ] **Step 6: Write `iac/stacks/evaluations/eventbridge.tf`**

```hcl
resource "aws_cloudwatch_event_rule" "eval_runner_schedule" {
  name                = "${var.project}-${var.env}-eval-runner-schedule"
  schedule_expression = var.eval_cron_schedule
}

resource "aws_cloudwatch_event_target" "eval_runner_target" {
  rule      = aws_cloudwatch_event_rule.eval_runner_schedule.name
  target_id = "eval_runner"
  arn       = aws_lambda_function.eval_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_eval_runner" {
  statement_id  = "AllowEventBridgeEvalRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.eval_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.eval_runner_schedule.arn
}

resource "aws_cloudwatch_event_rule" "golden_runner_schedule" {
  name                = "${var.project}-${var.env}-golden-runner-schedule"
  schedule_expression = var.golden_cron_schedule
}

resource "aws_cloudwatch_event_target" "golden_runner_target" {
  rule      = aws_cloudwatch_event_rule.golden_runner_schedule.name
  target_id = "golden_dataset_runner"
  arn       = aws_lambda_function.golden_dataset_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_golden_runner" {
  statement_id  = "AllowEventBridgeGoldenRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.golden_dataset_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.golden_runner_schedule.arn
}

resource "aws_cloudwatch_event_rule" "pca_runner_schedule" {
  name                = "${var.project}-${var.env}-pca-runner-schedule"
  schedule_expression = "rate(15 minutes)"
}

resource "aws_cloudwatch_event_target" "pca_runner_target" {
  rule      = aws_cloudwatch_event_rule.pca_runner_schedule.name
  target_id = "pca_runner"
  arn       = aws_lambda_function.pca_runner.arn
}

resource "aws_lambda_permission" "allow_eventbridge_pca_runner" {
  statement_id  = "AllowEventBridgePcaRunner"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pca_runner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.pca_runner_schedule.arn
}
```

- [ ] **Step 7: Write `iac/stacks/evaluations/outputs.tf`**

```hcl
output "eval_runner_name" {
  value = aws_lambda_function.eval_runner.function_name
}
output "golden_dataset_runner_name" {
  value = aws_lambda_function.golden_dataset_runner.function_name
}
output "pca_runner_name" {
  value = aws_lambda_function.pca_runner.function_name
}
output "qdrant_ingestion_name" {
  value = aws_lambda_function.qdrant_ingestion.function_name
}
output "ingestion_queue_url" {
  value = aws_sqs_queue.ingestion.url
}
output "ingestion_queue_arn" {
  value = aws_sqs_queue.ingestion.arn
}
```

- [ ] **Step 8: Validate**

> `terraform validate` does NOT evaluate `filebase64sha256` — that only runs at `plan` time. No zip file needed for validation.

```bash
cd iac/stacks/evaluations
terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 9: Commit**

```bash
git add iac/stacks/evaluations/
git commit -m "feat: add stacks/evaluations (Lambda + SQS + EventBridge + IAM)"
```

---

## Task 5: Create `stacks/app/` stack

**Files:**
- Create: `iac/stacks/app/main.tf`
- Create: `iac/stacks/app/variables.tf`
- Create: `iac/stacks/app/ecr.tf`
- Create: `iac/stacks/app/iam.tf`
- Create: `iac/stacks/app/ec2.tf`
- Create: `iac/stacks/app/user_data.sh`
- Create: `iac/stacks/app/outputs.tf`

- [ ] **Step 1: Write `iac/stacks/app/main.tf`**

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
```

- [ ] **Step 2: Write `iac/stacks/app/variables.tf`**

```hcl
variable "aws_region" { type = string }
variable "env"        { type = string }
variable "project"    { type = string }

variable "ec2_instance_type" {
  type    = string
  default = "t3.medium"
}
variable "ec2_key_name" {
  type    = string
  default = ""
}
variable "ecr_repo_name" {
  type    = string
  default = "llmops-api"
}
variable "app_image_tag" {
  type    = string
  default = "latest"
}

# injected from data stack by Makefile
variable "s3_bucket_name" { type = string }

# injected from security stack by Makefile
variable "app_secret_arn"  { type = string }
variable "app_secret_name" { type = string }
```

- [ ] **Step 3: Write `iac/stacks/app/ecr.tf`**

```hcl
resource "aws_ecr_repository" "api" {
  name                 = var.ecr_repo_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration { scan_on_push = true }

  tags = { Name = var.ecr_repo_name, Project = var.project, Env = var.env }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}
```

- [ ] **Step 4: Write `iac/stacks/app/iam.tf`**

```hcl
resource "aws_iam_role" "ec2_role" {
  name = "${var.project}-${var.env}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })

  tags = { Project = var.project, Env = var.env }
}

resource "aws_iam_role_policy" "ec2_policy" {
  name = "${var.project}-${var.env}-ec2-policy"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerRead"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = [var.app_secret_arn]
      },
      {
        Sid    = "ECRAccess"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken", "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"
        ]
        Resource = "*"
      },
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        Resource = "*"
      },
      {
        Sid    = "S3DocumentsAccess"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.s3_bucket_name}",
          "arn:aws:s3:::${var.s3_bucket_name}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project}-${var.env}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}
```

- [ ] **Step 5: Write `iac/stacks/app/ec2.tf`**

```hcl
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "api_server" {
  name        = "${var.project}-${var.env}-api-sg"
  description = "LLMOps API server security group"

  ingress {
    description = "FastAPI application"
    from_port   = 8000; to_port = 8000; protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "HTTPS"
    from_port   = 443; to_port = 443; protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    description = "SSH"
    from_port   = 22; to_port = 22; protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0; to_port = 0; protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project}-${var.env}-api-sg", Project = var.project, Env = var.env }
}

resource "aws_instance" "api_server" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.ec2_instance_type
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  vpc_security_group_ids = [aws_security_group.api_server.id]
  key_name               = var.ec2_key_name != "" ? var.ec2_key_name : null

  user_data = templatefile("${path.module}/user_data.sh", {
    ecr_url       = aws_ecr_repository.api.repository_url
    aws_region    = var.aws_region
    secret_id     = var.app_secret_name
    app_image_tag = var.app_image_tag
  })

  root_block_device {
    volume_type = "gp3"
    volume_size = 20
    encrypted   = true
  }

  tags = { Name = "${var.project}-${var.env}-api-server", Project = var.project, Env = var.env }
}
```

- [ ] **Step 6: Copy `user_data.sh`**

```bash
cp iac/terraform-aws/user_data.sh iac/stacks/app/user_data.sh
```

The file contents are unchanged — `templatefile` variables `ecr_url`, `aws_region`, `secret_id`, `app_image_tag` are still used.

- [ ] **Step 7: Write `iac/stacks/app/outputs.tf`**

```hcl
output "ec2_instance_id" {
  value = aws_instance.api_server.id
}
output "ec2_public_ip" {
  value = aws_instance.api_server.public_ip
}
output "ecr_repository_url" {
  value = aws_ecr_repository.api.repository_url
}
output "api_endpoint" {
  value = "http://${aws_instance.api_server.public_ip}:8000"
}
```

- [ ] **Step 8: Validate**

```bash
cd iac/stacks/app
terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 9: Commit**

```bash
git add iac/stacks/app/
git commit -m "feat: add stacks/app (ECR + EC2 + IAM)"
```

---

## Task 6: Create `stacks/monitoring/` stack

**Files:**
- Create: `iac/stacks/monitoring/main.tf`
- Create: `iac/stacks/monitoring/variables.tf`
- Create: `iac/stacks/monitoring/cloudwatch.tf`
- Create: `iac/stacks/monitoring/outputs.tf`

- [ ] **Step 1: Write `iac/stacks/monitoring/main.tf`**

```hcl
terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  backend "s3" {}
}

provider "aws" {
  region = var.aws_region
}
```

- [ ] **Step 2: Write `iac/stacks/monitoring/variables.tf`**

```hcl
variable "aws_region" { type = string }
variable "env"        { type = string }
variable "project"    { type = string }

variable "log_retention_days" {
  type    = number
  default = 14
}

# injected from evaluations stack by Makefile
variable "eval_runner_name"           { type = string }
variable "golden_dataset_runner_name" { type = string }
variable "pca_runner_name"            { type = string }
variable "qdrant_ingestion_name"      { type = string }

# injected from app stack by Makefile
variable "ec2_instance_id" { type = string }
```

- [ ] **Step 3: Write `iac/stacks/monitoring/cloudwatch.tf`**

```hcl
resource "aws_cloudwatch_log_group" "eval_runner" {
  name              = "/aws/lambda/${var.eval_runner_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "golden_dataset_runner" {
  name              = "/aws/lambda/${var.golden_dataset_runner_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "pca_runner" {
  name              = "/aws/lambda/${var.pca_runner_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "qdrant_ingestion" {
  name              = "/aws/lambda/${var.qdrant_ingestion_name}"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_dashboard" "llmops" {
  dashboard_name = "${var.project}-${var.env}-overview"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"; x = 0; y = 0; width = 12; height = 6
        properties = {
          title  = "Lambda Invocations"; period = 300; stat = "Sum"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.eval_runner_name],
            ["AWS/Lambda", "Invocations", "FunctionName", var.golden_dataset_runner_name],
            ["AWS/Lambda", "Invocations", "FunctionName", var.pca_runner_name],
            ["AWS/Lambda", "Invocations", "FunctionName", var.qdrant_ingestion_name]
          ]
        }
      },
      {
        type = "metric"; x = 12; y = 0; width = 12; height = 6
        properties = {
          title  = "Lambda Errors"; period = 300; stat = "Sum"
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", var.eval_runner_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.golden_dataset_runner_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.pca_runner_name],
            ["AWS/Lambda", "Errors", "FunctionName", var.qdrant_ingestion_name]
          ]
        }
      },
      {
        type = "metric"; x = 0; y = 6; width = 12; height = 6
        properties = {
          title  = "Lambda Duration (ms)"; period = 300; stat = "Average"
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.eval_runner_name],
            ["AWS/Lambda", "Duration", "FunctionName", var.pca_runner_name]
          ]
        }
      },
      {
        type = "metric"; x = 12; y = 6; width = 12; height = 6
        properties = {
          title  = "Ingestion Queue Depth"; period = 300; stat = "Average"
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "${var.project}-ingestion"],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", "${var.project}-ingestion-dlq"]
          ]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "eval_runner_errors" {
  alarm_name          = "${var.project}-${var.env}-eval-runner-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  dimensions          = { FunctionName = var.eval_runner_name }
}

resource "aws_cloudwatch_metric_alarm" "ingestion_dlq_depth" {
  alarm_name          = "${var.project}-${var.env}-ingestion-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  dimensions          = { QueueName = "${var.project}-ingestion-dlq" }
}

resource "aws_cloudwatch_metric_alarm" "golden_runner_errors" {
  alarm_name          = "${var.project}-${var.env}-golden-runner-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 3600
  statistic           = "Sum"
  threshold           = 3
  treat_missing_data  = "notBreaching"
  dimensions          = { FunctionName = var.golden_dataset_runner_name }
}
```

- [ ] **Step 4: Write `iac/stacks/monitoring/outputs.tf`**

```hcl
output "eval_runner_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.eval_runner_errors.arn
}
output "ingestion_dlq_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.ingestion_dlq_depth.arn
}
output "golden_runner_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.golden_runner_errors.arn
}
output "dashboard_name" {
  value = aws_cloudwatch_dashboard.llmops.dashboard_name
}
```

- [ ] **Step 5: Validate**

```bash
cd iac/stacks/monitoring
terraform init -backend=false
terraform validate
```

Expected: `Success! The configuration is valid.`

- [ ] **Step 6: Commit**

```bash
git add iac/stacks/monitoring/
git commit -m "feat: add stacks/monitoring (CloudWatch alarms + dashboard)"
```

---

## Task 7: Create `envs/` var files

**Files:** All files under `iac/envs/dev/` and `iac/envs/prod/`

- [ ] **Step 1: Write `iac/envs/dev/common.tfvars`**

```hcl
aws_region = "ap-south-1"
env        = "dev"
project    = "llmops"
```

- [ ] **Step 2: Write `iac/envs/dev/data.tfvars`**

```hcl
conversations_table  = "conversations"
evaluations_table    = "evaluations"
hitl_table           = "hitl_queue"
golden_results_table = "golden_results"
s3_bucket_name       = ""
```

- [ ] **Step 3: Write `iac/envs/dev/security.tfvars`**

```hcl
model_id             = "anthropic.claude-haiku-4-5-20251001-v1:0"
qdrant_host          = "localhost"
qdrant_port          = 6333
qdrant_api_key       = ""
qdrant_collection    = "llmops-rag"
langfuse_public_key  = ""
langfuse_secret_key  = ""
langfuse_host        = "https://cloud.langfuse.com"
conversations_table  = "conversations"
evaluations_table    = "evaluations"
hitl_table           = "hitl_queue"
golden_results_table = "golden_results"
s3_bucket_name       = ""
```

- [ ] **Step 4: Write `iac/envs/dev/evaluations.tfvars`**

```hcl
eval_cron_schedule    = "rate(15 minutes)"
golden_cron_schedule  = "rate(1 hour)"
rag_threshold         = 0.6
hitl_threshold        = 0.6
inactivity_minutes    = 15
golden_pass_threshold = 0.7
qdrant_host           = "localhost"
qdrant_port           = 6333
qdrant_api_key        = ""
qdrant_collection     = "llmops-rag"
```

- [ ] **Step 5: Write `iac/envs/dev/app.tfvars`**

```hcl
ec2_instance_type = "t3.medium"
ec2_key_name      = ""
ecr_repo_name     = "llmops-api"
app_image_tag     = "latest"
```

- [ ] **Step 6: Write `iac/envs/dev/monitoring.tfvars`**

```hcl
log_retention_days = 14
```

- [ ] **Step 7: Write prod var files**

Copy dev and adjust. The `prod` files have the same keys but different values for instance type and thresholds:

`iac/envs/prod/common.tfvars`:
```hcl
aws_region = "ap-south-1"
env        = "prod"
project    = "llmops"
```

`iac/envs/prod/data.tfvars` — identical to dev (table names are the same; state isolation is via the S3 key prefix):
```hcl
conversations_table  = "conversations"
evaluations_table    = "evaluations"
hitl_table           = "hitl_queue"
golden_results_table = "golden_results"
s3_bucket_name       = ""
```

`iac/envs/prod/security.tfvars` — same structure as dev; fill in real keys before applying:
```hcl
model_id             = "anthropic.claude-haiku-4-5-20251001-v1:0"
qdrant_host          = "localhost"
qdrant_port          = 6333
qdrant_api_key       = ""
qdrant_collection    = "llmops-rag"
langfuse_public_key  = ""
langfuse_secret_key  = ""
langfuse_host        = "https://cloud.langfuse.com"
conversations_table  = "conversations"
evaluations_table    = "evaluations"
hitl_table           = "hitl_queue"
golden_results_table = "golden_results"
s3_bucket_name       = ""
```

`iac/envs/prod/evaluations.tfvars`:
```hcl
eval_cron_schedule    = "rate(15 minutes)"
golden_cron_schedule  = "rate(1 hour)"
rag_threshold         = 0.6
hitl_threshold        = 0.6
inactivity_minutes    = 15
golden_pass_threshold = 0.7
qdrant_host           = "localhost"
qdrant_port           = 6333
qdrant_api_key        = ""
qdrant_collection     = "llmops-rag"
```

`iac/envs/prod/app.tfvars`:
```hcl
ec2_instance_type = "t3.large"
ec2_key_name      = ""
ecr_repo_name     = "llmops-api"
app_image_tag     = "latest"
```

`iac/envs/prod/monitoring.tfvars`:
```hcl
log_retention_days = 30
```

- [ ] **Step 8: Commit**

```bash
git add iac/envs/
git commit -m "feat: add envs/dev and envs/prod tfvars"
```

---

## Task 8: Validate all stacks end-to-end

- [ ] **Step 1: Format check all stacks**

```bash
terraform fmt -check -recursive iac/stacks/
```

If any files are reported, run `terraform fmt -recursive iac/stacks/` and re-check.

- [ ] **Step 2: Validate each stack**

```bash
for stack in data security evaluations app monitoring; do
  echo "=== Validating $stack ==="
  terraform -chdir=iac/stacks/$stack init -backend=false -upgrade 2>&1 | tail -3
  terraform -chdir=iac/stacks/$stack validate
done
```

Expected for each: `Success! The configuration is valid.`

- [ ] **Step 3: Verify Makefile dry-run for `apply-all`**

```bash
cd iac && make --dry-run apply-all ENV=dev 2>&1
```

Expected: Prints all terraform init + apply commands in dependency order (`data` → `security` → `evaluations` → `app` → `monitoring`). No errors.

- [ ] **Step 4: Commit validation result**

```bash
git add iac/stacks/**/.terraform.lock.hcl
git commit -m "chore: add terraform lock files for all stacks"
```

---

## Task 9: Remove old structure and clean up

> **Warning:** This step deletes `iac/terraform-aws/`. Confirm the new stacks validate correctly (Task 8) before proceeding.

- [ ] **Step 1: Remove old structure**

```bash
rm -rf iac/terraform-aws/
```

- [ ] **Step 2: Verify nothing in the rest of the repo referenced the old paths**

```bash
grep -r "terraform-aws" . --include="*.tf" --include="*.md" --include="*.yml" --include="*.yaml" --include="Makefile" | grep -v ".git"
```

Expected: No matches (or only documentation references you can update).

- [ ] **Step 3: Update `iac/Readme.md` if it references the old structure**

```bash
cat iac/Readme.md
```

Edit the file to reflect the new `stacks/` + `envs/` layout if it documents the old flat structure.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: migrate IaC to modular stacks/envs layout

Replaces flat iac/terraform-aws/ with:
- iac/stacks/{data,security,evaluations,app,monitoring}/
- iac/envs/{dev,prod}/*.tfvars
- iac/Makefile for orchestration

Each stack has independent S3 state keyed as {env}/{stack}/terraform.tfstate.
Cross-stack wiring via Makefile terraform output extraction."
```
