"""api/server.py
FastAPI app instantiation and router registration."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.profile import router as profile_router
from notifications.notify import notify_admin

logger = logging.getLogger(__name__)

app = FastAPI(title="JARVIS", version="0.1.0")

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(profile_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full traceback for the file log, then ping admin.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    notify_admin(type(exc).__name__, str(exc))
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
