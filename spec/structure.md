# Project Directory Structure

```
~/projects/jarvis/
├── config.yaml              # Non-sensitive config — single source of truth
├── config.py                # Reads config.yaml + env vars — only file that touches either
├── main.py                  # Dev entry point — launches FastAPI via uvicorn (reload=True)
├── .env                     # Actual secret values — never committed, listed in .gitignore
├── .env.example             # Canonical list of required env vars with empty values — committed to git
│                            #   JARVIS_SECRET_KEY=        # JWT signing secret — required always, including before running scripts (config.py hard-fails on import if unset)
│                            #   JARVIS_DB_BACKEND=sqlite  # sqlite | postgres — defaults to sqlite
│                            #   JARVIS_DB_URL=            # Postgres connection URL — required when DB_BACKEND=postgres
├── scripts/
│   └── seed_db.py           # First-run setup — creates initial clarkehines admin record only. All other users via invite flow.
├── tui/                     # Textual client
│   ├── app.py
│   ├── auth.py              # Token manager — silent refresh, 401 handling, ~/.jarvis/auth.json (deleted on logout). Opens WebSocket on startup, reconnects on drop. Disables input on confirm_request, re-enables on resolution.
│   ├── panels/
│   └── styles/
├── api/                     # FastAPI server
│   ├── server.py
│   ├── schemas.py           # Pydantic models for API request/response shapes
│   ├── dependencies.py      # get_current_user, get_connected_client_ws, ConnectedClient, tier checks
│   ├── connections.py       # Connection registry — maps user_id to active WebSockets, profile push
│   └── routes/
│       ├── auth.py          # JWT auth — access + refresh tokens, token_version validation, invite + register flow. Gets auth repository via db/auth/factory.py.
│       ├── chat.py          # WebSocket streaming endpoint — owns all frame sending, uses astream_events, drops messages during active invocation, fires memory/persist.py as background task after every exchange
│       ├── profile.py       # GET /profile, PATCH /profile
│       ├── tasks.py         # GET /tasks, DELETE /tasks/{id}
│       └── memory.py        # GET /memory (stub in Phase 3)
├── graph/                   # LangGraph — graph ends at RESPONDER
│   ├── graph.py
│   ├── state.py             # JarvisState — all fields required, node-populated fields zero-initialised by FastAPI
│   ├── nodes/
│   │   ├── router.py        # Sets intent + needs_memory (retrieval only), checks skills (intent-scoped), populates skill_context
│   │   ├── memory_retrieve.py  # Runs only when needs_memory=True — retrieves from ChromaDB
│   │   ├── conversation.py  # General chat — all tiers, calls tools/llm.py with messages + retrieved_context + skill_context
│   │   ├── memory.py        # Explicit memory queries and delete/forget — all tiers, scoped to user_id
│   │   ├── tasks.py         # Task management — calls db/tasks/ repository
│   │   ├── code.py          # Coding — calls tools/llm.py, tools/sandbox.py, tools/vault.py
│   │   ├── web.py           # Web search — calls tools/search.py
│   │   ├── system.py        # Shell execution — calls tools/shell.py, interrupt/confirm before every command, stdout+stderr both passed to Ollama for formatting
│   │   └── responder.py     # Pure formatter — checks error field, formats for client_type, derives and sets refresh list on state. Never an agent node. Graph ends here.
│   └── coding_team/         # Subgraph — architecture TBD in planning session
│       ├── subgraph.py
│       ├── architect.py
│       ├── coder.py
│       ├── reviewer.py
│       └── tester.py
├── tools/                   # Utility wrappers — stateless callables used by graph nodes. Add new capabilities here.
│   ├── llm.py               # Ollama wrapper — streaming, timeout, fallback model logic. All nodes call this.
│   ├── search.py            # DuckDuckGo search + Playwright scraping. Used by WEB node.
│   ├── shell.py             # Subprocess runner with path sandboxing against ALLOWED_PATHS. Captures stdout and stderr separately. Used by SYSTEM node.
│   ├── sandbox.py           # Sandboxed code execution subprocess. Used by CODE node.
│   ├── vault.py             # Obsidian vault file reader. Used by CODE node and memory ingestion. [pearlybaker only]
│   └── tokens.py            # Token counting utility. Used by history repository to enforce CONTEXT_WINDOW_BUDGET.
├── db/                      # All persistence — repositories, models, factories, schema
│   ├── schema.py            # Exposes create_tables() — called from FastAPI lifespan on startup (sqlite only)
│   ├── auth/
│   │   ├── models.py        # User, RefreshToken, Invite dataclasses
│   │   ├── repository.py    # Abstract base class
│   │   ├── sqlite.py        # SQLiteAuthRepository
│   │   ├── postgres.py      # PostgresAuthRepository (stub in Phase 3, full in Phase 6)
│   │   └── factory.py       # Reads JARVIS_DB_BACKEND env var, defaults to sqlite
│   ├── tasks/
│   │   ├── models.py        # Task dataclass — id, user_id, title, status, priority, due_date, created_at
│   │   ├── repository.py    # Abstract base class — all methods require user_id
│   │   ├── sqlite.py        # SQLiteTaskRepository
│   │   ├── postgres.py      # PostgresTaskRepository (stub in Phase 3, full in Phase 6)
│   │   └── factory.py       # Reads JARVIS_DB_BACKEND env var, defaults to sqlite
│   └── history/
│       ├── models.py        # HistoryEntry dataclass — id, user_id, role, content, created_at
│       ├── repository.py    # Abstract base class — load(user_id) -> list[dict], save(user_id, role, content)
│       ├── sqlite.py        # SQLiteHistoryRepository
│       ├── postgres.py      # PostgresHistoryRepository (stub in Phase 3, full in Phase 6)
│       └── factory.py       # Reads JARVIS_DB_BACKEND env var, defaults to sqlite
├── memory/                  # ChromaDB operations and long-term memory persistence
│   ├── chroma.py            # ChromaDB client — collections named by convention
│   ├── ingest.py            # Vault ingestion pipeline
│   ├── retrieval.py         # Queries memory_{user_id} + memory_shared
│   └── persist.py           # Background task — fired unconditionally after every exchange. Evaluates exchange, classifies personal vs shared, writes markdown to vault then ingests into ChromaDB if worth persisting.
├── notifications/
│   └── notify.py            # ntfy wrapper — notify_admin(error_class, message), 10-min cooldown per (error_class, message)
├── maintenance/
│   └── cleanup.py           # Daily maintenance job — purge expired tokens, invites, old history
├── tests/
│   ├── conftest.py          # Shared fixtures — test_user, test_db, mock_ollama
│   ├── unit/                # Fast, mocked — run on every commit via pre-commit hook
│   │   ├── test_router.py
│   │   ├── test_tasks_node.py
│   │   ├── test_responder.py
│   │   └── ...
│   └── integration/         # Real SQLite, Ollama mocked — run manually
│       ├── test_tasks_repository.py
│       ├── test_history_repository.py
│       └── ...
```
