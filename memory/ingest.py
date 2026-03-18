"""memory/ingest.py
Ingestion pipeline: Obsidian vault markdown → embeddings → ChromaDB.

Flow for each markdown file:
  1. Read the file
  2. Split into overlapping chunks
  3. Embed each chunk via nomic-embed-text (Ollama)
  4. Store chunk + embedding + metadata in ChromaDB

Which ChromaDB collection a note lands in is determined by which vault
folder it lives in — e.g. 01-knowledge/ → 'knowledge' collection."""

import hashlib
from pathlib import Path
import requests
from memory.chroma import get_collection

# Path to the Obsidian vault (resolves ~/jarvis-brain symlink correctly)
VAULT_PATH = Path.home() / "jarvis-brain"

# Ollama embedding endpoint — nomic-embed-text runs locally
EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# Chunking settings — tuned for Obsidian-style notes
CHUNK_SIZE = 500  # words per chunk
CHUNK_OVERLAP = 50  # words of overlap between consecutive chunks

# Maps vault top-level folders to ChromaDB collection names.
# Files outside these folders (e.g. 07-system/) are skipped —
# no point embedding JARVIS's own config into its memory.
FOLDER_TO_COLLECTION = {
    "01-knowledge": "knowledge",
    "02-skills": "knowledge",  # skills land in knowledge for now (Phase 3.5 adds dedicated collection)
    "03-projects": "projects",
    "04-conversations": "conversations",
    "05-people": "people",
    "06-tasks": "tasks",
    "07-system": "knowledge",
    "08-journal": "knowledge",
}


def _chunk_text(text: str) -> list[str]:
    """Splits text into overlapping word-based chunks.

    Word-based (not character-based) so chunks don't split mid-word.
    Overlap ensures context isn't lost at boundaries."""
    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + CHUNK_SIZE
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        # Move forward by (CHUNK_SIZE - CHUNK_OVERLAP) so next chunk
        # starts inside the tail of the current one
        start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def _embed(text: str) -> list[float]:
    """Sends text to Ollama's nomic-embed-text and returns the embedding vector.

    The vector is a list of ~768 floats representing the semantic meaning
    of the text. Similar texts produce similar vectors."""
    response = requests.post(EMBED_URL, json={
        "model": EMBED_MODEL,
        "prompt": text
    })
    response.raise_for_status()
    return response.json()["embedding"]


def _make_chunk_id(file_path: Path, chunk_text: str) -> str:
    """Generates a stable unique ID for a chunk.

    Using a hash of the file path + chunk index means re-ingesting the
    same file produces the same IDs — ChromaDB will upsert (update if
    exists, insert if not) rather than creating duplicates."""
    raw = f"{file_path}::{chunk_text}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_collection_for_file(file_path: Path):
    """Works out which ChromaDB collection this file belongs in,
    based on its top-level vault folder."""
    # file_path is absolute — get the folder name relative to vault root
    try:
        relative = file_path.relative_to(VAULT_PATH)
        top_folder = relative.parts[0]
    except (ValueError, IndexError):
        return None

    collection_name = FOLDER_TO_COLLECTION.get(top_folder)
    if not collection_name:
        return None  # folder not mapped — skip this file

    return get_collection(collection_name)


def ingest_file(file_path: Path) -> int:
    """Ingests a single markdown file into ChromaDB.

    Returns the number of chunks stored, or 0 if the file was skipped."""
    collection = _get_collection_for_file(file_path)
    if collection is None:
        return 0

    text = file_path.read_text(encoding="utf-8").strip()
    if not text:
        return 0  # skip empty files

    chunks = _chunk_text(text)

    for i, chunk in enumerate(chunks):
        chunk_id = _make_chunk_id(file_path, chunk)
        embedding = _embed(chunk)

        # upsert = insert if new, update if ID already exists
        # This means re-running ingest after editing a note is safe
        collection.upsert(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[chunk],
            metadatas=[{
                "source": str(file_path),
                "chunk_index": i,
                "filename": file_path.name,
            }]
        )

    return len(chunks)


def ingest_vault() -> None:
    """Walks the entire vault and ingests every markdown file.

    Safe to re-run — upsert means existing chunks are updated, not duplicated.
    Prints a summary of what was ingested."""
    markdown_files = list(VAULT_PATH.rglob("*.md"))
    print(f"[ingest] found {len(markdown_files)} markdown files in vault")

    total_chunks = 0
    for file_path in markdown_files:
        count = ingest_file(file_path)
        if count:
            print(f"[ingest] {file_path.relative_to(VAULT_PATH)} → {count} chunks")
            total_chunks += count

    print(f"[ingest] done — {total_chunks} chunks stored across all collections")