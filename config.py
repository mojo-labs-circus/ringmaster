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

# Models — one key per node, plus shared infrastructure keys
ROUTER_MODEL: str         = _config["models"]["router"]
PLANNER_MODEL: str        = _config["models"]["planner"]
CONVERSATION_MODEL: str   = _config["models"]["conversation"]
TASKS_MODEL: str          = _config["models"]["tasks"]
MEMORY_MODEL: str         = _config["models"]["memory"]
WEB_MODEL: str            = _config["models"]["web"]
SYSTEM_MODEL: str         = _config["models"]["system"]
RESPONDER_MODEL: str      = _config["models"]["responder"]
CODE_MODEL: str           = _config["models"]["code"]
CONSTITUTIONAL_MODEL: str = _config["models"]["constitutional"]
SKILLS_MODEL: str         = _config["models"]["skills"]
EMBEDDING_MODEL: str      = _config["models"]["embedding"]
FALLBACK_MODEL: str       = _config["models"]["fallback"]
MULTIMODAL_MODEL: str     = _config["models"]["multimodal"]

# Ollama
OLLAMA_BASE_URL: str    = _config["ollama"]["base_url"]
OLLAMA_TIMEOUT: int     = _config["ollama"]["timeout"]

# Server
SERVER_HOST: str        = _config["server"]["host"]
SERVER_PORT: int        = _config["server"]["port"]
SERVER_DEV: bool        = _config["server"]["dev"]

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
RETENTION_DAYS: int          = _config["maintenance"]["retention_days"]
LOG_ERROR_THRESHOLD: int     = _config["maintenance"]["log_error_threshold"]
IDLE_THRESHOLD_MINUTES: int  = _config["maintenance"]["idle_threshold_minutes"]

# Logging
LOG_PATH: str           = str(Path(_config["logging"]["path"]).expanduser())
LOG_MAX_BYTES: int      = _config["logging"]["max_bytes"]
LOG_BACKUP_COUNT: int   = _config["logging"]["backup_count"]

# Memory
VAULT_BASE: str         = str(Path(_config["memory"]["vault_base"]).expanduser())
CHUNK_SIZE: int         = _config["memory"]["chunk_size"]
CHUNK_OVERLAP: int      = _config["memory"]["chunk_overlap"]

# Improve log
IMPROVE_LOG_PATH: str   = str(Path(_config["improve"]["log_path"]).expanduser())

# Admin
ADMIN_CONTACT: str      = _config["admin"]["contact"]

# Skills
SHARED_SKILLS_PATH: str = _config["skills"]["shared_approved_path"]

# System
ALLOWED_PATHS: list[str] = [
    str(Path(p).expanduser()) for p in _config["system"]["allowed_paths"]
]

# Coding Team
MAX_REVIEW_ITERATIONS: int = _config["coding_team"]["max_review_iterations"]

# Tier gate messages — keyed by capability, shown to Standard tier users
TIER_GATE_MESSAGES: dict[str, str] = _config["tier_gate_messages"]

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
