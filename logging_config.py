"""logging_config.py
Logging setup for the JARVIS server process.

Extracted from main.py so it can be called from both the process entry point
and the FastAPI lifespan — uvicorn's reload mode spawns a child worker process
that imports the app fresh, so logging must be configured inside that process too."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import LOG_BACKUP_COUNT, LOG_MAX_BYTES, LOG_PATH, SERVER_DEV

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s — %(message)s"


def configure_logging() -> None:
    """Attach file and optional console log handlers to the root logger.

    Creates the log directory if it does not exist. The console handler is
    added only when SERVER_DEV is True — production writes to the rotating
    file only. Called from both main.py (parent reloader process) and the
    FastAPI lifespan (worker process) because uvicorn's reload mode spawns a
    fresh child that does not inherit the parent's log handlers.
    """
    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(file_handler)

    # In dev, also emit to stdout so you can watch logs without tailing the file.
    if SERVER_DEV:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logging.root.addHandler(console_handler)
