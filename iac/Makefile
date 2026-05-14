MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
STATE_BUCKET := llmops-langgraph-terraform
STATE_REGION := ap-south-1

STACKS := data security evaluations app monitoring

VARFLAGS = -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
           -var-file=$(MAKEFILE_DIR)envs/$(ENV)/$(STACK).tfvars

.PHONY: init plan apply destroy output \
        apply-all plan-all destroy-all \
        apply-data apply-security apply-evaluations apply-app apply-monitoring \
        plan-evaluations plan-app plan-monitoring

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

plan-evaluations:
	@$(MAKE) -s init ENV=$(ENV) STACK=data
	$(eval S3_BUCKET     := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket))
	$(eval S3_BUCKET_ARN := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket_arn))
	$(eval CONV_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw conversations_table))
	$(eval EVAL_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw evaluations_table))
	$(eval HITL_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw hitl_table))
	@$(MAKE) -s init ENV=$(ENV) STACK=evaluations
	terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations plan \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/evaluations.tfvars \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="s3_bucket_arn=$(S3_BUCKET_ARN)" \
	  -var="conversations_table=$(CONV_TABLE)" \
	  -var="evaluations_table=$(EVAL_TABLE)" \
	  -var="hitl_table=$(HITL_TABLE)"

apply-evaluations:
	@$(MAKE) -s init ENV=$(ENV) STACK=data
	$(eval S3_BUCKET     := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket))
	$(eval S3_BUCKET_ARN := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket_arn))
	$(eval CONV_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw conversations_table))
	$(eval EVAL_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw evaluations_table))
	$(eval HITL_TABLE    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw hitl_table))
	@$(MAKE) -s init ENV=$(ENV) STACK=evaluations
	terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations apply \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/evaluations.tfvars \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="s3_bucket_arn=$(S3_BUCKET_ARN)" \
	  -var="conversations_table=$(CONV_TABLE)" \
	  -var="evaluations_table=$(EVAL_TABLE)" \
	  -var="hitl_table=$(HITL_TABLE)"

plan-app:
	@$(MAKE) -s init ENV=$(ENV) STACK=data
	$(eval S3_BUCKET   := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket))
	@$(MAKE) -s init ENV=$(ENV) STACK=security
	$(eval SECRET_ARN  := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/security output -json | jq -r '.app_secret_arn.value'))
	$(eval SECRET_NAME := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/security output -raw app_secret_name))
	@$(MAKE) -s init ENV=$(ENV) STACK=app
	terraform -chdir=$(MAKEFILE_DIR)stacks/app plan \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/app.tfvars \
	  -var="s3_bucket_name=$(S3_BUCKET)" \
	  -var="app_secret_arn=$(SECRET_ARN)" \
	  -var="app_secret_name=$(SECRET_NAME)"

apply-app:
	@$(MAKE) -s init ENV=$(ENV) STACK=data
	$(eval S3_BUCKET   := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/data output -raw s3_documents_bucket))
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

plan-monitoring:
	@$(MAKE) -s init ENV=$(ENV) STACK=evaluations
	$(eval EVAL_FN   := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw eval_runner_name))
	$(eval PCA_FN    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw pca_runner_name))
	$(eval INGEST_FN := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw qdrant_ingestion_name))
	@$(MAKE) -s init ENV=$(ENV) STACK=app
	$(eval EC2_ID    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/app output -raw ec2_instance_id))
	@$(MAKE) -s init ENV=$(ENV) STACK=monitoring
	terraform -chdir=$(MAKEFILE_DIR)stacks/monitoring plan \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/monitoring.tfvars \
	  -var="eval_runner_name=$(EVAL_FN)" \
	  -var="pca_runner_name=$(PCA_FN)" \
	  -var="qdrant_ingestion_name=$(INGEST_FN)" \
	  -var="ec2_instance_id=$(EC2_ID)"

apply-monitoring:
	@$(MAKE) -s init ENV=$(ENV) STACK=evaluations
	$(eval EVAL_FN   := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw eval_runner_name))
	$(eval PCA_FN    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw pca_runner_name))
	$(eval INGEST_FN := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/evaluations output -raw qdrant_ingestion_name))
	@$(MAKE) -s init ENV=$(ENV) STACK=app
	$(eval EC2_ID    := $(shell terraform -chdir=$(MAKEFILE_DIR)stacks/app output -raw ec2_instance_id))
	@$(MAKE) -s init ENV=$(ENV) STACK=monitoring
	terraform -chdir=$(MAKEFILE_DIR)stacks/monitoring apply \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/common.tfvars \
	  -var-file=$(MAKEFILE_DIR)envs/$(ENV)/monitoring.tfvars \
	  -var="eval_runner_name=$(EVAL_FN)" \
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
