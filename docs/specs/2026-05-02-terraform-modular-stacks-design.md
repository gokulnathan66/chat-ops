# Terraform Modular Multi-Env Stacks Design

**Date:** 2026-05-02  
**Status:** Approved  

## Overview

Restructure `iac/terraform-aws/` into a two-layer layout: shared Terraform resource files in `stacks/` (written once) and per-environment variable files in `envs/` (values only, no TF code). Each env×stack combination gets its own isolated S3 remote state. A Makefile orchestrates full-environment deploys. No Terragrunt — pure Terraform + Makefile. All stacks standardize on AWS provider `~> 6.0` (upgraded from `~> 5.0` — see provider migration notes below).

---

## Directory Structure

```
iac/
├── Makefile
├── stacks/                        <- TF resource files live here ONCE
│   ├── data/                      <- DynamoDB tables + S3 documents bucket
│   │   ├── main.tf                (empty backend "s3" block)
│   │   ├── variables.tf
│   │   ├── dynamodb.tf
│   │   ├── s3.tf
│   │   └── outputs.tf
│   ├── security/                  <- Secrets Manager
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── secrets.tf
│   │   └── outputs.tf
│   ├── evaluations/               <- SQS + Lambda (all 4) + S3 notification + EventBridge + IAM
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── sqs.tf                 (queues + queue policy + s3 bucket notification)
│   │   ├── lambda.tf              (eval_runner, golden_dataset_runner, pca_runner, qdrant_ingestion)
│   │   ├── eventbridge.tf
│   │   ├── iam.tf
│   │   └── outputs.tf
│   ├── app/                       <- ECR + EC2 + EC2 IAM role/profile
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── ecr.tf
│   │   ├── ec2.tf
│   │   ├── iam.tf
│   │   ├── user_data.sh
│   │   └── outputs.tf
│   └── monitoring/                <- CloudWatch alarms
│       ├── main.tf
│       ├── variables.tf
│       ├── cloudwatch.tf
│       └── outputs.tf
└── envs/                          <- only .tfvars, no TF code
    ├── dev/
    │   ├── common.tfvars          <- shared: aws_region, env, project
    │   ├── data.tfvars
    │   ├── security.tfvars
    │   ├── evaluations.tfvars
    │   ├── app.tfvars
    │   └── monitoring.tfvars
    └── prod/
        ├── common.tfvars
        ├── data.tfvars
        ├── security.tfvars
        ├── evaluations.tfvars
        ├── app.tfvars
        └── monitoring.tfvars
```

---

## Stack Responsibilities

| Stack | Resources | State Key |
|-------|-----------|-----------|
| `data` | DynamoDB (conversations, evaluations, hitl_queue, golden_results) + S3 documents bucket | `{env}/data/terraform.tfstate` |
| `security` | Secrets Manager (app config secrets) | `{env}/security/terraform.tfstate` |
| `evaluations` | SQS (ingestion + DLQ) + SQS queue policy + S3 bucket notification + Lambda (eval_runner, golden_dataset_runner, pca_runner, **qdrant_ingestion**) + EventBridge schedules + Lambda IAM role | `{env}/evaluations/terraform.tfstate` |
| `app` | ECR repository + EC2 instance + EC2 IAM role/profile + security group | `{env}/app/terraform.tfstate` |
| `monitoring` | CloudWatch alarms | `{env}/monitoring/terraform.tfstate` |

**Why `evaluations` owns the S3 bucket notification and `qdrant_ingestion`:**  
`aws_s3_bucket_notification` references both the S3 bucket (from `data`) and the SQS queue (from `evaluations`). Splitting it would require a circular dependency. The notification and `qdrant_ingestion` are ingestion concerns — they naturally belong with the queue they service. The `data` stack exports the bucket ARN and ID as outputs; `evaluations` receives them as variables.

---

## Dependency Order

```
data  ──┐
        ├──> evaluations ──┐
security ──> app           ├──> monitoring
```

Linear apply order: `data` → `security` → `evaluations` → `app` → `monitoring`  
Linear destroy order (reverse): `monitoring` → `app` → `evaluations` → `security` → `data`

`evaluations` and `app` do not depend on each other, so either ordering between them is valid. The linear order above is used for simplicity.

---

## Backend Configuration

Every stack's `main.tf` uses an **empty** `backend "s3" {}` block (partial backend config). The Makefile injects the full backend at `init` time.

> **Pre-requisite:** The state bucket (`llmops-langgraph-terraform`) must exist before running any `make` target. It is not managed by these stacks — create it once manually or via a bootstrap script before first use.

```hcl
# stacks/data/main.tf (representative — all stacks identical except stack name)
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

The `-reconfigure` flag is required when switching `ENV` on the same stack directory, since the backend key changes between environments.

---

## common.tfvars Convention

Every stack's `variables.tf` **must** declare these three variables (they come from `common.tfvars`):

```hcl
variable "aws_region" { type = string }
variable "env"        { type = string }  # "dev" | "prod"
variable "project"    { type = string }  # "llmops"
```

If any stack omits these declarations, Terraform will error with "no variable declaration found."

---

## Required Outputs Per Stack

These are the outputs each stack must expose for downstream cross-stack wiring.

### `data` outputs (`stacks/data/outputs.tf`)

| Output name | Value |
|---|---|
| `s3_documents_bucket` | `aws_s3_bucket.documents.id` (bucket name) |
| `s3_documents_bucket_arn` | `aws_s3_bucket.documents.arn` |
| `conversations_table` | DynamoDB table name |
| `evaluations_table` | DynamoDB table name |
| `hitl_table` | DynamoDB table name |
| `golden_results_table` | DynamoDB table name |

### `security` outputs (`stacks/security/outputs.tf`)

| Output name | Value | Note |
|---|---|---|
| `app_secret_arn` | `aws_secretsmanager_secret.app_secrets.arn` | **sensitive = true** |
| `app_secret_name` | `aws_secretsmanager_secret.app_secrets.name` | |

### `evaluations` outputs (`stacks/evaluations/outputs.tf`)

| Output name | Value |
|---|---|
| `eval_runner_name` | `aws_lambda_function.eval_runner.function_name` |
| `golden_dataset_runner_name` | `aws_lambda_function.golden_dataset_runner.function_name` |
| `pca_runner_name` | `aws_lambda_function.pca_runner.function_name` |
| `qdrant_ingestion_name` | `aws_lambda_function.qdrant_ingestion.function_name` |
| `ingestion_queue_url` | `aws_sqs_queue.ingestion.url` |
| `ingestion_queue_arn` | `aws_sqs_queue.ingestion.arn` |

### `app` outputs (`stacks/app/outputs.tf`)

| Output name | Value |
|---|---|
| `ec2_instance_id` | `aws_instance.api_server.id` |
| `ec2_public_ip` | `aws_instance.api_server.public_ip` |
| `ecr_repository_url` | `aws_ecr_repository.api.repository_url` |
| `api_endpoint` | `http://${aws_instance.api_server.public_ip}:8000` |

### `monitoring` outputs

No downstream consumers. Outputs are informational only (alarm ARNs, etc.).

---

## Makefile Design

### Var-file resolution

`$(MAKEFILE_DIR)` expands to the directory containing the Makefile regardless of where `make` is invoked from (fixes the `$(CURDIR)` invocation-directory bug):

```makefile
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
STATE_BUCKET := llmops-langgraph-terraform
STATE_REGION := ap-south-1

VARFLAGS = -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
           -var-file=$(MAKEFILE_DIR)envs/$(ENV)/$(STACK).tfvars
```

### Per-stack targets

```makefile
init:
	terraform -chdir=stacks/$(STACK) init \
	  -reconfigure \
	  -backend-config="bucket=$(STATE_BUCKET)" \
	  -backend-config="key=$(ENV)/$(STACK)/terraform.tfstate" \
	  -backend-config="region=$(STATE_REGION)"

plan:
	@$(MAKE) init ENV=$(ENV) STACK=$(STACK)
	terraform -chdir=stacks/$(STACK) plan $(VARFLAGS)

apply:
	@$(MAKE) init ENV=$(ENV) STACK=$(STACK)
	terraform -chdir=stacks/$(STACK) apply $(VARFLAGS)

destroy:
	@$(MAKE) init ENV=$(ENV) STACK=$(STACK)
	terraform -chdir=stacks/$(STACK) destroy $(VARFLAGS)

output:
	@$(MAKE) init ENV=$(ENV) STACK=$(STACK)
	terraform -chdir=stacks/$(STACK) output -json
```

Usage: `make apply ENV=dev STACK=data`

### Full-environment targets

```makefile
apply-all: apply-data apply-security apply-evaluations apply-app apply-monitoring

plan-all:
	@echo "NOTE: plan-all requires all stacks to have been applied at least once."
	@echo "      terraform output will fail on empty state."
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

---

## Cross-Stack Wiring (full Makefile snippets)

`terraform output` reads the state of whichever backend key was last initialized in that stack directory. In `apply-all`, stacks are initialized in order, so each `terraform output` call reflects the correct env's state.

### `apply-evaluations` (receives from `data`)

```makefile
apply-evaluations:
	@$(MAKE) init ENV=$(ENV) STACK=data
	$(eval S3_BUCKET     := $(shell terraform -chdir=stacks/data output -raw s3_documents_bucket))
	$(eval S3_BUCKET_ARN := $(shell terraform -chdir=stacks/data output -raw s3_documents_bucket_arn))
	$(eval CONV_TABLE    := $(shell terraform -chdir=stacks/data output -raw conversations_table))
	$(eval EVAL_TABLE    := $(shell terraform -chdir=stacks/data output -raw evaluations_table))
	$(eval HITL_TABLE    := $(shell terraform -chdir=stacks/data output -raw hitl_table))
	$(eval GOLDEN_TABLE  := $(shell terraform -chdir=stacks/data output -raw golden_results_table))
	@$(MAKE) init ENV=$(ENV) STACK=evaluations
	terraform -chdir=stacks/evaluations apply \
	  $(VARFLAGS) \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="s3_bucket_arn=$(S3_BUCKET_ARN)" \
	  -var="conversations_table=$(CONV_TABLE)" \
	  -var="evaluations_table=$(EVAL_TABLE)" \
	  -var="hitl_table=$(HITL_TABLE)" \
	  -var="golden_results_table=$(GOLDEN_TABLE)"
```

### `apply-app` (receives from `data` + `security`)

> **Sensitive output note:** `app_secret_arn` is marked `sensitive = true` in Terraform. `terraform output -raw` fails on sensitive values. Use `-json` piped through `jq` instead.

```makefile
apply-app:
	@$(MAKE) init ENV=$(ENV) STACK=data
	$(eval S3_BUCKET  := $(shell terraform -chdir=stacks/data output -raw s3_documents_bucket))
	@$(MAKE) init ENV=$(ENV) STACK=security
	$(eval SECRET_ARN := $(shell terraform -chdir=stacks/security output -json | jq -r '.app_secret_arn.value'))
	@$(MAKE) init ENV=$(ENV) STACK=app
	terraform -chdir=stacks/app apply \
	  $(VARFLAGS) \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="app_secret_arn=$(SECRET_ARN)"
```

`jq` must be installed. `terraform output -json` on a sensitive output returns the value when invoked locally (it does not redact in JSON mode when the caller is the state owner).

### `apply-monitoring` (receives from `evaluations` + `app`)

```makefile
apply-monitoring:
	@$(MAKE) init ENV=$(ENV) STACK=evaluations
	$(eval EVAL_FN    := $(shell terraform -chdir=stacks/evaluations output -raw eval_runner_name))
	$(eval GOLDEN_FN  := $(shell terraform -chdir=stacks/evaluations output -raw golden_dataset_runner_name))
	$(eval PCA_FN     := $(shell terraform -chdir=stacks/evaluations output -raw pca_runner_name))
	@$(MAKE) init ENV=$(ENV) STACK=app
	$(eval EC2_ID     := $(shell terraform -chdir=stacks/app output -raw ec2_instance_id))
	@$(MAKE) init ENV=$(ENV) STACK=monitoring
	terraform -chdir=stacks/monitoring apply \
	  $(VARFLAGS) \
	  -var="eval_runner_name=$(EVAL_FN)" \
	  -var="golden_dataset_runner_name=$(GOLDEN_FN)" \
	  -var="pca_runner_name=$(PCA_FN)" \
	  -var="ec2_instance_id=$(EC2_ID)"
```

---

## `monitoring` Stack Variables

`stacks/monitoring/variables.tf` must declare (in addition to the three `common.tfvars` vars):

```hcl
variable "eval_runner_name"            { type = string }
variable "golden_dataset_runner_name"  { type = string }
variable "pca_runner_name"             { type = string }
variable "ec2_instance_id"             { type = string }
```

`cloudwatch.tf` uses these instead of hardcoded function/instance names.

---

## Variable Strategy

- `envs/{env}/common.tfvars` — `aws_region`, `env`, `project` (all stacks declare these)
- `envs/{env}/{stack}.tfvars` — stack-specific: thresholds, instance types, cron schedules, image tags, Qdrant config
- Cross-stack values (ARNs, bucket names/ARNs, table names, function names, instance IDs) are **never** in tfvars — injected at apply time by the Makefile via `terraform output`

---

## AWS Provider 6.x Migration Notes

All stacks upgrade from `~> 5.0` to `~> 6.0`. Key breaking changes to verify during implementation:

| Area | Change |
|---|---|
| `aws_s3_bucket` sub-resources | `aws_s3_bucket_acl` removed; use `aws_s3_bucket_ownership_controls`. Verify all S3 bucket config resources still compile. |
| EventBridge | `aws_cloudwatch_event_rule` / `aws_cloudwatch_event_target` still supported in 6.x but `aws_scheduler_schedule` is the modern alternative. Existing resources should migrate as-is unless you want to modernize. |
| Default tags | Provider-level `default_tags` behavior changed; if added later, verify no tag conflicts. |
| IAM role policies | `aws_iam_role_policy` inline policy syntax unchanged — no action needed. |
| Resource renames | Run `terraform plan` after upgrading to see any deprecation warnings before applying. |

Run `terraform init -upgrade` in each stack after changing the provider constraint to pull 6.x.

---

## Migration from Current Structure

| Current file | New location | Notes |
|---|---|---|
| `main.tf` (S3 bucket) | `stacks/data/s3.tf` | |
| `ec2.tf`, `ecr.tf` + EC2 IAM in `ec2.tf` | `stacks/app/` | |
| `user_data.sh` | `stacks/app/user_data.sh` | |
| `iam.tf` (Lambda IAM) | `stacks/evaluations/iam.tf` | Covers all 4 Lambdas |
| `lambda.tf` (3 eval Lambdas) | `stacks/evaluations/lambda.tf` | |
| `sqs.tf` (SQS queues + policy + S3 notification + qdrant_ingestion) | `stacks/evaluations/sqs.tf` + `stacks/evaluations/lambda.tf` | S3 bucket id/arn received as `-var` |
| `event_bridge.tf` | `stacks/evaluations/eventbridge.tf` | |
| `cloudwatch.tf` | `stacks/monitoring/cloudwatch.tf` | Parameterize function/instance names |
| `secrets.tf` (root) | `stacks/security/secrets.tf` | |
| `data_managment/dynamodb.tf` | `stacks/data/dynamodb.tf` | |
| `data_managment/outputs.tf` | `stacks/data/outputs.tf` | Add 4 missing outputs (see Required Outputs) |
| `evaluations/` (subdir) | merged into `stacks/evaluations/` | Consolidate with root evaluations resources |
| `security/` (subdir) | merged into `stacks/security/` | |
| `monitoring/` (subdir) | merged into `stacks/monitoring/` | |
| `terraform.tfvars` (root) | split into `envs/dev/*.tfvars` | |

The entire `iac/terraform-aws/` directory is removed. The `.terraform/` cache dirs and `.terraform.lock.hcl` files from the old structure are deleted (new lock files will be generated per stack under `stacks/`).

---

## Independent Operation (without Makefile)

All `make` commands must be run from the `iac/` directory (where the Makefile lives). If invoking terraform directly, run from the repo root and use absolute paths:

```bash
cd /path/to/repo/iac

terraform -chdir=stacks/data init \
  -reconfigure \
  -backend-config="bucket=llmops-langgraph-terraform" \
  -backend-config="key=dev/data/terraform.tfstate" \
  -backend-config="region=ap-south-1"

terraform -chdir=stacks/data plan \
  -var-file=$(pwd)/envs/dev/common.tfvars \
  -var-file=$(pwd)/envs/dev/data.tfvars

terraform -chdir=stacks/data apply \
  -var-file=$(pwd)/envs/dev/common.tfvars \
  -var-file=$(pwd)/envs/dev/data.tfvars
```

When operating `evaluations`, `app`, or `monitoring` standalone, cross-stack vars must be supplied manually:

```bash
terraform -chdir=stacks/evaluations apply \
  -var-file=$(pwd)/envs/dev/common.tfvars \
  -var-file=$(pwd)/envs/dev/evaluations.tfvars \
  -var="s3_bucket_name=llmops-documents-613884141368" \
  -var="s3_bucket_arn=arn:aws:s3:::llmops-documents-613884141368" \
  -var="conversations_table=conversations" \
  # ... etc
```
