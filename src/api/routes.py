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
        return conversation_svc.list_conversations(status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{session_id}")
async def get_conversation(session_id: str):
    try:
        return conversation_svc.get_conversation(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
