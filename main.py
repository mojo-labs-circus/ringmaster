"""main.py
Entry point for JARVIS. Initialises memory then launches the TUI."""

from memory.chroma import initialise_collections
from memory.ingest import ingest_vault
from tui.app import JarvisApp

if __name__ == "__main__":
    # Initialise ChromaDB collections and ingest the vault before the TUI
    # opens. This ensures memory is ready from the very first message.
    # upsert means this is safe to run every startup — no duplicates.
    print("[startup] initialising memory...")
    initialise_collections()
    ingest_vault()
    print("[startup] memory ready\n")

    app = JarvisApp()
    app.run()