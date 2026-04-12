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
- [ ] Minimal FastAPI server — single `/chat` WebSocket endpoint
- [ ] Auth repository — `db/auth/` (models, repository, sqlite, postgres stub, factory)
- [ ] `POST /auth/login` — returns access + refresh tokens, inserts `refresh_tokens` row
- [ ] `POST /auth/refresh` — validates token hash, issues new access token with current user values
- [ ] `POST /auth/logout` — increments `token_version`, marks refresh token `revoked = true`
- [ ] `POST /auth/invite` — Admin only, returns one-time token (48hr)
- [ ] `POST /auth/register` — open (invite token required), creates user, marks invite used
- [ ] `db/schema.py` — `create_tables()`, called from FastAPI lifespan on startup (sqlite only)
- [ ] `scripts/seed_db.py` — idempotent, interactive password prompt, creates `clarkehines` admin only
- [ ] `JarvisState` updated — all fields present, node-populated fields zero-initialised by FastAPI
- [ ] `token_version` validated against DB on every request and every WebSocket message
- [ ] FastAPI uses `astream_events` — node-entry status frames from `STATUS_MESSAGES`, mid-node `status_message` forwarded as `status` frames
- [ ] WebSocket streaming — typed JSON frames with `message_id`, one invocation at a time per connection, queue with `"One moment..."` acknowledgement
- [ ] Conversation history repository — `db/history/` (mirrors `db/tasks/` structure)
- [ ] History load → inject into state bounded by `CONTEXT_WINDOW_BUDGET`, FastAPI appends `current_input` as final entry
- [ ] History write back after invocation
- [ ] `main.py` — uvicorn, `reload=True` in dev
- [ ] `monitoring/notify.py` — `notify_admin(error_class, message)`, 10-min cooldown
- [ ] `RotatingFileHandler` configured in `main.py` — path from `LOG_PATH`, 10 MB / 5 files
- [ ] FastAPI global exception handler wired to `notify_admin`
- [ ] Daily maintenance job — `maintenance/cleanup.py` (expired tokens, invites, old history, error log threshold)
- [ ] **Verify FastAPI end to end with throwaway test client before rewriting TUI**

**Then tool nodes:**
- [ ] `tools/llm.py` — Ollama wrapper, streaming, timeout, fallback logic
- [ ] `tools/tokens.py` — token counting for history budget
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
