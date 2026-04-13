"""main.py
Process entry point. Configures logging and starts the API server.
config.py hard-fails on import if JARVIS_SECRET_KEY is not set."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import uvicorn

from config import LOG_PATH, SERVER_DEV, SERVER_HOST, SERVER_PORT

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s — %(message)s"


def _configure_logging() -> None:
    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))

    logging.root.setLevel(logging.INFO)
    logging.root.addHandler(file_handler)

    # In dev, also emit to stdout so you can watch logs without tailing the file.
    if SERVER_DEV:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logging.root.addHandler(console_handler)


def main() -> None:
    _configure_logging()
    logging.getLogger(__name__).info("Starting JARVIS API on %s:%d", SERVER_HOST, SERVER_PORT)
    uvicorn.run("api.server:app", host=SERVER_HOST, port=SERVER_PORT, reload=SERVER_DEV)


if __name__ == "__main__":
    main()
