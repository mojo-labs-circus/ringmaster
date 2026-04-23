# Build Phases

## Phase 1 ✅ — Foundation
LangGraph skeleton, TUI, Ollama, routing. Done.

## Phase 2 ✅ — Memory
ChromaDB, vault ingestion pipeline, RAG, MEMORY node. Done.

## Phase 3 — Tools + FastAPI Skeleton *(current)*

All tool nodes built with repository pattern and `user_id` scoping from day one. FastAPI skeleton built alongside the first node — all subsequent nodes go straight against the API, no retrofit later.

**Branch:** `phase-3` — merge to main only when phase is complete and verified.

**`[pearlybaker only]` items require a vault and ChromaDB — do not attempt on nomadbaker.**

**FastAPI skeleton (built first, before any tool node):**
- [ ] Minimal FastAPI server — single `/chat` WebSocket endpoint
- [ ] Auth repository — `db/auth/` with full factory pattern mirroring tasks and history
  - [ ] `db/auth/models.py` — User, RefreshToken, Invite dataclasses
  - [ ] `db/auth/repository.py` — abstract base class
  - [ ] `db/auth/sqlite.py` — SQLiteAuthRepository
  - [ ] `db/auth/postgres.py` — PostgresAuthRepository (stub)
  - [ ] `db/auth/factory.py` — reads `JARVIS_DB_BACKEND` env var, defaults to `sqlite`
  - [ ] `api/routes/auth.py` gets its repository via the factory — never accesses storage directly
- [ ] JWT auth — `POST /auth/login` endpoint. Request: `{"username": "...", "password": "..."}`. Response: `{"access_token": "...", "refresh_token": "...", "access_expires_at": "..."}`. Inserts row into `refresh_tokens` on success. Returns 401 on failure. Tracks failed attempts per IP — 5 failures in 10 minutes triggers `notify_admin`.
- [ ] `/auth/refresh` endpoint — silent token renewal, called by `tui/auth.py`. Validates token hash against `refresh_tokens` table — rejects if revoked or expired.
- [ ] `/auth/logout` endpoint — marks current device's refresh token row `revoked = true`. Does not increment `token_version` — other devices stay active.
- [ ] `GET /profile` endpoint — returns `username`, `tier`, `assistant_name` for the authenticated user
- [ ] `PATCH /profile` endpoint — updates `assistant_name`, returns updated profile. Pushes `profile` frame to all of the user's active connections.
- [ ] `/auth/invite` endpoint — Admin only. Generates one-time invite token (48hr expiry), returns raw token to Admin
- [ ] `/auth/register` endpoint — Open (invite token required). Validates token, creates user record, marks invite `used = true`
- [ ] `users` table — fields: `username` (PK), `password_hash`, `tier`, `assistant_name`, `token_version`
- [ ] `refresh_tokens` table — fields: `id`, `user_id`, `token_hash`, `expires_at`, `revoked`
- [ ] `invites` table — fields: `id`, `token_hash`, `username`, `tier`, `assistant_name`, `expires_at`, `used`
- [ ] `db/schema.py` — exposes `create_tables()` function. Opens connections to `auth.db` (users, refresh_tokens, invites), `tasks.db` (tasks), and `history.db` (history) and runs `CREATE TABLE IF NOT EXISTS` for each. Called from FastAPI's lifespan context manager on startup, conditional on `DB_BACKEND == "sqlite"` — never at module import time. When the schema changes during development, delete the relevant `.db` file and let startup recreate it: `~/.jarvis/auth.db` for auth tables, `~/.jarvis/tasks.db` for tasks, `~/.jarvis/history.db` for history. Proper migrations (Alembic) are introduced in Phase 6.
- [ ] `scripts/seed_db.py` — calls `create_tables()` first, then creates initial `clarkehines` admin record. Idempotent, interactive password prompt, prints confirmation. All other users added via invite flow.
- [ ] `JarvisState` updated — all fields present, node-populated fields zero-initialised by FastAPI at invocation (including `interrupt_payload: None`)
- [ ] FastAPI validates `token_version` against database on every request and on every WebSocket message received
- [ ] FastAPI uses `astream_events` — sends node-entry `status` frames driven by `STATUS_MESSAGES` dict. Forwards mid-node `status_message` updates from state as `status` frames. Sends `"One moment..."` status frame immediately when a message is queued during an active invocation. Rejects non-confirm/cancel messages during active interrupt with `"Please confirm or cancel the pending action first."` status frame. On `token_version` mismatch, clears the queue and sends an `error` frame indicating re-authentication was required.
- [ ] WebSocket streaming — typed JSON frames (`token`, `done`, `error`, `status`) with `message_id`. FastAPI owns all frame sending. One invocation at a time per connection — incoming messages queued until `done` frame is sent.
- [ ] Conversation history repository — `db/history/` with SQLite dev backend, Postgres stub (mirrors `db/tasks/` structure exactly)
- [ ] Conversation history load from repository → inject into state as `list[{"role": str, "content": str}]`, bounded by `CONTEXT_WINDOW_BUDGET` tokens. FastAPI appends `current_input` as the final entry before invocation.
- [ ] Conversation history write back to repository after invocation
- [ ] Secrets via env vars only — `JARVIS_SECRET_KEY` hard-fails if unset, no sensitive values in `config.yaml` or git
- [ ] `main.py` — launches FastAPI via uvicorn, `reload=True` in dev
- [ ] `notifications/notify.py` — ntfy wrapper, `notify_admin(error_class, message)`, 10-minute cooldown keyed on `(error_class, message)` tuple
- [ ] Logging configured in `main.py` — `RotatingFileHandler`, path from `LOG_PATH`, 10 MB max per file, 5 files retained, `INFO` level by default
- [ ] FastAPI global exception handler wired to `notify_admin`
- [ ] Daily ofelia maintenance job — purges expired `refresh_tokens`, expired `invites`, and history entries older than `RETENTION_DAYS`. Counts `ERROR`-level log entries from the last 24 hours — notifies admin if over `LOG_ERROR_THRESHOLD`. Intentionally general-purpose — future maintenance tasks added here.
- [ ] **Verify FastAPI works end to end with a throwaway test client before rewriting TUI**

**Then tool nodes (built against FastAPI from the start):**
- [ ] TASKS node — repository pattern, SQLite dev backend, Postgres interface stubbed
  - [ ] `db/tasks/models.py` — Task dataclass with fields: `id`, `user_id`, `title`, `status` (`open|closed`), `priority` (`low|medium|high`), `due_date`, `created_at`
  - [ ] `db/tasks/repository.py` — abstract base class, all methods require `user_id`
  - [ ] `db/tasks/sqlite.py` — SQLiteTaskRepository
  - [ ] `db/tasks/postgres.py` — PostgresTaskRepository (stub)
  - [ ] `db/tasks/factory.py` — reads `JARVIS_DB_BACKEND` env var, defaults to `sqlite`
  - [ ] `graph/nodes/tasks.py` — calls repository only, never raw SQL. Operations: create, update, complete, list, delete.
  - [ ] `GET /tasks` — returns all tasks for the authenticated user as a JSON array (open and closed). Built alongside the TASKS node — endpoint and feature ship together.
  - [ ] `DELETE /tasks/{id}` — permanently deletes a task scoped to the authenticated user. Returns 404 if not found or not owned by requesting user. Built alongside the TASKS node.
- [ ] `tools/llm.py` — Ollama wrapper. Handles streaming, timeout, fallback model logic. All nodes call this rather than Ollama directly.
- [ ] `tools/search.py` — DuckDuckGo search + Playwright scraping wrapper. WEB node calls this.
- [ ] `tools/shell.py` — subprocess runner with path sandboxing against `ALLOWED_PATHS`. Captures stdout and stderr separately. SYSTEM node calls this.
- [ ] `tools/sandbox.py` — sandboxed code execution subprocess. CODE node calls this.
- [ ] `tools/vault.py` — Obsidian vault file reader. CODE node and memory ingestion call this. `[pearlybaker only]`
- [ ] `tools/tokens.py` — token counting utility. History repository uses this to enforce `CONTEXT_WINDOW_BUDGET`.
- [ ] WEB node — calls `tools/search.py`. Writes specific `status_message` for each query. Includes `skill_context` in Ollama prompt if non-empty.
- [ ] SYSTEM node — calls `tools/shell.py` for execution. Confirmation gate via interrupt/confirm. No Ollama streaming before confirmation. On cancel, writes hardcoded cancellation message. Passes both stdout and stderr to Ollama for formatting. Includes `skill_context` in Ollama prompt if non-empty.
- [ ] CODE node — single-agent, calls `tools/llm.py` with reasoning model directly (Coding Team subgraph wired in Phase 8). Calls `tools/sandbox.py` for code execution. Calls `tools/vault.py` for project context `[pearlybaker only]`. Writes granular `status_message` updates throughout. Includes `skill_context` in Ollama prompt if non-empty.
- [ ] CONVERSATION node — `graph/nodes/conversation.py`. General chat for all tiers. Calls `tools/llm.py` with `messages`, `retrieved_context`, and `skill_context`. Writes to `response`.
- [ ] MEMORY node — `graph/nodes/memory.py`. Handles explicit memory queries and delete/forget operations against ChromaDB. All tiers. Scoped to `user_id`. Operates on `retrieved_context` — does not query ChromaDB directly for retrieval. `[pearlybaker only]`.
- [ ] `memory/persist.py` — asyncio background task fired by FastAPI unconditionally after every exchange. Evaluates exchange, classifies personal vs shared. If worth persisting: writes markdown to vault (`tools/vault.py`), then immediately ingests into ChromaDB (`memory/ingest.py`, `memory/chroma.py`). Vault is source of truth — ChromaDB is derived from it. Uses `tools/llm.py` for inference. `[pearlybaker only]`
- [ ] `GET /memory` — stub response in Phase 3 (ChromaDB is `[pearlybaker only]`). Returns an empty JSON array `[]`. Endpoint exists so TUI refresh handling is fully wired and testable.
- [ ] ROUTER updated — `needs_memory` flag per intent controls retrieval only (conditional on request type for `tasks` — see ROUTER spec), skills check with graceful no-op `[pearlybaker only for skills check]`
- [ ] RESPONDER updated — reads `client_type` from state, checks `error` field, derives and sets `refresh` list on state from `intent` (RESPONDER is sole owner of `refresh`)
- [ ] `MEMORY_RETRIEVE` node — queries ChromaDB, populates `retrieved_context` `[pearlybaker only]`
- [ ] TUI rewritten — connects to FastAPI WebSocket instead of local LangGraph (only after FastAPI is verified working). Opens connection on startup, reconnects automatically on drop. Disables input field on `confirm_request` frame, re-enables on resolution.
- [ ] TUI auth client (`tui/auth.py`) — token storage in `~/.jarvis/auth.json`, silent refresh, handles 401 token version mismatch, deletes `auth.json` on logout, login prompt if `auth.json` missing or refresh token expired/revoked. Calls `GET /profile` on startup and after every login/refresh to populate `tier` and `assistant_name` in memory. Handles `profile` WebSocket frames by re-fetching `GET /profile`.
- [ ] TUI listens for `done` frames and re-fetches panels listed in `refresh`
- [ ] Unit tests alongside every node implementation

### TUI Token Management

The TUI is a long-lived terminal process — the access token can expire mid-session. The TUI handles this silently via a token manager module (`tui/auth.py`):

- On startup, loads stored tokens from `~/.jarvis/auth.json` — if the file does not exist, presents the login prompt immediately
- Calls `GET /profile` immediately after loading tokens (or after any successful login/refresh) to populate `tier` and `assistant_name` in memory
- Opens the WebSocket connection immediately on startup — not lazily on first message
- Before every API request, checks `access_expires_at` in `auth.json` — if within 5 minutes of expiry, calls the `/auth/refresh` endpoint automatically
- On successful refresh, writes the new access token and updated `access_expires_at` back to `~/.jarvis/auth.json`
- If the server returns 401 (token version mismatch), triggers silent refresh immediately
- If the refresh token is also expired or revoked, presents the login prompt
- On receipt of a `profile` WebSocket frame, calls `GET /profile` and updates the in-memory cache — this is how assistant name and tier changes propagate to active sessions
- If the WebSocket connection drops (network blip, server restart), the TUI reconnects automatically
- On logout (or forced logout via token version mismatch with no valid refresh), `tui/auth.py` immediately closes the WebSocket, deletes `~/.jarvis/auth.json` from disk, clears all data panels (chat history, tasks, memory — no previously seen data remains visible), and returns the user to the login prompt — it does not wait for a subsequent request or message to fail
- The user never sees an interruption during normal use

`~/.jarvis/auth.json` is chmod 600 and listed in `.gitignore`.

**`~/.jarvis/auth.json` schema:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "access_expires_at": "2026-04-10T14:00:00Z"
}
```

`access_expires_at` is an ISO 8601 UTC timestamp. The TUI checks this directly — no JWT decoding required to determine whether refresh is needed.
- [ ] Pre-commit hook configured — `pytest tests/unit/` blocks commits on failure

**Exit criteria:** JARVIS can search the web, manage tasks (create, update, complete, delete), run shell commands, switch into coding mode (single-agent), handle general conversation via CONVERSATION node, and respond to explicit memory queries via MEMORY node `[pearlybaker only]` — on nomadbaker, verify that the `memory` intent returns a clean ChromaDB unavailable error message. TUI connects to FastAPI via WebSocket, tokens stream word by word. Responses arrive as typed JSON frames. Tasks panel updates automatically when tasks are mutated — `GET /tasks` and `DELETE /tasks/{id}` endpoints verified working and TUI re-fetches on `refresh: ["tasks"]`. All data operations go through repository interfaces with `user_id` — including auth. Conversation history correctly written and loaded across multiple exchanges. Admin notified via ntfy on service failures. Secrets are env-var only. Full auth flow verified end to end: login produces a valid JWT, `GET /profile` returns correct user data, `PATCH /profile` updates `assistant_name` and returns the updated profile, silent refresh works, logout revokes the token. Invite+register verified end to end: Admin generates an invite token via `POST /auth/invite`, a second user registers via `POST /auth/register` with that token, that user logs in and receives a valid JWT, and at minimum one WebSocket chat exchange completes successfully as that user with data correctly scoped to their `user_id`. No external services required to run in dev (memory/skills work deferred to pearlybaker). Queuing and interrupt/confirm contracts verified: queued messages receive `"One moment..."` status frame, non-confirm/cancel messages during interrupt are rejected with appropriate status frame, TUI disables input on `confirm_request`.

## Phase 4 — Multi-User + Full Auth

FastAPI skeleton exists from Phase 3. This phase completes the multi-user platform.

- [ ] Full user management — three test accounts (admin, power, standard) created via invite flow, tiers and assistant names verified
- [ ] All agent nodes accessible via API with tier gating
- [ ] Per-user data scoping verified end-to-end
- [ ] Refresh token rotation
- [ ] User management endpoints (Admin only) — `PATCH /admin/users/{username}` for tier changes and forced deauth (`token_version` increment)
- [ ] Assistant name hotswappable — `PATCH /profile` updates DB, server pushes `profile` frame to all active connections, clients re-fetch `GET /profile`
- [ ] Tier changes hotswappable — admin updates DB via `PATCH /admin/users/{username}`, server pushes `profile` frame to all active connections, clients re-fetch `GET /profile`
- [ ] Multiple concurrent users verified

**Exit criteria:** Three test users exist — one of each tier (admin, power, standard) — all created via invite flow except the admin. All three can chat simultaneously with fully isolated data. Tier gating verified (standard user cannot access code or system nodes). Assistant names and tiers are hotswappable — changes propagate to all active connections via `profile` WebSocket push within seconds, no re-login required.

## Phase 5 — Web Client

The web client is the onboarding gateway — zero install, works in any browser, accessible from every family device as soon as the server is live in Phase 6.

### Family device breakdown

| Person | Devices |
|---|---|
| Clarke (admin) | Linux + iOS |
| Brother | Windows + iOS |
| Everyone else | macOS + iOS |

Every family member has iOS. No Android devices in the family.

### Tailscale + NordVPN — known per-platform situation

All clients connect over Tailscale. Family members using NordVPN need to handle coexistence per platform:

| Platform | Fix | Notes |
|---|---|---|
| Linux | `nordvpn whitelist add subnet 100.64.0.0/10 && nordvpn whitelist add port 41641 protocol UDP` | One-time CLI setup |
| macOS | NordVPN app → Split Tunneling → add `100.64.0.0/10` to bypass list | GUI only — no CLI needed |
| Windows | NordVPN app → Split Tunneling → Bypass VPN → add `100.64.0.0/10` | GUI only — no CLI needed |
| iOS | **Not fixable.** iOS allows only one active VPN at a time. Tailscale and NordVPN cannot run simultaneously. | Toggle NordVPN off when using JARVIS |

The iOS limitation is a hard iOS platform constraint — not a configuration issue. It affects every family member. At home on WiFi, NordVPN is typically inactive so the conflict rarely occurs in practice.

### Features
- [ ] Login screen — prompts for credentials, stores tokens on success
- [ ] Chat panel — full WebSocket flow, streaming token display
- [ ] Tasks panel — reads `GET /tasks`, updates automatically on `done` frame `refresh` array
- [ ] Memory panel — reads `GET /memory` (stub until Phase 7)
- [ ] Skill approval queue — Admin/Power only, shown based on JWT tier claim
- [ ] User settings — assistant name, preferences
- [ ] Silent token refresh — handled transparently, user never sees it
- [ ] Handles `profile` WebSocket frames — re-fetches `GET /profile` on receipt
- [ ] Reconnects automatically on dropped WebSocket connection

### Token storage
httpOnly cookie for refresh token, memory-only for access token.

### Distribution
Deployed at `jarvis.home` via Docker Compose (service definition added in Phase 6). No install required — accessible from any browser on the tailnet.

**Exit criteria:** Web client live at `jarvis.home`. Full family can register via invite token, log in, and use JARVIS from a browser. Tasks panel updates automatically on `refresh`. Silent token refresh works. Ready for Phase 7 family onboarding.

## Phase 6 — Server Deployment + Postgres Migration *(summer 2026)*

Postgres lives on the server — there is no reason to run it locally in dev. SQLite handles development; Postgres is introduced here alongside the server stack.

**Postgres migration:**
- [ ] `PostgresAuthRepository` full implementation
- [ ] `PostgresTaskRepository` full implementation
- [ ] `PostgresHistoryRepository` full implementation
- [ ] `JARVIS_DB_BACKEND=postgres` env var switches all repository backends
- [ ] Alembic introduced — migration tooling for all future schema changes. Replaces drop-and-recreate dev convention. All schema changes from this point forward go through Alembic migrations.
- [ ] Migration script: SQLite → Postgres

**Server deployment:**
- [ ] Docker Compose for full JARVIS stack
- [ ] All services containerised — Postgres, ChromaDB, Ollama (primary), Ollama (secondary), FastAPI, web client
- [ ] Data on `/tank/docker/jarvis/` (ZFS, auto-snapshotted)
- [ ] Caddy entry — `jarvis.home`
- [ ] Tailscale access from all devices
- [ ] ofelia for scheduled tasks including daily maintenance job
- [ ] All clients pointed at server — config update only, no code changes
- [ ] Voice container placeholders in Docker Compose (STT + TTS service definitions, no implementation yet)

**Dual-GPU inference split:**
- [ ] Second GPU installed — cheaper secondary card dedicated to lightweight inference
- [ ] Two Ollama instances: primary (4070 Ti Super) serves reasoning and coding models, secondary serves lightweight models (ROUTER, CONVERSATION, TASKS, MEMORY, WEB, SYSTEM, RESPONDER)
- [ ] `config.yaml` — `ollama_url_primary` and `ollama_url_secondary`
- [ ] `tools/llm.py` — model-based routing: checks requested model name, routes to the correct Ollama instance. No tier logic needed — the model encodes the workload type.

**Exit criteria:** JARVIS running on server against Postgres. All clients connect over Tailscale. All data on ZFS. All schema changes go through Alembic. Lightweight inference (chat, tasks, routing) never contends with heavy inference (planning, coding).

**Note:** Post-deployment, all development runs against the live server stack over Tailscale. The SQLite dev backends (`auth.db`, `tasks.db`, `history.db`), local vault paths, and `[pearlybaker only]` annotations become redundant at this point and may be retired.

**Post-Phase-6 cleanup task:** Once the server is running and all clients are connecting to it, do a full cleanup pass: remove all `[pearlybaker only]` annotations and conditional code paths, retire nomadbaker stand-in model config, consolidate all vault and data paths to `/tank/docker/jarvis/`, and remove the SQLite dev scaffolding from the spec, codebase, and databases.

## Phase 7 — Multi-User Onboarding

Onboarding begins as soon as the web client is live (Phase 5) — family members start using JARVIS via `jarvis.home` while the remaining native clients (Phase 9) are still being built.

- [ ] Family members get on Tailscale — invite link sent per person, platform-specific NordVPN guide where needed (see Phase 5 NordVPN table)
- [ ] Family member accounts created via invite flow — all register via `jarvis.home` in a browser
- [ ] Per-user vaults initialised
- [ ] Shared family vault populated with household knowledge
- [ ] Shared vault ingested — `memory_shared` ChromaDB collection populated
- [ ] Shared skills ingested — `skills_shared` ChromaDB collection populated
- [ ] ROUTER verified to query `skills_shared` and return relevant results
- [ ] Personal → shared memory classifier tuned
- [ ] Each user sets their assistant name

**Exit criteria:** All family members using JARVIS daily. Shared and personal memory working correctly. ROUTER successfully retrieves from both personal and shared skills collections.

## Phase 8 — Coding Team + Skills System

**Coding Team requires a dedicated planning session before implementation begins.** Internal architecture (sandbox boundaries, interruption model, loop behaviour, Tester constraints) must be fully specified before any code is written.

- [ ] Dedicated Coding Team planning session
- [ ] Architect, Coder, Reviewer, Tester nodes as LangGraph subgraph
- [ ] Each subgraph node writes its own `status_message` — "Architect planning...", "Coder implementing...", "Reviewer checking...", "Tester running..."
- [ ] On cancel at any interrupt point, node writes hardcoded cancellation message derived from `interrupt_payload` — no inference call
- [ ] Tier gate — Admin and Power only
- [ ] Skills vault structure created (personal + shared)
- [ ] Skill ingestion — personal (`skills_{user_id}`) and shared (`skills_shared`) pipelines
- [ ] ROUTER checks personal + shared skills before every action
- [ ] Assistant proposes skills → `pending/` for review
- [ ] Reviewer → Coder loop with configurable max iterations

**Exit criteria:** Complex coding task runs through full team loop. A shared skill is approved and used across multiple users. Coding Team used to assist with Phase 9 client development.

## Phase 9 — Remaining Clients

Four native clients, built with Coding Team assistance (Phase 8). `jarvis-tui` already exists and covers Clarke throughout development — it is extracted to its own repo here.

### Build order

| Priority | Repo | Platform | Who uses it | Stack | Admin panel |
|---|---|---|---|---|---|
| 1 | `jarvis-ios` | iOS | Everyone | Swift/SwiftUI | Yes |
| 2 | `jarvis-desktop-macos` | macOS | Everyone else | Swift/SwiftUI | No |
| 3 | `jarvis-desktop-windows` | Windows | Brother | C#/WinUI 3 | No |
| 4 | `jarvis-desktop-linux` | Linux | Clarke | Python/GTK4 + libadwaita | Yes |

`jarvis-swift-core` — separate repo, a shared Swift Package consumed by both `jarvis-desktop-macos` and `jarvis-ios`. Contains auth, token refresh, WebSocket client, and API models. Built before either Swift client.

### Repo extraction (done first)
- [ ] Extract TUI into `jarvis-tui` — own venv + requirements, no imports from backend repo
- [ ] Create `jarvis-swift-core` — shared Swift Package for macOS and iOS
- [ ] Create remaining client repos with basic project scaffolding

### Features — all clients
- [ ] Login screen — prompts for credentials, stores tokens on success
- [ ] Chat panel — full WebSocket flow, streaming token display
- [ ] Tasks panel — reads `GET /tasks`, updates automatically on `done` frame `refresh` array
- [ ] Memory panel — reads `GET /memory` (stub until Phase 7)
- [ ] Skill approval queue — Admin/Power only, shown based on JWT tier claim
- [ ] User settings — assistant name, preferences
- [ ] Silent token refresh — handled transparently, user never sees it
- [ ] Handles `profile` WebSocket frames — re-fetches `GET /profile` on receipt
- [ ] Reconnects automatically on dropped WebSocket connection

### Admin panel — TUI, Linux desktop, iOS only
- [ ] User management — invite generation, token invalidation, tier changes
- [ ] System status — active connections, server health
- Intentionally minimal — a full observability and statistics dashboard is a future addition

### Token storage
Per-client storage is the current approach. Centralised storage via the server's Vaultwarden instance is a planned future upgrade — see `spec/ideas.md`.

| Client | Storage |
|---|---|
| TUI | `~/.jarvis/auth.json` |
| Linux desktop | `~/.jarvis/auth.json` or libsecret keyring |
| Windows desktop | Windows Credential Manager |
| macOS desktop | Keychain |
| iOS | Keychain |

### Distribution
| Client | Method |
|---|---|
| TUI | Install script (bash) |
| Linux desktop | Install script (clone, venv, deps, optional `.desktop` file) |
| Windows desktop | Installer package (WiX or similar) |
| macOS desktop | `.app` bundle, direct download |
| iOS | TestFlight |

Auto-update for desktop apps is a future addition — see `spec/ideas.md`.

**Exit criteria:** All native clients functional. Admin can generate an invite token, change a user's tier, and force-deauth a user from the TUI or iOS app. macOS and iOS share `jarvis-swift-core`. Full family has their preferred native client alongside the web client. Base development complete.

## Phase 10 — Voice

Voice is an add-on — the rest of the platform is fully functional without it. The specific STT/TTS software may change before this phase is reached given the pace of progress in the voice AI space; the architecture below is the current best guess but should be revisited at Phase 10 planning time.

**Planned architecture:**
- STT and TTS each run as separate Docker containers with internal API endpoints
- FastAPI proxies STT/TTS requests to these containers — clients never call them directly
- Phase 6's Docker Compose will include placeholder service definitions for both containers so the internal network topology is correct from the start, even before Phase 10 implements them properly

**Checklist:**
- [ ] STT container — Whisper (or equivalent at time of implementation)
- [ ] TTS container — Piper (or equivalent at time of implementation)
- [ ] FastAPI STT/TTS proxy endpoints
- [ ] Wake word detection (optional)
- [ ] Voice mode in TUI and web client

**Exit criteria:** Hands-free JARVIS interaction.
