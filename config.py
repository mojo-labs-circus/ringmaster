"""config.py
Single source of truth for all configuration.
Every module imports from here — nothing reads config.yaml directly."""

import yaml
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "config.yaml"

def _load() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

_config = _load()

# Ollama
OLLAMA_HOST: str = _config["ollama"]["host"]
ROUTER_MODEL: str = _config["ollama"]["models"]["router"]
GENERAL_MODEL: str = _config["ollama"]["models"]["general"]
CODING_MODEL: str = _config["ollama"]["models"]["coding"]
EMBEDDING_MODEL: str = _config["ollama"]["models"]["embedding"]

# Memory
CHROMA_PATH: str = str(Path(_config["memory"]["chroma_path"]).expanduser())
VAULT_PATH: str = str(Path(_config["memory"]["vault_path"]).expanduser())
AUTO_INGEST: bool = _config["memory"]["auto_ingest"]

# System
CONFIRM_SHELL: bool = _config["system"]["confirm_shell"]
ALLOWED_PATHS: list[str] = [
    str(Path(p).expanduser()) for p in _config["system"]["allowed_paths"]
]

# API
API_ENABLED: bool = _config["api"]["enabled"]
API_HOST: str = _config["api"]["host"]
API_PORT: int = _config["api"]["port"]
