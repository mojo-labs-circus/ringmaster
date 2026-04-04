"""main.py
Entry point for JARVIS. Initialises memory then launches the TUI."""

from memory.chroma import initialise_collections
from memory.ingest import ingest_vault
from tui.app import JarvisApp

if __name__ == "__main__":
    # Memory initialisation disabled on nomadbaker — vault not available.
    # Re-enable on pearlybaker by uncommenting below.
    # from memory.chroma import initialise_collections
    # from memory.ingest import ingest_vault
    # print("[startup] initialising memory...")
    # initialise_collections()
    # ingest_vault()
    # print("[startup] memory ready\n")

    app = JarvisApp()
    app.run()