"""api/server.py
FastAPI app instantiation and router registration."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.profile import router as profile_router
from config import DB_BACKEND
from db.schema import create_tables
from logging_config import configure_logging
from notifications.notify import notify_admin

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging inside the worker process — required because uvicorn's
    # reload mode spawns a child process that imports the app fresh, and logging
    # set up in main.py only applies to the parent reloader process.
    configure_logging()
    if DB_BACKEND == "sqlite":
        create_tables()
    logger.info("JARVIS worker process started")
    yield


app = FastAPI(title="JARVIS", version="0.1.0", lifespan=lifespan)

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
