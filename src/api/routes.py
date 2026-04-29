import logging
import uuid

from fastapi import APIRouter
from langfuse import observe

from src.graph.builder import graph
from src.schema.config import GraphInvokeRequest, GraphInvokeResponse

logging.basicConfig(level=logging.INFO)
logging.getLogger("langfuse").setLevel(logging.INFO)

router = APIRouter(prefix="/api", tags=["api"])


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
