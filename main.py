"""main.py
Process entry point. Configures logging and starts the API server.
config.py hard-fails on import if JARVIS_SECRET_KEY is not set."""

import logging

import uvicorn

from config import SERVER_DEV, SERVER_HOST, SERVER_PORT
from logging_config import configure_logging


def main() -> None:
    """Configure logging and start the uvicorn server.

    reload= is driven by SERVER_DEV so file changes restart the worker
    automatically in development. config.py hard-fails on import if
    JARVIS_SECRET_KEY is not set, so misconfiguration is caught before
    uvicorn starts.
    """
    configure_logging()
    logging.getLogger(__name__).info("Starting JARVIS API on %s:%d", SERVER_HOST, SERVER_PORT)
    uvicorn.run("api.server:app", host=SERVER_HOST, port=SERVER_PORT, reload=SERVER_DEV)


if __name__ == "__main__":
    main()
