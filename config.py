"""config.py
Single source of truth for all configuration.
Every module imports from here — nothing reads config.yaml or env vars directly."""

import os
import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def _load() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


_config = _load()

# Models
ROUTER_MODEL: str       = _config["models"]["router"]
GENERAL_MODEL: str      = _config["models"]["general"]
REASONING_MODEL: str    = _config["models"]["reasoning"]
EMBEDDING_MODEL: str    = _config["models"]["embedding"]
FALLBACK_MODEL: str     = _config["models"]["fallback"]
MULTIMODAL_MODEL: str   = _config["models"]["multimodal"]

# Ollama
OLLAMA_BASE_URL: str    = _config["ollama"]["base_url"]
OLLAMA_TIMEOUT: int     = _config["ollama"]["timeout"]

# Server
SERVER_HOST: str        = _config["server"]["host"]
SERVER_PORT: int        = _config["server"]["port"]

# Auth
ACCESS_TOKEN_EXPIRE_HOURS: int      = _config["auth"]["access_token_expire_hours"]
REFRESH_TOKEN_EXPIRE_DAYS: int      = _config["auth"]["refresh_token_expire_days"]
BRUTE_FORCE_LIMIT: int              = _config["auth"]["brute_force_limit"]
BRUTE_FORCE_WINDOW_MINUTES: int     = _config["auth"]["brute_force_window_minutes"]

# Database
DB_PATH: str            = str(Path(_config["db"]["path"]).expanduser())
DB_BACKEND: str         = os.environ.get("JARVIS_DB_BACKEND", "sqlite")

# History
CONTEXT_WINDOW_BUDGET: int = _config["history"]["context_window_budget"]

# Maintenance
RETENTION_DAYS: int     = _config["maintenance"]["retention_days"]
LOG_ERROR_THRESHOLD: int = _config["maintenance"]["log_error_threshold"]

# Logging
LOG_PATH: str           = str(Path(_config["logging"]["path"]).expanduser())

# Memory
VAULT_BASE: str         = str(Path(_config["memory"]["vault_base"]).expanduser())
CHUNK_SIZE: int         = _config["memory"]["chunk_size"]
CHUNK_OVERLAP: int      = _config["memory"]["chunk_overlap"]

# Skills
SHARED_SKILLS_PATH: str = _config["skills"]["shared_approved_path"]

# System
ALLOWED_PATHS: list[str] = [
    str(Path(p).expanduser()) for p in _config["system"]["allowed_paths"]
]

# Coding Team
MAX_REVIEW_ITERATIONS: int = _config["coding_team"]["max_review_iterations"]

# Status messages
STATUS_MESSAGES: dict[str, str] = _config["status_messages"]

# Secrets — hard fail if not set, no silent fallback
SECRET_KEY: str = os.environ["JARVIS_SECRET_KEY"]

# JWT algorithm — hardcoded, not a config key. HS256 is symmetric and appropriate for
# single-server use where the secret never leaves the backend. Changing this would
# immediately invalidate all active tokens, so it is not a runtime tunable.
ALGORITHM: str = "HS256"


def get_postgres_url() -> str:
    """
    Returns the Postgres connection URL from the environment.
    Only called by Postgres repository factories — never at module import time.
    Hard-fails if JARVIS_DB_URL is not set, so misconfiguration is caught immediately.
    """
    return os.environ["JARVIS_DB_URL"]
