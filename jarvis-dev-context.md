## JARVIS — Development Session Context
> Paste this at the start of every Claude Code session. Update as phases complete.
> Lives at: `~/jarvis-brain/07-system/JARVIS-DEV-CONTEXT.md`

---

## Machine Timeline

| Period | Machine | Notes |
|---|---|---|
| Now → ~Apr 20 | nomadbaker | Current — no CUDA, light models only, no vault, no ChromaDB |
| ~Apr 20 → end of May | pearlybaker | Full GPU, vault, ChromaDB available |
| End of May → server build | nomadbaker | Light dev / prep |
| Server build onwards | home server | All dev moves server-side permanently |

---

## Current Machine — nomadbaker
- **Host:** nomadbaker | **User:** clarkehines | **OS:** Arch Linux
- **GPU:** Intel Arc 140V — no CUDA, no ROCm
- **Active branch:** `phase-3`
- **JARVIS code:** `~/projects/jarvis/`
- **Python venv:** `~/.venvs/jarvis`
- **Dev DBs:** `~/.jarvis/auth.db`, `~/.jarvis/tasks.db`, `~/.jarvis/history.db`
- **Vault:** ❌ not available on this machine
- **ChromaDB:** ❌ not available on this machine

**Home server target: summer 2026.**

---

## Model Stack

| Model | Role | nomadbaker | pearlybaker |
|---|---|---|---|
| `qwen2.5:3b` | All roles (stand-in) | ✅ | ❌ |
| `mistral:7b` | Router | ❌ | ✅ |
| `qwen2.5:14b` | General stand-in | ❌ | ✅ |
| `deepseek-coder-v2:16b` | Coding stand-in | ❌ | ✅ |
| `nomic-embed-text` | Embeddings | ❌ | ✅ |

**Model names are never hardcoded — always read from `config.yaml` via `config.py`.**

---

## Phase Status

| Phase | Name | Status |
|---|---|---|
| 1 | Foundation — LangGraph + TUI skeleton | ✅ Done |
| 2 | Memory — ChromaDB + vault ingestion + RAG | ✅ Done |
| 3 | Tools + FastAPI — all nodes, JWT auth, WebSocket | 🔜 **Current** |
| 3.5 | Coding Team + Skills System | ⏳ Pending |
| 4 | Multi-User + Full Auth | ⏳ Pending |
| 5 | Postgres Migration | ⏳ Pending |
| 6 | Server Deployment (summer 2026) | ⏳ Pending |
| 7–9 | Web Dashboard, Onboarding, Voice | ⏳ Pending |

---

## Phase 3 Checklist

**FastAPI skeleton first — before any tool node:**
- [x] Minimal FastAPI server — single `/chat` WebSocket endpoint
- [x] Auth repository — `db/auth/` (models, repository, sqlite, postgres stub, factory)
- [x] `POST /auth/login` — returns access + refresh tokens, inserts `refresh_tokens` row
- [x] `POST /auth/refresh` — validates token hash, issues new access token with current user values
- [x] `POST /auth/logout` — marks refresh token `revoked = true` (current device only; `token_version` reserved for forced deauth)
- [x] `POST /auth/invite` — Admin only, returns one-time token (48hr)
- [x] `POST /auth/register` — open (invite token required), creates user, marks invite used
- [x] `db/schema.py` — `create_tables()`, called from FastAPI lifespan on startup (sqlite only)
- [x] `scripts/seed_db.py` — idempotent, interactive password prompt, creates `clarkehines` admin only
- [x] `JarvisState` updated — all fields present, node-populated fields zero-initialised by FastAPI
- [x] `token_version` validated against DB on every request and every WebSocket message
- [x] FastAPI uses `astream_events` — node-entry status frames from `STATUS_MESSAGES`, mid-node `status_message` forwarded as `status` frames
- [x] WebSocket streaming — typed JSON frames with `message_id`, one invocation at a time per connection, busy messages dropped with status frame (no queue)
- [x] Conversation history repository — `db/history/` (mirrors `db/tasks/` structure)
- [x] History load → inject into state bounded by `CONTEXT_WINDOW_BUDGET`, FastAPI appends `current_input` as final entry
- [x] History write back after invocation
- [x] `main.py` — `dev` flag in `config.yaml`/`config.py`, drives `reload=` and console log handler
- [x] `notifications/notify.py` — `notify_admin(error_class, message)`, 10-min cooldown keyed on `(error_class, message)` tuple
- [x] `RotatingFileHandler` configured in `main.py` — path from `LOG_PATH`, 10 MB / 5 files
- [x] FastAPI global exception handler wired to `notify_admin`
- [x] Daily maintenance job — `maintenance/cleanup.py` (expired tokens, invites, old history, error log threshold)
- [x] **Verify FastAPI end to end with throwaway test client before rewriting TUI**

**Then tool nodes:**
- [x] `tools/llm.py` — Ollama wrapper, streaming, fallback logic, `StreamResult` dataclass
- [x] `tools/tokens.py` — token counting for history budget
- [ ] Full spec audit of DAG orchestration section (PLANNER + ORCHESTRATOR) — next session
- [ ] TASKS node + `db/tasks/` repository + `GET /tasks` + `DELETE /tasks/{id}`
- [ ] CONVERSATION node — general chat, all tiers
- [ ] WEB node + `tools/search.py` (DuckDuckGo + Playwright)
- [ ] SYSTEM node + `tools/shell.py` — Admin/Power only, interrupt/confirm before every command
- [ ] CODE node + `tools/sandbox.py` — Admin/Power only, single-agent in Phase 3
- [ ] MEMORY node — explicit query/forget, all tiers
- [ ] MEMORY_RETRIEVE node
- [ ] `memory/persist.py` background task
- [ ] `GET /memory` — stub returning `[]` in Phase 3
- [ ] ROUTER updated — `needs_memory` per intent, skills check
- [ ] RESPONDER updated — checks `error`, formats for `client_type`, derives and sets `refresh`
- [ ] TUI rewritten — connects to FastAPI WebSocket, opens on startup, reconnects on drop
- [ ] `tui/auth.py` — `~/.jarvis/auth.json`, silent refresh, deletes on logout
- [ ] TUI handles `confirm_request` (disable input), `done` (re-fetch `refresh` panels)
- [ ] Unit tests alongside every node — pre-commit hook runs `pytest tests/unit/`

---

## Standing Rules for Claude Code

### Architecture rules
- Repository pattern everywhere — nodes never touch raw SQL or storage directly
- All data operations scoped to `user_id` — no global queries
- Model names always from `config.yaml` via `config.py` — never hardcoded
- Secrets via env vars only — `JARVIS_SECRET_KEY` hard-fails if unset
- One branch per phase — merge to main only when complete and verified
- Write tests alongside implementation — never defer
- Comment the why, not the what

### Ownership rules — how Claude Code fits into this project

**Explain before writing.** Before producing any file, Claude explains: what the file is for, why it's structured the way it is, and any non-obvious design decisions. The user reads and approves the plan before any code is written. If anything is unclear, ask before the code appears — not after.

**Boilerplate vs logic — two different modes.**
- Boilerplate (repository skeletons, dataclasses, factory pattern, test fixtures) can be generated wholesale by Claude — the pattern is understood, it just needs typing.
- Logic-heavy components (all graph nodes, routing decisions, state management, error handling) are co-written. For every node, the user writes a first draft or pseudocode outline first. Claude then fills in, corrects, or extends — never produces the node from scratch without user input to anchor it.

**System prompt content is always written by the user.** Claude implements the infrastructure that calls Ollama. The actual prompt text — what each node tells the model about its role — comes from the user. That's where JARVIS's personality lives and it should never be AI-generated filler.

**Comprehension gate before moving on.** Before marking any component done and moving to the next, the user should be able to explain every function in it in plain English. If something isn't clear, stop and ask Claude to walk through it. Do this now, not six months later when a bug appears.

**If you want to edit a file Claude writes, do it — don't just passively approve it.** There's no obligation to edit every file, but if something feels off, change it rather than letting it slide.

**Call out spec deviations immediately.** If Claude proposes something that isn't in the spec or contradicts it, flag it before the code lands. The spec is the source of truth — not whatever seems convenient in the moment. If the spec needs updating, update it explicitly and intentionally.

**Commit and push after every completed bulletpoint on the phase checklist.** No accumulating a session's worth of work before committing.

---

## Session Log

| Date | What happened |
|---|---|
| 2026-03-12 | Architecture planned, vault created, spec written |
| 2026-03-13 | Phase 1 complete — LangGraph skeleton, routing, TUI, alias working |
| 2026-03-19 | Phase 2 complete — ChromaDB, ingestion, retrieval, MEMORY node |
| 2026-04-08 | nomadbaker env set up, `config.yaml` + `config.py` built, `phase-3-tools` branch opened |
| 2026-04-08 | Architecture rewritten — server-first, multi-user, repository pattern |
| 2026-04-09–10 | Nine spec review rounds — spec locked at rev 10 |
| 2026-04-11 | Spec called airtight. Dev context rewritten to match. Standing rules expanded with ownership section. On nomadbaker. |
| 2026-04-12 | Auth repository complete — `db/auth/` (models, repository, sqlite, postgres stub, factory) + `db/schema.py`. Spec updated: `...` convention for abstract methods, task `id` changed to integer, priority required on creation, logout clears UI immediately. `scripts/seed_db.py` written and verified — `clarkehines` admin created. Next: auth endpoints. |
| 2026-04-12 | Auth endpoints written — `api/auth.py`, `api/schemas.py`, `api/dependencies.py`. Major spec decisions: `assistant_name` removed from JWT (moved to `GET /profile`), `token_version` increment reserved for forced deauth only, normal logout revokes current device only, brute force config keys added. Cleanup pass needed next session — see CLAUDE.md current task. |
| 2026-04-12 | Auth cleanup pass complete — `get_current_user` imported in `auth.py`, `assistant_name` removed from `_build_access_token` payload, `ProfileResponse` + `ProfileUpdateRequest` added to `schemas.py`, `GET /profile` + `PATCH /profile` added in `api/routes/profile.py`, both auth and profile routers wired into `server.py`. Profile frame `message_id` uses `__push__` sentinel. Next: `main.py` dev flag. |
| 2026-04-13 | Chat WebSocket endpoint complete and verified end-to-end. Refactored `dependencies.py` — `_decode_token` + `_get_user_from_payload` split so JWT decoded once, `ConnectedClient` dataclass + `get_connected_client_ws` added for WebSocket routes needing both user and client_type. Added `api/connections.py` — connection registry for profile push. Wrote full `chat_ws` — auth, per-message token_version check, busy-drop, JarvisState construction, `astream_events` loop, history load/write. Moved `api/auth.py` → `api/routes/auth.py` — all routes in routes/. Extracted `logging_config.py` from `main.py` and added FastAPI lifespan to fix logging in uvicorn reload mode. End-to-end verified with `scripts/test_chat_ws.py`. Next: `tools/tokens.py`, then daily maintenance job, then tool nodes. |
| 2026-04-13 | `tools/tokens.py` written — character-based heuristic, wired into `db/history/sqlite.py` load(). `maintenance/cleanup.py` written and verified. `tools/llm.py` written — `ChatOllama` streaming wrapper, fallback model support, `StreamResult` dataclass. Spec updated to rev 25 — DAG orchestration architecture: PLANNER node (REASONING_MODEL, produces StepPlan), ORCHESTRATOR node (reactive execution, dependency-aware failure isolation), `step_plan` and `step_results` added to JarvisState. Next session: full spec audit of orchestration section, then TASKS node. |
