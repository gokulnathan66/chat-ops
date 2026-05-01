# Terraform Modular Multi-Env Stacks Design

**Date:** 2026-05-02  
**Status:** Approved  

## Overview

Restructure `iac/terraform-aws/` into a two-layer layout: shared Terraform resource files in `stacks/` (written once) and per-environment variable files in `envs/` (values only, no TF code). Each env×stack combination gets its own isolated S3 remote state. A Makefile orchestrates full-environment deploys. No Terragrunt — pure Terraform + Makefile. All stacks standardize on AWS provider `~> 6.0`.

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
│   ├── app/                       <- ECR + EC2 + EC2 IAM role/profile
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── ecr.tf
│   │   ├── ec2.tf
│   │   ├── iam.tf
│   │   ├── user_data.sh
│   │   └── outputs.tf
│   ├── evaluations/               <- Lambda + SQS + EventBridge + Lambda IAM
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── lambda.tf
│   │   ├── sqs.tf
│   │   ├── eventbridge.tf
│   │   ├── iam.tf
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
    │   ├── app.tfvars
    │   ├── evaluations.tfvars
    │   └── monitoring.tfvars
    └── prod/
        ├── common.tfvars
        ├── data.tfvars
        ├── security.tfvars
        ├── app.tfvars
        ├── evaluations.tfvars
        └── monitoring.tfvars
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

Every stack's `main.tf` uses an **empty** `backend "s3" {}` block. The Makefile injects the full backend config at `init` time, including the env-scoped state key.

```hcl
# stacks/data/main.tf (representative)
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
STATE_BUCKET := llmops-terraform-state-613884141368
STATE_REGION := ap-south-1

init:
	terraform -chdir=stacks/$(STACK) init \
	  -reconfigure \
	  -backend-config="bucket=$(STATE_BUCKET)" \
	  -backend-config="key=$(ENV)/$(STACK)/terraform.tfstate" \
	  -backend-config="region=$(STATE_REGION)"
```

The `-reconfigure` flag is required when switching `ENV` on the same stack directory, since the backend key changes between environments.

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

### Var-file resolution

Stack TF files are in `stacks/$(STACK)`; var files are in `envs/$(ENV)/`. The Makefile uses `$(CURDIR)` (the `iac/` directory where `make` is invoked) for unambiguous absolute paths:

```makefile
VARFLAGS = -var-file=$(CURDIR)/envs/$(ENV)/common.tfvars \
           -var-file=$(CURDIR)/envs/$(ENV)/$(STACK).tfvars

plan:
	terraform -chdir=stacks/$(STACK) plan $(VARFLAGS)

apply:
	terraform -chdir=stacks/$(STACK) apply $(VARFLAGS)
```

---

## Cross-Stack Wiring

No `terraform_remote_state`. The Makefile extracts outputs from upstream stacks via `terraform output` and passes them as `-var` flags to downstream stacks.

**evaluations receives from data:**

```makefile
apply-evaluations: apply-data
	$(eval S3_BUCKET    := $(shell terraform -chdir=stacks/data output -raw s3_documents_bucket))
	$(eval CONV_TABLE   := $(shell terraform -chdir=stacks/data output -raw conversations_table))
	$(eval EVAL_TABLE   := $(shell terraform -chdir=stacks/data output -raw evaluations_table))
	$(eval HITL_TABLE   := $(shell terraform -chdir=stacks/data output -raw hitl_table))
	$(eval GOLDEN_TABLE := $(shell terraform -chdir=stacks/data output -raw golden_results_table))
	terraform -chdir=stacks/evaluations apply \
	  $(VARFLAGS) \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="conversations_table=$(CONV_TABLE)" \
	  -var="evaluations_table=$(EVAL_TABLE)" \
	  -var="hitl_table=$(HITL_TABLE)" \
	  -var="golden_results_table=$(GOLDEN_TABLE)"
```

`terraform output` on a `stacks/` directory reads whichever state was last initialized (the last `init` with a specific `key=`). In `apply-all`, the Makefile initializes and applies stacks in order, so outputs always reflect the correct env's state.

**app receives from data + security:**  
`s3_documents_bucket` (from data) and `app_secret_arn` (from security) passed as `-var` flags.

**monitoring receives from app + evaluations:**  
EC2 instance ID (from app) and Lambda function names (from evaluations) passed as `-var` flags.

---

## Variable Strategy

- `envs/{env}/common.tfvars` — env-wide: `aws_region`, `env` (string tag), `project`
- `envs/{env}/{stack}.tfvars` — stack-specific: thresholds, instance types, cron schedules, image tags
- Cross-stack values (ARNs, bucket names, table names, function names) are **never** in tfvars — injected at apply time by the Makefile via `terraform output`

---

## Migration from Current Structure

| Current file | New location |
|---|---|
| `main.tf` (S3 bucket) | `stacks/data/s3.tf` |
| `ec2.tf`, `ecr.tf` + EC2 IAM in `ec2.tf` | `stacks/app/` |
| `user_data.sh` | `stacks/app/user_data.sh` |
| `iam.tf` (Lambda IAM) | `stacks/evaluations/iam.tf` |
| `lambda.tf` | `stacks/evaluations/lambda.tf` |
| `sqs.tf` | `stacks/evaluations/sqs.tf` |
| `event_bridge.tf` | `stacks/evaluations/eventbridge.tf` |
| `cloudwatch.tf` | `stacks/monitoring/cloudwatch.tf` |
| `secrets.tf` (root) | `stacks/security/secrets.tf` |
| `data_managment/dynamodb.tf` | `stacks/data/dynamodb.tf` |
| `evaluations/` (subdir) | merged into `stacks/evaluations/` |
| `security/` (subdir) | merged into `stacks/security/` |
| `monitoring/` (subdir) | merged into `stacks/monitoring/` |
| `terraform.tfvars` (root) | split into `envs/dev/*.tfvars` |

The entire `iac/terraform-aws/` directory is removed and replaced with `iac/stacks/` + `iac/envs/` + `iac/Makefile`.

---

## Independent Operation (without Makefile)

```bash
cd iac
terraform -chdir=stacks/data init \
  -reconfigure \
  -backend-config="bucket=llmops-terraform-state-613884141368" \
  -backend-config="key=dev/data/terraform.tfstate" \
  -backend-config="region=ap-south-1"
terraform -chdir=stacks/data plan \
  -var-file=$(pwd)/envs/dev/common.tfvars \
  -var-file=$(pwd)/envs/dev/data.tfvars
terraform -chdir=stacks/data apply \
  -var-file=$(pwd)/envs/dev/common.tfvars \
  -var-file=$(pwd)/envs/dev/data.tfvars
```

Cross-stack vars must be supplied manually via `-var` when operating standalone.
