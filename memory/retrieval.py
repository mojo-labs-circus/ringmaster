"""memory/retrieval.py
Retrieves relevant context from ChromaDB given a query string.

The query is embedded with the same model used during ingestion
(nomic-embed-text), then ChromaDB finds the stored chunks whose
vectors are closest to the query vector — semantic search."""

import requests
from memory.chroma import get_collection, COLLECTIONS

EMBED_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# How many chunks to retrieve per collection.
# 3 is enough context without flooding the prompt.
TOP_K = 3


def _embed_query(text: str) -> list[float]:
    """Embeds the query using nomic-embed-text.

    Identical to the embedding step in ingest.py — must use the same
    model, otherwise the vectors are incomparable."""
    response = requests.post(EMBED_URL, json={
        "model": EMBED_MODEL,
        "prompt": text
    })
    response.raise_for_status()
    return response.json()["embedding"]


def retrieve(query: str, collections: list[str] | None = None) -> list[dict]:
    """Searches ChromaDB for chunks relevant to the query.

    Searches across all collections by default, or a specific subset
    if collections is provided (e.g. ["projects", "knowledge"]).

    Returns a list of result dicts, each with:
        - text: the raw chunk content
        - source: which vault file it came from
        - collection: which ChromaDB collection it was in
        - distance: how far from the query vector (lower = more similar)
    """
    query_embedding = _embed_query(query)

    # Default to searching all collections
    collections_to_search = collections or COLLECTIONS

    results = []
    for collection_name in collections_to_search:
        collection = get_collection(collection_name)

        # Skip empty collections — querying an empty collection errors
        if collection.count() == 0:
            continue

        hits = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(TOP_K, collection.count()),  # can't request more than exists
            include=["documents", "metadatas", "distances"]
        )

        # ChromaDB returns nested lists — one list per query embedding.
        # Since we only ever send one query at a time, we take index [0].
        for doc, meta, dist in zip(
                hits["documents"][0],
                hits["metadatas"][0],
                hits["distances"][0]
        ):
            results.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "collection": collection_name,
                "distance": dist,
            })

    # Sort all results across all collections by distance (ascending).
    # Lower distance = more similar to query = should appear first.
    results.sort(key=lambda x: x["distance"])

    return results


def retrieve_as_context(query: str, collections: list[str] | None = None) -> str:
    """Convenience wrapper that returns retrieved chunks as a formatted string.

    This is what gets injected into the LangGraph prompt — a clean block
    of text the model can read as background context."""
    results = retrieve(query, collections)

    if not results:
        return ""

    lines = ["Relevant context from your knowledge base:\n"]
    for r in results:
        # Just the filename, not the full path — cleaner for the prompt
        filename = r["source"].split("/")[-1]
        lines.append(f"[{filename}]\n{r['text']}\n")

    return "\n".join(lines)