"""api/server.py
FastAPI app instantiation and router registration."""

from fastapi import FastAPI

from api.routes.chat import router as chat_router

app = FastAPI(title="JARVIS", version="0.1.0")

app.include_router(chat_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
