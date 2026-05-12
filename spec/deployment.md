# Deployment & Infrastructure

## Tech Stack

| Component | Technology | Notes |
|---|---|---|
| TUI framework | Textual (Python) | Power-user client |
| API server | FastAPI | Unified backend for all clients |
| Auth | JWT (python-jose) | Access token (24hr) + refresh token (90 days) + token_version per user |
| Orchestration | LangGraph | Stateless per-request agent graph — context injected at invocation, `astream_events` for streaming, graph ends at RESPONDER |
| LLM inference | Ollama | Local, GPU-accelerated, shared, streaming mode |
| Vector store | ChromaDB | Per-user + shared collections, named by convention |
| Embeddings | nomic-embed-text | Via Ollama |
| Primary database | Postgres | Tasks, users, sessions, refresh_tokens, invites, conversation history |
| Dev database | SQLite | Dev stand-in, identical interface via repository pattern |
| Knowledge base | Obsidian vault (Markdown) | Per-user + shared family vault |
| Web search | DuckDuckGo | No key, no tracking — via `tools/search.py` |
| Web scraping | Playwright | Headless — via `tools/search.py` |
| Notifications | ntfy | Admin error alerts via `notifications/notify.py` |
| Containerisation | Docker + Docker Compose | Server deployment |
| Reverse proxy | Caddy | TLS + routing |
| Remote access | Tailscale | All clients connect via Tailscale |
| ZFS storage | `/tank/docker/jarvis/` | Postgres + ChromaDB + vaults on server |
| Task scheduler | ofelia | Daily maintenance job — purge expired tokens, invites, old history |
| Voice STT | Whisper / TBD at Phase 10 | Phase 10 — separate container, FastAPI proxy |
| Voice TTS | Piper / TBD at Phase 10 | Phase 10 — separate container, FastAPI proxy |
| Language | Python 3.11+ | |
| Dev GPU | NVIDIA RTX 3080 (pearlybaker) | CUDA 12.1 |
| Server GPUs | See `spec/server.md` | Dual-GPU inference split — primary for reasoning/coding, secondary for lightweight models |
| Test runner | pytest | Unit + integration suites |
