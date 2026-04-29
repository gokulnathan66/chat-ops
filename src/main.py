from fastapi import FastAPI

from src.api.dashboard import router as dashboard_router
from src.api.routes import router as api_router

app = FastAPI(
    title="llmops",
    version="1.0.0",
)

app.include_router(api_router)
app.include_router(dashboard_router)


@app.get("/health")
async def health():
    return {"status": "ok"}