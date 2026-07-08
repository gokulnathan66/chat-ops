#!/usr/bin/env bash
# Build Lambda deployment zip: iac/dist/lambdas.zip
#
# Usage: bash scripts/build_lambda_zip.sh
#
# Requires: Docker (for Linux-compatible native binaries)
# Output:   iac/dist/lambdas.zip
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT/iac/dist"
BUILD_DIR="$DIST_DIR/build"

GREEN='\033[0;32m'; NC='\033[0m'
log() { echo -e "${GREEN}[build-lambda]${NC} $1"; }

command -v docker >/dev/null 2>&1 || { echo "Docker is required but not found."; exit 1; }

log "Cleaning previous build..."
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# ── Install Python deps inside a Lambda-compatible container ─────────────────
log "Installing Python 3.12 dependencies for linux/x86_64..."
docker run --rm \
  --platform linux/amd64 \
  -v "$BUILD_DIR:/build" \
  python:3.12-slim \
  bash -c "
    pip install --quiet --no-cache-dir --target /build \
      boto3 \
      langchain \
      langchain-aws \
      langchain-core \
      pydantic \
      'pydantic-settings>=2.0' \
      pypdf \
      qdrant-client
  "

# ── Copy application source ──────────────────────────────────────────────────
log "Copying application code..."

# src/ package (services, tools, schema, setting, states)
cp -r "$ROOT/src" "$BUILD_DIR/src"

# evaluations/ package — kept as a package so internal imports (evaluations.rag_evaluator) resolve
cp -r "$ROOT/evaluations" "$BUILD_DIR/evaluations"

# Lambda handler entry points must be at the zip root (Lambda resolves handler as <module>.<function>)
cp "$ROOT/evaluations/eval_runner.py" "$BUILD_DIR/eval_runner.py"
cp "$ROOT/evaluations/pca.py"         "$BUILD_DIR/pca.py"

# qdrant_ingestion Lambda — lives in data/ but is deployed as a top-level module
cp "$ROOT/data/qdrant_ingestion.py" "$BUILD_DIR/qdrant_ingestion.py"

# ── Zip ───────────────────────────────────────────────────────────────────────
log "Zipping..."
(cd "$BUILD_DIR" && zip -r "$DIST_DIR/lambdas.zip" . \
  --exclude "*.pyc" \
  --exclude "*/__pycache__/*" \
  > /dev/null)

SIZE=$(du -sh "$DIST_DIR/lambdas.zip" | cut -f1)
log "Done: iac/dist/lambdas.zip ($SIZE)"
log "Run 'terraform apply' inside each iac/stacks/* directory to deploy."

rm -rf "$BUILD_DIR"
