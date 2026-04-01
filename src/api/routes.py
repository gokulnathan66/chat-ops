from typing import Any
from src.schema.config import GraphInvokeRequest, GraphInvokeResponse
from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.graph.builder import graph


router = APIRouter(prefix="/api", tags=["api"])


@router.post("/chat", response_model=GraphInvokeResponse)
async def invoke_graph(request: GraphInvokeRequest):
    result = graph.invoke(request.model_dump())
    return GraphInvokeResponse(result=result)