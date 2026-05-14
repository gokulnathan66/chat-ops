import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from langfuse import observe

from src.graph.builder import graph
from src.schema.config import GraphInvokeRequest, GraphInvokeResponse
from src.services.conversation import ConversationService

logging.basicConfig(level=logging.INFO)
logging.getLogger("langfuse").setLevel(logging.INFO)

router = APIRouter(prefix="/api", tags=["api"])
conversation_svc = ConversationService()


@router.post("/chat", response_model=GraphInvokeResponse)
@observe()
async def invoke_graph(request: GraphInvokeRequest) -> GraphInvokeResponse:
    session_id = request.session_id or str(uuid.uuid4())

    # If session is in HITL, write user message without invoking the AI
    conv = conversation_svc.get_conversation(session_id)
    if conv["metadata"].get("status") == "hitl_pending":
        turns = conv.get("turns", [])
        next_turn_n = max((int(t["sk"].replace("turn#", "")) for t in turns), default=0) + 1
        conversation_svc.write_user_turn_hitl(session_id, next_turn_n, request.user_query)
        return GraphInvokeResponse(result={
            "user_query": request.user_query,
            "session_id": session_id,
            "route": "hitl_pending",
            "message": "",
            "intent": "hitl_user_reply",
            "retrieved_docs": [],
            "token_usage": {"input": 0, "output": 0},
            "latency_ms": 0,
        })

    result = graph.invoke({
        "name": "llmops",
        "user_query": request.user_query,
        "session_id": session_id,
        "turn": request.turn,
        "messages": request.messages,
        "message": request.message,
    })
    return GraphInvokeResponse(result=result)


@router.get("/conversations")
async def list_conversations(
    status: str = Query(default="active"),
    limit: int = Query(default=50, ge=1, le=200),
):
    try:
        if status == "all":
            sessions: list[dict] = []
            for s in ["active", "hitl_pending", "approval_pending", "complete"]:
                sessions.extend(conversation_svc.list_conversations(status=s, limit=limit))
            sessions.sort(key=lambda x: x.get("last_updated_at", ""), reverse=True)
            return sessions[:limit]
        return conversation_svc.list_conversations(status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{session_id}")
async def get_conversation(session_id: str):
    try:
        return conversation_svc.get_conversation(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
