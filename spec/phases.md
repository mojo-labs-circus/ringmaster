# Build Marks

## Foundation ✅
Phase 1 (Foundation) and Phase 2 (Memory) are complete — LangGraph skeleton, TUI, Ollama routing, ChromaDB, vault ingestion, RAG. These form the base everything else builds on.

---

## Mk1 — Family Product *(current)*
> Dad can use it. The whole family is on it. That's the bar.

**Target:** End of summer 2026
**Branch:** `mk1` (currently `phase-3` — rename when convenient)

Admin and power features (SYSTEM node, CODE node, CONSTITUTIONAL check, tier gating) live in Mk2. Mk1 is one tier — everyone gets the same capabilities.

**FastAPI skeleton ✅ complete** — WebSocket, JWT auth, refresh, logout, invite, register, profile, history, maintenance, logging, notify_admin all built and verified.

### Remaining nodes

- [ ] PLANNER node — `graph/nodes/planner.py` — calls REASONING_MODEL via `tools/llm.py`, receives `intent: list[str]`, produces `step_plan: list[Step]`, sets `error` on failure
- [ ] ORCHESTRATOR node — `graph/nodes/orchestrator.py` — reactive loop, dispatches to CONVERSATION, TASKS, WEB, and MEMORY agent nodes, writes `step_results`, clears `error`/`step_response` between steps, marks blocked steps, routes to RESPONDER when plan exhausted
- [ ] `graph/graph.py` wiring — conditional edge skipping MEMORY_RETRIEVE when `needs_memory: false`, ORCHESTRATOR loop back to itself or forward to RESPONDER, universal error edge routing any node with `error` set directly to RESPONDER
- [ ] TASKS node + `db/tasks/` repository + `GET /tasks` + `DELETE /tasks/{id}`
- [ ] CONVERSATION node — general chat, all users, calls `tools/llm.py` with `messages` and `retrieved_context`
- [ ] WEB node + `tools/search.py` (DuckDuckGo + Playwright)
- [ ] MEMORY node — explicit query/forget against ChromaDB, scoped to `user_id` `[pearlybaker only]`
- [ ] MEMORY_RETRIEVE node — queries ChromaDB, populates `retrieved_context` `[pearlybaker only]`
- [ ] `memory/persist.py` — asyncio background task, evaluates exchange, writes to vault then ingests into ChromaDB `[pearlybaker only]`
- [ ] `GET /memory` — stub returning `[]`
- [ ] ROUTER updated — `needs_memory` flag per intent. No tier gating in Mk1 — all users have equal access
- [ ] RESPONDER updated — checks `error` field, derives and sets `refresh` list from `intent`, formats response for `client_type`
- [ ] TUI rewritten — connects to FastAPI WebSocket, opens on startup, reconnects automatically on drop, disables input on `confirm_request`
- [ ] `tui/auth.py` — `~/.jarvis/auth.json`, silent refresh, handles 401 token version mismatch, deletes on logout, login prompt if missing or expired
- [ ] TUI handles `done` frames and re-fetches panels listed in `refresh`
- [ ] Unit tests alongside every node
- [ ] Pre-commit hook — `pytest tests/unit/` blocks commits on failure

### Multi-user verification

- [ ] Three test accounts created via invite flow
- [ ] Per-user data scoping verified end-to-end — no user can see another's tasks, history, or memory
- [ ] Refresh token rotation
- [ ] Assistant name hotswappable — `PATCH /profile` updates DB, `profile` frame pushed to all active connections, clients re-fetch `GET /profile`
- [ ] Multiple concurrent users verified

### Web client

- [ ] Login screen — prompts for credentials, stores tokens on success
- [ ] Chat panel — full WebSocket flow, streaming token display
- [ ] Tasks panel — reads `GET /tasks`, updates automatically on `done` frame `refresh` array
- [ ] Memory panel — reads `GET /memory` (stub until Mk2 memory UI)
- [ ] User settings — assistant name
- [ ] Silent token refresh — transparent, user never sees it
- [ ] Handles `profile` WebSocket frames — re-fetches `GET /profile` on receipt
- [ ] Reconnects automatically on dropped WebSocket connection
- [ ] Token storage: httpOnly cookie for refresh token, memory-only for access token

### Server deployment

- [ ] `PostgresAuthRepository` full implementation
- [ ] `PostgresTaskRepository` full implementation
- [ ] `PostgresHistoryRepository` full implementation
- [ ] Alembic introduced — all schema changes from this point forward go through migrations
- [ ] Migration script: SQLite → Postgres
- [ ] Docker Compose — Postgres, ChromaDB, Ollama, FastAPI, web client
- [ ] Data on `/tank/docker/jarvis/` (ZFS, auto-snapshotted)
- [ ] Caddy — `jarvis.home`
- [ ] Tailscale access from all devices
- [ ] ofelia for daily maintenance job
- [ ] All clients pointed at server — config update only, no code changes

### Family onboarding

- [ ] Family on Tailscale — invite link per person, NordVPN coexistence guide where needed
- [ ] Family accounts created via invite flow, all register via `jarvis.home`
- [ ] Per-user vaults initialised
- [ ] Shared family vault populated with household knowledge
- [ ] Shared vault ingested — `memory_shared` ChromaDB collection populated

### Exit criteria

Family can log in from any browser on the tailnet, chat with JARVIS, manage tasks, search the web, and JARVIS remembers things about them across sessions. Clarke has TUI working alongside the web client. All data on home server, ZFS, behind Tailscale. Any family member can get an account via the invite flow. No admin panel or power features required — those are Mk2.

---

## Mk2 — Dev Tool
> JARVIS helps Clarke build. Clarke can admin it properly.

**Target:** End of 2027

All the power and admin features deferred from Mk1, plus the Coding Team that enables JARVIS to help build Mk3.

### Power + admin features

- [ ] SYSTEM node + `tools/shell.py` — Admin/Power only, interrupt/confirm before every command, path sandboxing against `ALLOWED_PATHS`
- [ ] CODE node + `tools/sandbox.py` — Admin/Power only, sandboxed code execution, calls `tools/vault.py` for project context
- [ ] CONSTITUTIONAL check — `api/constitutional.py` — concurrent async coroutine, watches token buffer, fires `truncate` frame on ethics violation, silent on happy path
- [ ] Full tier gating — ROUTER sets `tier_gate` list for Admin/Power-only intents, RESPONDER formats tier-gate messages from `config.yaml`
- [ ] Admin endpoints — `PATCH /admin/users/{username}` for tier changes and forced deauth (three-step sequence from `spec/auth.md`)
- [ ] Admin panel in web client — invite generation, user management, tier changes, system status

### Coding Team

A dedicated planning session is required before any Coding Team implementation — internal architecture (sandbox boundaries, interruption model, loop behaviour, Tester constraints) must be fully specified first.

- [ ] Dedicated Coding Team planning session
- [ ] Architect, Coder, Reviewer, Tester nodes as LangGraph subgraph
- [ ] Each subgraph node writes granular `status_message` updates
- [ ] On cancel at any interrupt, hardcoded cancellation message — no inference call
- [ ] Tier gate — Admin and Power only
- [ ] Reviewer → Coder loop with configurable max iterations

### Skills system

- [ ] SKILLS node — full implementation
- [ ] ORCHESTRATOR → SKILLS conditional edge wired (`current_step.intent == "skill"`)
- [ ] Skills vault structure — personal (`skills_{user_id}`) and shared (`skills_shared`)
- [ ] Skill ingestion pipelines
- [ ] ROUTER checks personal + shared skills before every action
- [ ] Skill approval queue in web client — Admin/Power only
- [ ] Assistant proposes skills → `pending/` for review

### Exit criteria

Clarke can run shell commands and execute code via JARVIS. Coding Team working for complex tasks. Skills system live — ROUTER retrieves from personal and shared collections. Admin panel working. Tier gating enforced. JARVIS starts helping build JARVIS.

---

## Mk3 — Cool JARVIS
> Voice, native clients, whatever Mk1 and Mk2 usage reveals is actually needed.

**Target:** End of 2029 (not locked — shaped by real usage from Mk1 and Mk2)

Native clients built with Mk2's Coding Team assistance.

### Native clients

- [ ] `jarvis-swift-core` — shared Swift Package (auth, token refresh, WebSocket client, API models) consumed by both iOS and macOS clients
- [ ] `jarvis-ios` — Swift/SwiftUI, everyone — admin panel for Clarke
- [ ] `jarvis-desktop-macos` — Swift/SwiftUI, everyone else
- [ ] `jarvis-desktop-windows` — C#/WinUI 3, brother
- [ ] `jarvis-desktop-linux` — Python/GTK4 + libadwaita, Clarke — admin panel
- [ ] TUI extracted to `jarvis-tui` own repo, own venv

### Voice

The specific STT/TTS software may change before this phase — revisit at Mk3 planning time.

- [ ] STT container (Whisper or equivalent)
- [ ] TTS container (Piper or equivalent)
- [ ] FastAPI STT/TTS proxy endpoints
- [ ] Voice mode in web client and iOS

### Exit criteria

Full native experience on every family device. Hands-free JARVIS. The complete platform.
