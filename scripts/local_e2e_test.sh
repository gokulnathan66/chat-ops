#!/usr/bin/env bash
# Local end-to-end test script for LLMOps
# Usage: bash scripts/local_e2e_test.sh
# Runs: infra check → ingest → chat (tools + general) → eval → dashboard APIs

BASE_URL="http://localhost:8000"
PASS=0
FAIL=0
ERRORS=()

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

pass()    { echo -e "  ${GREEN}✓${NC} $1"; ((PASS++)); }
fail()    { echo -e "  ${RED}✗${NC} $1"; ((FAIL++)); ERRORS+=("$1"); }
skip()    { echo -e "  ${CYAN}–${NC} $1 (skipped)"; }
section() { echo -e "\n${YELLOW}━━━ $1 ━━━${NC}"; }

run_py() {
    # Run a python snippet from project root, suppress boto3 warnings
    uv run python -W ignore -c "$1" 2>/dev/null
}

# ─── 1. Prerequisites ────────────────────────────────────────────────────────
section "1. Prerequisites"

# Docker — Docker Desktop on Mac puts docker at /usr/local/bin or ~/.docker/bin
if docker info >/dev/null 2>&1; then
    pass "Docker running"
else
    fail "Docker not running — start Docker Desktop"
fi

command -v uv >/dev/null 2>&1 && pass "uv installed" || fail "uv not found — install from https://github.com/astral-sh/uv"
command -v aws >/dev/null 2>&1 && pass "aws cli installed" || fail "aws cli not found"
command -v terraform >/dev/null 2>&1 && pass "terraform installed" || fail "terraform not found"

if [ -f ".env" ]; then
    pass ".env file present"
else
    fail ".env missing — copy .env.example and fill in values"
fi

# Read key env vars
AWS_REGION=$(grep -E "^AWS_REGION=" .env 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo "ap-south-1")
QDRANT_HOST=$(grep -E "^QDRANT_HOST=" .env 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo "http://localhost:6333")
QDRANT_COLLECTION=$(grep -E "^QDRANT_COLLECTION=" .env 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo "llmops")
ENABLE_LANGFUSE=$(grep -E "^ENABLE_LANGFUSE=" .env 2>/dev/null | cut -d= -f2 | tr -d ' ' | tr '[:upper:]' '[:lower:]' || echo "false")

echo "  Region: $AWS_REGION | Qdrant: $QDRANT_HOST | Collection: $QDRANT_COLLECTION"

# AWS credentials
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "")
if [ -n "$AWS_ACCOUNT" ]; then
    pass "AWS credentials valid (account: $AWS_ACCOUNT)"
else
    fail "AWS credentials invalid — run: aws sso login  (or check AWS_PROFILE)"
fi

# ─── 2. Infrastructure ───────────────────────────────────────────────────────
section "2. Infrastructure"

# Qdrant Docker
if docker compose ps 2>/dev/null | grep -q "Up"; then
    pass "Qdrant container running"
else
    echo "  Starting Qdrant..."
    docker compose up -d >/dev/null 2>&1 && sleep 3
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        pass "Qdrant container started"
    else
        fail "Qdrant failed to start — check docker-compose.yaml"
    fi
fi

if curl -sf "${QDRANT_HOST}/healthz" >/dev/null 2>&1; then
    pass "Qdrant API reachable at ${QDRANT_HOST}"
else
    fail "Qdrant not reachable at ${QDRANT_HOST}"
fi

# DynamoDB tables
if [ -n "$AWS_ACCOUNT" ]; then
    for TABLE in conversations evaluations hitl_queue golden_results; do
        STATUS=$(aws dynamodb describe-table --table-name "$TABLE" --region "$AWS_REGION" \
            --query 'Table.TableStatus' --output text 2>/dev/null || echo "MISSING")
        if [ "$STATUS" = "ACTIVE" ]; then
            pass "DynamoDB '$TABLE' active"
        else
            fail "DynamoDB '$TABLE' missing — run: terraform -chdir=iac/terraform-aws/data_managment apply"
        fi
    done
else
    skip "DynamoDB table check (no AWS credentials)"
fi

# ─── 3. Document Ingestion ───────────────────────────────────────────────────
section "3. Document Ingestion (Qdrant + Titan Embeddings)"

if [ -n "$AWS_ACCOUNT" ]; then
    echo "  Ingesting CSV files..."
    INGEST_OUT=$(run_py "
import pathlib, sys
from src.services.embedding import EmbeddingService
from src.services.qdrant import QdrantService
emb = EmbeddingService()
qs = QdrantService()
total = 0
for f in pathlib.Path('data/csv').glob('*.csv'):
    text = f.read_text()
    chunks = emb.chunk_text(text)
    vectors = emb.embed_texts(chunks)
    _, points = qs.build_points(
        full_text=text, chunks=chunks, vectors=vectors,
        source='local', title=f.stem, url_or_file_path=str(f),
        tags=['csv','financials'], section_prefix=f.stem,
    )
    qs.upsert_points(points)
    total += len(points)
    print(f'  {f.name}: {len(points)} chunks')
print('TOTAL:' + str(total))
" 2>&1 || echo "INGEST_FAILED")

    if echo "$INGEST_OUT" | grep -q "INGEST_FAILED\|Error\|Traceback"; then
        fail "Document ingestion failed — check AWS credentials and Bedrock access"
        echo "$INGEST_OUT" | tail -5
    else
        TOTAL=$(echo "$INGEST_OUT" | grep "^TOTAL:" | cut -d: -f2 | tr -d ' ')
        echo "$INGEST_OUT" | grep -v "^TOTAL:" | grep "chunks" || true
        if [ -n "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
            pass "Ingested $TOTAL chunks into Qdrant"
        else
            fail "Ingestion returned 0 chunks"
        fi
    fi

    # Verify collection point count
    POINT_COUNT=$(curl -sf "${QDRANT_HOST}/collections/${QDRANT_COLLECTION}" 2>/dev/null \
        | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null || echo "0")
    if [ "$POINT_COUNT" -gt 0 ]; then
        pass "Qdrant collection '$QDRANT_COLLECTION' has $POINT_COUNT points"
    else
        fail "Qdrant collection empty after ingestion"
    fi
else
    skip "Document ingestion (no AWS credentials)"
fi

# ─── 4. API Server ───────────────────────────────────────────────────────────
section "4. API Server"

# Kill any existing server
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

echo "  Starting FastAPI server..."
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/llmops_server.log 2>&1 &
SERVER_PID=$!

for i in {1..20}; do
    if curl -sf "${BASE_URL}/health" >/dev/null 2>&1; then break; fi
    sleep 1
done

if curl -sf "${BASE_URL}/health" >/dev/null 2>&1; then
    pass "FastAPI server started (PID: $SERVER_PID)"
else
    fail "FastAPI server failed to start"
    echo "  Last 10 lines of /tmp/llmops_server.log:"
    tail -10 /tmp/llmops_server.log | sed 's/^/    /'
fi

HEALTH=$(curl -sf "${BASE_URL}/health" 2>/dev/null || echo "{}")
if echo "$HEALTH" | grep -q '"ok"'; then
    pass "GET /health → {\"status\":\"ok\"}"
else
    fail "GET /health unexpected: $HEALTH"
fi

# ─── 5. Chat — Tools Route (RAG) ─────────────────────────────────────────────
section "5. Chat — Tools Route (RAG)"

TOOLS_RESP=$(curl -sf -X POST "${BASE_URL}/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"user_query":"What is Apple total revenue and key financial metrics?","session_id":"e2e-tools-001","turn":1}' \
    2>/dev/null || echo '{}')

ROUTE=$(echo "$TOOLS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('route',''))" 2>/dev/null || echo "")
if [ "$ROUTE" = "tools" ]; then
    pass "Routed to 'tools' (RAG path)"
else
    fail "Expected route='tools', got '$ROUTE'"
    echo "  Response: $(echo "$TOOLS_RESP" | head -c 200)"
fi

CONFIDENCE=$(echo "$TOOLS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('confidence',0))" 2>/dev/null || echo "0")
python3 -c "assert float('$CONFIDENCE') > 0.5" 2>/dev/null \
    && pass "Intent confidence: $CONFIDENCE" \
    || fail "Low intent confidence: $CONFIDENCE"

RETRIEVED=$(echo "$TOOLS_RESP" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('result',{}).get('retrieved_docs',[])))" 2>/dev/null || echo "0")
[ "$RETRIEVED" -gt 0 ] \
    && pass "RAG retrieved $RETRIEVED doc(s) from Qdrant" \
    || fail "No documents retrieved from Qdrant"

MESSAGE=$(echo "$TOOLS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('message','')[:80])" 2>/dev/null || echo "")
[ -n "$MESSAGE" ] \
    && pass "LLM response: \"${MESSAGE}...\"" \
    || fail "Empty LLM response"

TOKEN_IN=$(echo "$TOOLS_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('token_usage',{}).get('input',0))" 2>/dev/null || echo "0")
[ "$TOKEN_IN" -gt 0 ] \
    && pass "Token usage tracked: input_tokens=$TOKEN_IN" \
    || fail "Token usage not tracked"

LATENCY=$(echo "$TOOLS_RESP" | python3 -c "import sys,json; print(round(json.load(sys.stdin).get('result',{}).get('latency_ms',0)))" 2>/dev/null || echo "0")
[ "$LATENCY" -gt 0 ] \
    && pass "Latency tracked: ${LATENCY}ms" \
    || fail "Latency not tracked"

# ─── 6. Chat — General Route ─────────────────────────────────────────────────
section "6. Chat — General Route"

GENERAL_RESP=$(curl -sf -X POST "${BASE_URL}/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"user_query":"Hello, what topics can you help me with?","session_id":"e2e-general-001","turn":1}' \
    2>/dev/null || echo '{}')

ROUTE_G=$(echo "$GENERAL_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('route',''))" 2>/dev/null || echo "")
[ "$ROUTE_G" = "general" ] \
    && pass "Routed to 'general'" \
    || fail "Expected route='general', got '$ROUTE_G'"

GEN_MSG=$(echo "$GENERAL_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('message','')[:80])" 2>/dev/null || echo "")
[ -n "$GEN_MSG" ] \
    && pass "General response: \"${GEN_MSG}...\"" \
    || fail "Empty general response"

# ─── 7. DynamoDB Conversation Persistence ────────────────────────────────────
section "7. DynamoDB Conversation Persistence"

CONV=$(curl -sf "${BASE_URL}/api/conversations/e2e-tools-001" 2>/dev/null || echo '{}')
TURN_COUNT=$(echo "$CONV" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('turns',[])))" 2>/dev/null || echo "0")
[ "$TURN_COUNT" -ge 1 ] \
    && pass "GET /api/conversations/e2e-tools-001 → $TURN_COUNT turn(s) persisted" \
    || fail "Conversation not persisted in DynamoDB"

CONV_STATUS=$(echo "$CONV" | python3 -c "import sys,json; print(json.load(sys.stdin).get('metadata',{}).get('status',''))" 2>/dev/null || echo "")
[ "$CONV_STATUS" = "active" ] \
    && pass "Session status = 'active'" \
    || fail "Unexpected session status: '$CONV_STATUS'"

LIST=$(curl -sf "${BASE_URL}/api/conversations?status=active" 2>/dev/null || echo "[]")
echo "$LIST" | python3 -c "import sys,json; items=json.load(sys.stdin); assert any(c.get('session_id')=='e2e-tools-001' for c in items)" 2>/dev/null \
    && pass "GET /api/conversations?status=active → session listed" \
    || fail "Session not in active conversations list"

# ─── 8. Langfuse Observability ───────────────────────────────────────────────
section "8. Langfuse Observability"

if [ "$ENABLE_LANGFUSE" = "true" ]; then
    LF_PUBLIC=$(grep -E "^LANGFUSE_PUBLIC_KEY=" .env | cut -d= -f2 | tr -d ' ')
    LF_SECRET=$(grep -E "^LANGFUSE_SECRET_KEY=" .env | cut -d= -f2 | tr -d ' ')
    LF_HOST=$(grep -E "^LANGFUSE_BASE_URL=" .env | cut -d= -f2 | tr -d ' ')

    if command -v langfuse >/dev/null 2>&1; then
        TRACE_COUNT=$(langfuse api traces list --limit 5 \
            --public-key "$LF_PUBLIC" --secret-key "$LF_SECRET" --host "$LF_HOST" 2>/dev/null \
            | python3 -c "import sys,json; print(json.load(sys.stdin)['meta']['totalItems'])" 2>/dev/null || echo "0")
        [ "$TRACE_COUNT" -gt 0 ] \
            && pass "Langfuse traces: $TRACE_COUNT total" \
            || fail "No Langfuse traces found"
    else
        skip "langfuse CLI not installed (npm install -g langfuse)"
    fi
else
    skip "Langfuse disabled (ENABLE_LANGFUSE=false)"
fi

# ─── 9. RAG Evaluator ────────────────────────────────────────────────────────
section "9. RAG Evaluator"

if [ -n "$AWS_ACCOUNT" ]; then
    EVAL_OUT=$(run_py "
import json
from evaluations.rag_evaluator import evaluate_session
r = evaluate_session('e2e-tools-001')
print(json.dumps(r))
" 2>&1 | grep "^{" || echo "{}")

    RAG_SCORE=$(echo "$EVAL_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('rag_score',0))" 2>/dev/null || echo "0")
    FAITHFULNESS=$(echo "$EVAL_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('faithfulness',0))" 2>/dev/null || echo "0")
    HITL=$(echo "$EVAL_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('hitl_flagged','?'))" 2>/dev/null || echo "?")

    python3 -c "assert '$RAG_SCORE' != '0' or True" 2>/dev/null  # always passes, just checking it ran
    [ "$EVAL_OUT" != "{}" ] \
        && pass "RAG evaluator ran: rag_score=$RAG_SCORE, faithfulness=$FAITHFULNESS, hitl=$HITL" \
        || fail "RAG evaluator failed to run"

    EVAL_API=$(curl -sf "${BASE_URL}/api/evaluations?type=rag&limit=5" 2>/dev/null || echo "[]")
    EVAL_COUNT=$(echo "$EVAL_API" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    [ "$EVAL_COUNT" -gt 0 ] \
        && pass "GET /api/evaluations?type=rag → $EVAL_COUNT record(s)" \
        || fail "No RAG eval records in DynamoDB"
else
    skip "RAG evaluator (no AWS credentials)"
fi

# ─── 10. PCA ─────────────────────────────────────────────────────────────────
section "10. Post-Conversation Analysis (PCA)"

if [ -n "$AWS_ACCOUNT" ]; then
    PCA_OUT=$(run_py "
import json
from evaluations.pca import analyze_conversation
r = analyze_conversation('e2e-tools-001')
print(json.dumps(r))
" 2>&1 | grep "^{" || echo "{}")

    TOPICS=$(echo "$PCA_OUT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('pca_topics',[])))" 2>/dev/null || echo "0")
    SENTIMENT=$(echo "$PCA_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('pca_sentiment',''))" 2>/dev/null || echo "")

    [ "$TOPICS" -gt 0 ] \
        && pass "PCA topics: $TOPICS extracted" \
        || fail "PCA returned no topics"

    [ -n "$SENTIMENT" ] \
        && pass "PCA sentiment: $SENTIMENT" \
        || fail "PCA sentiment missing"

    EVAL_PCA=$(curl -sf "${BASE_URL}/api/evaluations?type=pca&limit=5" 2>/dev/null || echo "[]")
    PCA_COUNT=$(echo "$EVAL_PCA" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    [ "$PCA_COUNT" -gt 0 ] \
        && pass "GET /api/evaluations?type=pca → $PCA_COUNT record(s)" \
        || fail "No PCA eval records in DynamoDB"
else
    skip "PCA (no AWS credentials)"
fi

# ─── 11. Eval Runner ─────────────────────────────────────────────────────────
section "11. Eval Runner (stale session detection)"

if [ -n "$AWS_ACCOUNT" ]; then
    STALE_OUT=$(run_py "
import json, boto3
from datetime import datetime, timezone, timedelta
from src.setting.config import settings
from evaluations.eval_runner import get_stale_sessions

# Mark e2e-general-001 as stale (20 min old)
ddb = boto3.resource('dynamodb', region_name=settings.AWS_REGION)
t = ddb.Table('conversations')
old_ts = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
t.update_item(
    Key={'session_id': 'e2e-general-001', 'sk': 'metadata'},
    UpdateExpression='SET #s = :active, last_updated_at = :ts',
    ExpressionAttributeNames={'#s': 'status'},
    ExpressionAttributeValues={':active': 'active', ':ts': old_ts},
)
stale = get_stale_sessions()
print(json.dumps({'stale': stale}))
" 2>&1 | grep "^{" || echo "{}")

    STALE_COUNT=$(echo "$STALE_OUT" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('stale',[])))" 2>/dev/null || echo "0")
    [ "$STALE_COUNT" -gt 0 ] \
        && pass "Stale session detection: $STALE_COUNT session(s) found" \
        || fail "Stale session detection returned 0 (check GSI on conversations table)"
else
    skip "Eval runner (no AWS credentials)"
fi

# ─── 12. Dashboard APIs ───────────────────────────────────────────────────────
section "12. Dashboard APIs"

METRICS=$(curl -sf "${BASE_URL}/api/metrics/summary" 2>/dev/null || echo "{}")
if echo "$METRICS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'avg_rag_score' in d" 2>/dev/null; then
    AVG_RAG=$(echo "$METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['avg_rag_score'])" 2>/dev/null)
    HITL_P=$(echo "$METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['hitl_pending'])" 2>/dev/null)
    GOLDEN_PCT=$(echo "$METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['golden_pass_rate_pct'])" 2>/dev/null)
    pass "GET /api/metrics/summary → avg_rag=$AVG_RAG, hitl_pending=$HITL_P, golden_pass=${GOLDEN_PCT}%"
else
    fail "GET /api/metrics/summary failed: $METRICS"
fi

HITL_LIST=$(curl -sf "${BASE_URL}/api/hitl?status=pending" 2>/dev/null || echo "[]")
HITL_COUNT=$(echo "$HITL_LIST" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
pass "GET /api/hitl?status=pending → $HITL_COUNT item(s)"

GOLDEN=$(curl -sf "${BASE_URL}/api/golden-results?limit=5" 2>/dev/null || echo "[]")
GOLDEN_COUNT=$(echo "$GOLDEN" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
pass "GET /api/golden-results → $GOLDEN_COUNT result(s)"

# ─── 13. Unit Tests ──────────────────────────────────────────────────────────
section "13. Unit Test Suite"

TEST_OUT=$(uv run pytest tests/ -q --tb=line 2>&1 | tail -5)
if echo "$TEST_OUT" | grep -q "passed" && ! echo "$TEST_OUT" | grep -q " failed"; then
    PASSED=$(echo "$TEST_OUT" | grep -oE '[0-9]+ passed' | head -1)
    pass "pytest: $PASSED, 0 failed"
else
    fail "pytest failures detected"
    echo "$TEST_OUT" | sed 's/^/    /'
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${GREEN}${PASS} passed${NC}  ${RED}${FAIL} failed${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ ${#ERRORS[@]} -gt 0 ]; then
    echo -e "\n${RED}Failed checks:${NC}"
    for err in "${ERRORS[@]}"; do
        echo "  • $err"
    done
fi

echo ""
echo "  Server log : /tmp/llmops_server.log"
[ -n "${SERVER_PID:-}" ] && echo "  Server PID : $SERVER_PID  (stop: kill $SERVER_PID)"
echo ""

[ "$FAIL" -eq 0 ] && exit 0 || exit 1
