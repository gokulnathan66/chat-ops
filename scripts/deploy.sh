#!/usr/bin/env bash
# Full deploy script for LLMOps
# Usage: bash scripts/deploy.sh [--infra-only | --app-only | --data-only]
#
# Default: deploys all infrastructure modules then builds and pushes the Docker image.
set -euo pipefail

REGION="${AWS_REGION:-ap-south-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="llmops"
IMAGE_TAG="${IMAGE_TAG:-latest}"
TF_DIR="iac/terraform-aws"
STATE_BUCKET="llmops-terraform-state-${ACCOUNT_ID}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()     { echo -e "${GREEN}[deploy]${NC} $1"; }
section() { echo -e "\n${YELLOW}━━━ $1 ━━━${NC}"; }

INFRA_ONLY=false
APP_ONLY=false
DATA_ONLY=false

for arg in "$@"; do
    case $arg in
        --infra-only) INFRA_ONLY=true ;;
        --app-only)   APP_ONLY=true ;;
        --data-only)  DATA_ONLY=true ;;
    esac
done

# ─── Preflight ────────────────────────────────────────────────────────────────
section "Preflight"

command -v terraform >/dev/null 2>&1 || { echo "terraform not found"; exit 1; }
command -v docker    >/dev/null 2>&1 || { echo "docker not found"; exit 1; }
command -v aws       >/dev/null 2>&1 || { echo "aws cli not found"; exit 1; }

aws sts get-caller-identity >/dev/null 2>&1 || { echo "AWS credentials invalid — run: aws sso login"; exit 1; }
log "AWS account: $ACCOUNT_ID | region: $REGION"

# Ensure Terraform state bucket exists
if ! aws s3 ls "s3://${STATE_BUCKET}" >/dev/null 2>&1; then
    log "Creating Terraform state bucket: $STATE_BUCKET"
    aws s3 mb "s3://${STATE_BUCKET}" --region "$REGION"
    aws s3api put-bucket-versioning \
        --bucket "$STATE_BUCKET" \
        --versioning-configuration Status=Enabled \
        --region "$REGION"
fi

# ─── Terraform: data_managment (DynamoDB) ────────────────────────────────────
if [ "$APP_ONLY" = false ]; then
    section "Terraform: data_managment (DynamoDB tables)"
    terraform -chdir="${TF_DIR}/data_managment" init -upgrade -input=false
    terraform -chdir="${TF_DIR}/data_managment" apply -auto-approve -input=false
    log "DynamoDB tables deployed"
fi

# ─── Terraform: root module (EC2, ECR, SQS, Lambda, IAM, EventBridge) ────────
if [ "$APP_ONLY" = false ] && [ "$DATA_ONLY" = false ]; then
    section "Terraform: root module"

    if [ ! -f "${TF_DIR}/terraform.tfvars" ]; then
        echo "ERROR: ${TF_DIR}/terraform.tfvars not found."
        echo "       Copy terraform.tfvars.example and fill in your values."
        exit 1
    fi

    terraform -chdir="$TF_DIR" init -upgrade -input=false
    terraform -chdir="$TF_DIR" apply -auto-approve -input=false
    log "Root infrastructure deployed"

    ECR_URL=$(terraform -chdir="$TF_DIR" output -raw ecr_repository_url 2>/dev/null || echo "")
fi

# ─── Docker build & push ──────────────────────────────────────────────────────
if [ "$INFRA_ONLY" = false ] && [ "$DATA_ONLY" = false ]; then
    section "Docker build & push"

    ECR_URL="${ECR_URL:-${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}}"
    FULL_IMAGE="${ECR_URL}:${IMAGE_TAG}"

    log "Logging into ECR..."
    aws ecr get-login-password --region "$REGION" \
        | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"

    log "Building image: $FULL_IMAGE"
    docker build -t "$FULL_IMAGE" .

    log "Pushing image..."
    docker push "$FULL_IMAGE"
    log "Image pushed: $FULL_IMAGE"
fi

# ─── Terraform: monitoring & security ────────────────────────────────────────
if [ "$APP_ONLY" = false ] && [ "$DATA_ONLY" = false ]; then
    section "Terraform: monitoring"
    terraform -chdir="${TF_DIR}/monitoring" init -upgrade -input=false
    terraform -chdir="${TF_DIR}/monitoring" apply -auto-approve -input=false

    section "Terraform: security"
    terraform -chdir="${TF_DIR}/security" init -upgrade -input=false
    terraform -chdir="${TF_DIR}/security" apply -auto-approve -input=false
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
section "Deploy complete"

if [ "$DATA_ONLY" = false ] && [ "$APP_ONLY" = false ]; then
    API_ENDPOINT=$(terraform -chdir="$TF_DIR" output -raw api_endpoint 2>/dev/null || echo "check: terraform -chdir=iac/terraform-aws output api_endpoint")
    log "API endpoint : $API_ENDPOINT"
    log "Health check : curl $API_ENDPOINT/health"
fi
