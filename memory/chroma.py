"""memory/chroma.py
Initialises and provides access to the ChromaDB vector store.

ChromaDB is a local vector database — it stores text alongside its embedding
(a list of numbers representing meaning) so we can search by semantic
similarity rather than exact keywords.

This module is the single point of contact with ChromaDB for the rest of
the codebase. Everything else imports get_collection() from here."""

import chromadb
from pathlib import Path

# Where ChromaDB persists its data on disk.
# NVMe for fast reads — separate from the vault which lives on the HDD.
CHROMA_PATH = Path.home() / ".jarvis" / "chroma"

# Collections we maintain — one per category of memory.
# Adding a new category later means adding it to this list.
COLLECTIONS = [
    "knowledge",
    "projects",
    "people",
    "conversations",
    "tasks",
]

# Client is created once at module level and reused.
# PersistentClient means data survives between sessions (written to disk).
_client = chromadb.PersistentClient(path=str(CHROMA_PATH))


def get_collection(name: str):
    """Returns a ChromaDB collection by name, creating it if it doesn't exist.

    get_or_create_collection is idempotent — safe to call on every startup.
    If the collection already exists, it connects to it. If not, it creates it.
    """
    if name not in COLLECTIONS:
        raise ValueError(f"Unknown collection '{name}'. Valid options: {COLLECTIONS}")

    return _client.get_or_create_collection(name=name)


def initialise_collections() -> None:
    """Ensures all collections exist in ChromaDB.

    Called once at startup. Safe to call repeatedly — won't overwrite
    existing data."""
    for name in COLLECTIONS:
        collection = _client.get_or_create_collection(name=name)
        print(f"[chroma] collection ready: {name} ({collection.count()} docs)")