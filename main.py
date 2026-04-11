"""main.py
Process entry point. Configures logging and starts the API server.
config.py hard-fails on import if JARVIS_SECRET_KEY is not set."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from config import LOG_PATH, SERVER_HOST, SERVER_PORT


def _configure_logging() -> None:
    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s — %(message)s"
    ))
    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(handler)


def main() -> None:
    _configure_logging()
    logging.getLogger(__name__).info("Starting JARVIS API on %s:%d", SERVER_HOST, SERVER_PORT)
    uvicorn.run("api.server:app", host=SERVER_HOST, port=SERVER_PORT, reload=False)


if __name__ == "__main__":
    main()
