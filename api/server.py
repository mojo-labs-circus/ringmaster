"""api/server.py
FastAPI app instantiation and router registration."""

from fastapi import FastAPI

from api.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.profile import router as profile_router

app = FastAPI(title="JARVIS", version="0.1.0")

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(profile_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
