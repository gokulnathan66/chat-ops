from typing import Any
from src.schema.config import GraphInvokeRequest, GraphInvokeResponse
from fastapi import APIRouter
from pydantic import BaseModel, Field
from langfuse import observe
import logging
from src.graph.builder import graph



logging.basicConfig(level=logging.INFO)
logging.getLogger("langfuse").setLevel(logging.INFO)

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/chat", response_model=GraphInvokeResponse)
@observe()
async def invoke_graph(request: GraphInvokeRequest):
    result = graph.invoke(request.model_dump())
    return GraphInvokeResponse(result=result)
