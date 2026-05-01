# Terraform Modular Multi-Env Stacks Design

**Date:** 2026-05-02  
**Status:** Approved  

## Overview

Restructure `iac/terraform-aws/` into a multi-environment, multi-stack Terraform layout. Each stack is independently deployable with its own S3 remote state. A root Makefile orchestrates full-environment deploys. No Terragrunt — pure Terraform + Makefile. All stacks standardize on AWS provider `~> 6.0` (the root already locks to 6.41.0; subdirectories currently on 5.x will be upgraded).

---

## Directory Structure

```
iac/
├── Makefile
└── envs/
    ├── dev/
    │   ├── common.tfvars          <- shared: aws_region, env, project
    │   ├── data/                  <- DynamoDB tables + S3 documents bucket
    │   │   ├── main.tf
    │   │   ├── variables.tf
    │   │   ├── terraform.tfvars
    │   │   ├── dynamodb.tf
    │   │   ├── s3.tf
    │   │   └── outputs.tf
    │   ├── security/              <- Secrets Manager
    │   │   ├── main.tf
    │   │   ├── variables.tf
    │   │   ├── terraform.tfvars
    │   │   ├── secrets.tf
    │   │   └── outputs.tf
    │   ├── app/                   <- ECR + EC2 + EC2 IAM role/profile
    │   │   ├── main.tf
    │   │   ├── variables.tf
    │   │   ├── terraform.tfvars
    │   │   ├── ecr.tf
    │   │   ├── ec2.tf
    │   │   ├── iam.tf
    │   │   ├── user_data.sh       <- EC2 bootstrap script (copied from current root)
    │   │   └── outputs.tf
    │   ├── evaluations/           <- Lambda + SQS + EventBridge + Lambda IAM
    │   │   ├── main.tf
    │   │   ├── variables.tf
    │   │   ├── terraform.tfvars
    │   │   ├── lambda.tf
    │   │   ├── sqs.tf
    │   │   ├── eventbridge.tf
    │   │   ├── iam.tf
    │   │   └── outputs.tf
    │   └── monitoring/            <- CloudWatch alarms
    │       ├── main.tf
    │       ├── variables.tf
    │       ├── terraform.tfvars
    │       ├── cloudwatch.tf
    │       └── outputs.tf
    └── prod/
        └── (same structure as dev, different tfvars values)
```

---

## Stack Responsibilities

| Stack | Resources | State Key |
|-------|-----------|-----------|
| `data` | DynamoDB (conversations, evaluations, hitl_queue, golden_results) + S3 documents bucket | `{env}/data/terraform.tfstate` |
| `security` | Secrets Manager (app config secrets) | `{env}/security/terraform.tfstate` |
| `app` | ECR repository + EC2 instance + EC2 IAM role/profile + security group | `{env}/app/terraform.tfstate` |
| `evaluations` | Lambda (eval_runner, golden_dataset_runner, pca_runner) + SQS (ingestion + DLQ) + EventBridge schedules + Lambda IAM roles | `{env}/evaluations/terraform.tfstate` |
| `monitoring` | CloudWatch alarms | `{env}/monitoring/terraform.tfstate` |

---

## Backend Configuration

Every stack's `main.tf` uses an **empty** `backend "s3" {}` block (partial backend config). The Makefile provides the full backend at `init` time via `-backend-config` flags.

```hcl
# envs/dev/data/main.tf (representative)
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

```makefile
# Makefile — backend config injected at init time
STATE_BUCKET := llmops-terraform-state-613884141368
STATE_REGION := ap-south-1

init:
	terraform -chdir=envs/$(ENV)/$(STACK) init \
	  -backend-config="bucket=$(STATE_BUCKET)" \
	  -backend-config="key=$(ENV)/$(STACK)/terraform.tfstate" \
	  -backend-config="region=$(STATE_REGION)"
```

State bucket name lives in exactly one place: the Makefile. State keys follow the pattern `{env}/{stack}/terraform.tfstate`.

---

## Makefile Targets

### Per-stack (independent operation)

```makefile
make init    ENV=dev  STACK=data
make plan    ENV=dev  STACK=app
make apply   ENV=dev  STACK=security
make destroy ENV=dev  STACK=monitoring
make output  ENV=dev  STACK=data        # prints all outputs as JSON
```

### Full-environment orchestration

```makefile
make apply-all    ENV=dev    # applies all 5 stacks in dependency order
make plan-all     ENV=dev
make destroy-all  ENV=dev    # destroys in reverse dependency order
```

Dependency order: `data` -> `security` -> `app` -> `evaluations` -> `monitoring`

---

## Cross-Stack Wiring

No `terraform_remote_state`. The Makefile extracts outputs from upstream stacks via `terraform output` and passes them as `-var` flags to downstream stacks.

**evaluations receives from data:**

```makefile
apply-evaluations: apply-data
	$(eval S3_BUCKET    := $(shell terraform -chdir=envs/$(ENV)/data output -raw s3_documents_bucket))
	$(eval CONV_TABLE   := $(shell terraform -chdir=envs/$(ENV)/data output -raw conversations_table))
	$(eval EVAL_TABLE   := $(shell terraform -chdir=envs/$(ENV)/data output -raw evaluations_table))
	$(eval HITL_TABLE   := $(shell terraform -chdir=envs/$(ENV)/data output -raw hitl_table))
	$(eval GOLDEN_TABLE := $(shell terraform -chdir=envs/$(ENV)/data output -raw golden_results_table))
	terraform -chdir=envs/$(ENV)/evaluations apply \
	  -var-file=../common.tfvars \
	  -var-file=./terraform.tfvars \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="conversations_table=$(CONV_TABLE)" \
	  -var="evaluations_table=$(EVAL_TABLE)" \
	  -var="hitl_table=$(HITL_TABLE)" \
	  -var="golden_results_table=$(GOLDEN_TABLE)"
```

**app receives from data + security:**

The `app` stack receives `s3_documents_bucket` from `data` and `app_secret_arn` from `security` (for the EC2 IAM policy and user_data template).

**monitoring receives from app + evaluations:**

The `monitoring` stack receives the EC2 instance ID from `app` and Lambda function names from `evaluations` to target CloudWatch alarms correctly.

---

## Variable Strategy

- `envs/{env}/common.tfvars` — env-wide values: `aws_region`, `env` (string tag), project name
- `envs/{env}/{stack}/terraform.tfvars` — stack-specific values (thresholds, instance types, cron schedules)
- Makefile always passes both: `-var-file=../common.tfvars -var-file=./terraform.tfvars`
- Cross-stack values (ARNs, bucket names, table names, function names) are **never** hardcoded in tfvars — they come from `terraform output` at apply time

---

## Migration from Current Structure

The current `iac/terraform-aws/` flat layout will be replaced. Resources map to new stacks as follows:

| Current file | New stack |
|---|---|
| `main.tf` (S3 bucket) | `data/s3.tf` |
| `ec2.tf`, `ecr.tf` + EC2 IAM in `ec2.tf` | `app/` |
| `user_data.sh` | `app/user_data.sh` |
| `iam.tf` (Lambda IAM) | `evaluations/iam.tf` |
| `lambda.tf` | `evaluations/lambda.tf` |
| `sqs.tf` | `evaluations/sqs.tf` |
| `event_bridge.tf` | `evaluations/eventbridge.tf` |
| `cloudwatch.tf` | `monitoring/cloudwatch.tf` |
| `secrets.tf` (root) | `security/secrets.tf` |
| `data_managment/dynamodb.tf` | `data/dynamodb.tf` |
| `evaluations/` (subdir) | merged into `evaluations/` stack |
| `security/` (subdir) | merged into `security/` stack |
| `monitoring/` (subdir) | merged into `monitoring/` stack |

The subdirectories (`data_managment/`, `evaluations/`, `security/`, `monitoring/`) and the root flat files are removed. Only `envs/` and `Makefile` remain under `iac/`. The `.terraform/` cache directories and `.terraform.lock.hcl` files from the old structure are also deleted.

---

## Independent Operation

Any stack can be operated without the Makefile:

```bash
cd iac/envs/dev/data
terraform init \
  -backend-config="bucket=llmops-terraform-state-613884141368" \
  -backend-config="key=dev/data/terraform.tfstate" \
  -backend-config="region=ap-south-1"
terraform plan -var-file=../common.tfvars -var-file=./terraform.tfvars
terraform apply -var-file=../common.tfvars -var-file=./terraform.tfvars
```

Cross-stack vars (ARNs, table names) must be supplied manually via `-var` when operating standalone. The Makefile automates this for `apply-all`.
