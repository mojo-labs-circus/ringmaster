# JARVIS — Claude Code Context

## Current Machine — nomadbaker
- **Host:** nomadbaker | **User:** clarkehines | **OS:** Arch Linux
- **GPU:** Intel Arc 140V — no CUDA, no ROCm
- **Active branch:** `phase-3`
- **JARVIS code:** `~/projects/jarvis/`
- **Python venv:** `~/.venvs/jarvis`
- **Dev DBs:** `~/.jarvis/auth.db`, `~/.jarvis/tasks.db`, `~/.jarvis/history.db`
- **Vault:** ❌ not available on this machine
- **ChromaDB:** ❌ not available on this machine
- **Ollama:** ✅ available — model `qwen2.5:3b` only (no CUDA, CPU inference)
- **All URLs use `localhost`** — Docker service names (e.g. `ollama`, `ntfy`) do not exist yet

## Phase Status
- Phase 1 ✅ Done
- Phase 2 ✅ Done
- Phase 3 🔜 Current — Tools + FastAPI

## Current Task
Building the FastAPI skeleton. Files in scope right now:
- `main.py` — entry point, uvicorn, logging setup
- `api/server.py` — FastAPI app instantiation
- `api/routes/chat.py` — `/chat` WebSocket endpoint

Auth is stubbed — do not implement JWT validation yet. The auth system does not exist yet.
LangGraph invocation is stubbed — return a hardcoded response so the frame contract can be verified.

## Standing Rules — Follow These Every Session

Explain before writing. Before producing any file, explain what it is for, why it is structured that way, and any non-obvious design decisions. Wait for approval before writing any code.

Boilerplate vs logic — two modes:
- Boilerplate (repository skeletons, dataclasses, factories, test fixtures) — generate wholesale, user reviews
- Logic-heavy components (graph nodes, routing, state management, error handling) — user writes first draft or pseudocode first, Claude fills in and corrects

System prompt content is always written by the user. Claude implements the infrastructure. The actual prompt text for each node comes from the user.

Comprehension gate. Before marking any component done, the user must be able to explain every function in plain English. Stop and explain anything that isn't clear.

Make at least one deliberate edit to every file Claude writes.

Call out spec deviations immediately. The spec is the source of truth. If something contradicts it, flag it before the code lands.

## Architecture Rules
- Repository pattern everywhere — nodes never touch raw SQL or storage directly
- All data operations scoped to `user_id` — no global queries
- Model names always from `config.yaml` via `config.py` — never hardcoded
- Secrets via env vars only — `JARVIS_SECRET_KEY` hard-fails if unset
- One branch per phase — merge to main only when complete and verified
- Write tests alongside implementation — never defer
- Comment the why, not the what

## WebSocket Frame Contract
All frames are typed JSON with a `message_id` field:

    {"type": "token",  "message_id": "abc123", "content": "..."}
    {"type": "done",   "message_id": "abc123", "refresh": []}
    {"type": "error",  "message_id": "abc123", "message": "..."}
    {"type": "status", "message_id": "abc123", "message": "..."}

Client sends:

    {"message_id": "abc123", "content": "user message here"}

## Key Config
- `config.yaml` — non-sensitive config, single source of truth
- `config.py` — only file that reads config.yaml and env vars
- `.env` — secret values, never committed
- `JARVIS_SECRET_KEY` — required always, hard-fails if unset
- `JARVIS_DB_BACKEND` — `sqlite` in dev
- `JARVIS_DB_URL` — only needed when backend is postgres

## Project Structure (relevant now)

    ~/projects/jarvis/
    ├── config.yaml
    ├── config.py
    ├── main.py
    ├── .env
    ├── .env.example
    ├── api/
    │   ├── server.py
    │   └── routes/
    │       └── chat.py
    └── tests/
        └── unit/

## What Does Not Exist Yet
- Auth system (JWT, users table, refresh tokens) — being built in Phase 3
- Any database tables — `db/schema.py` not written yet
- LangGraph nodes — Phase 1/2 skeleton exists but nodes are being rebuilt
- ChromaDB — pearlybaker only
- Docker / containerisation — Phase 6
