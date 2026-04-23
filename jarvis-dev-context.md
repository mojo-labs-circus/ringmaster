## JARVIS — Development Context

---

## Machine Timeline

| Period | Machine | Notes |
|---|---|---|
| Phase 3 start → Apr 20 | nomadbaker | Done — no CUDA, light models only, no vault, no ChromaDB |
| Apr 20 → end of May | pearlybaker | **Current** — full GPU, vault, ChromaDB available |
| End of May → server build | nomadbaker | Light dev / prep |
| Server build onwards | home server | All dev moves server-side permanently |

---

## Current Machine — pearlybaker

- **Host:** pearlybaker | **User:** clarkehines | **OS:** Arch Linux
- **GPU:** full CUDA available
- **Active branch:** `phase-3`
- **JARVIS code:** `~/projects/jarvis/`
- **Python venv:** `~/.venvs/jarvis`
- **Dev DBs:** `~/.jarvis/auth.db`, `~/.jarvis/tasks.db`, `~/.jarvis/history.db`
- **Vault:** ✅ available
- **ChromaDB:** ✅ available
- **Ollama:** ✅ available — full model stack (see Model Stack table)
- **All URLs use `localhost`** — Docker service names do not exist yet

**Home server target: summer 2026.**

---

## Model Stack

| Model | Role | nomadbaker | pearlybaker |
|---|---|---|---|
| `qwen2.5:3b` | All roles (stand-in) | ✅ | ❌ |
| `mistral:7b` | Router | ❌ | ✅ |
| `qwen2.5:14b` | General + PLANNER stand-in | ❌ | ✅ |
| `deepseek-coder-v2:16b` | Coding stand-in (CODE node only) | ❌ | ✅ |
| `nomic-embed-text` | Embeddings | ❌ | ✅ |

**Model names are never hardcoded — always read from `config.yaml` via `config.py`.**

---

## Phase Status

| Phase | Name | Status |
|---|---|---|
| 1 | Foundation — LangGraph + TUI skeleton | ✅ Done |
| 2 | Memory — ChromaDB + vault ingestion + RAG | ✅ Done |
| 3 | Tools + FastAPI — all nodes, JWT auth, WebSocket | 🔜 **Current** |
| 4 | Multi-User + Full Auth | ⏳ Pending |
| 5 | Web Client | ⏳ Pending |
| 6 | Server Deployment + Postgres Migration (summer 2026) | ⏳ Pending |
| 7 | Family Onboarding | ⏳ Pending |
| 8 | Coding Team + Skills System | ⏳ Pending |
| 9 | Remaining Clients (iOS, macOS, Windows, Linux desktop) | ⏳ Pending |
| 10 | Voice | ⏳ Pending |

---

## Phase 3 Checklist

**FastAPI skeleton first — before any tool node:**
- [x] Minimal FastAPI server — single `/chat` WebSocket endpoint
- [x] Auth repository — `db/auth/` (models, repository, sqlite, postgres stub, factory)
- [x] `POST /auth/login` — returns access + refresh tokens, inserts `refresh_tokens` row
- [x] `POST /auth/refresh` — validates token hash, issues new access token with current user values
- [x] `POST /auth/logout` — marks refresh token `revoked = true` (current device only)
- [x] `POST /auth/invite` — Admin only, returns one-time token (48hr)
- [x] `POST /auth/register` — open (invite token required), creates user, marks invite used
- [x] `db/schema.py` — `create_tables()`, called from FastAPI lifespan on startup (sqlite only)
- [x] `scripts/seed_db.py` — idempotent, interactive password prompt, creates `clarkehines` admin only
- [x] `JarvisState` updated — all fields present, node-populated fields zero-initialised by FastAPI
- [x] `token_version` validated against DB on every request and every WebSocket message
- [x] FastAPI uses `astream_events` — node-entry status frames from `STATUS_MESSAGES`, mid-node `status_message` forwarded as `status` frames
- [x] WebSocket streaming — typed JSON frames with `message_id`, one invocation at a time per connection, busy messages dropped with status frame
- [x] Conversation history repository — `db/history/` (mirrors `db/tasks/` structure)
- [x] History load → inject into state bounded by `CONTEXT_WINDOW_BUDGET`, FastAPI appends `current_input` as final entry
- [x] History write back after invocation
- [x] `main.py` — `dev` flag in `config.yaml`/`config.py`, drives `reload=` and console log handler
- [x] `notifications/notify.py` — `notify_admin(error_class, message)`, 10-min cooldown
- [x] `RotatingFileHandler` configured in `main.py` — path from `LOG_PATH`, 10 MB / 5 files
- [x] FastAPI global exception handler wired to `notify_admin`
- [x] Daily maintenance job — `maintenance/cleanup.py` (expired tokens, invites, old history, error log threshold)
- [x] **Verify FastAPI end to end with throwaway test client before rewriting TUI**

**Then tool nodes:**
- [x] `tools/llm.py` — Ollama wrapper, streaming, fallback logic, `StreamResult` dataclass
- [x] `tools/tokens.py` — token counting for history budget
- [x] Full spec audit of DAG orchestration section (PLANNER + ORCHESTRATOR)
- [ ] PLANNER node — `graph/nodes/planner.py` — calls REASONING_MODEL via `tools/llm.py`, receives `intent: list[str]`, produces `step_plan: list[Step]`, sets `error` on failure
- [ ] ORCHESTRATOR node — `graph/nodes/orchestrator.py` — reactive loop, dispatches to agent nodes, writes `step_results`, clears `error`/`step_response` between steps, marks blocked steps, routes to RESPONDER when plan exhausted
- [ ] `graph/graph.py` wiring — conditional edge skipping MEMORY_RETRIEVE when `needs_memory: false`, ORCHESTRATOR loop back to itself or forward to RESPONDER, universal error edge routing any node with `error` set directly to RESPONDER
- [ ] TASKS node + `db/tasks/` repository + `GET /tasks` + `DELETE /tasks/{id}`
- [ ] CONVERSATION node — general chat, all tiers
- [ ] WEB node + `tools/search.py` (DuckDuckGo + Playwright)
- [ ] SYSTEM node + `tools/shell.py` — Admin/Power only, interrupt/confirm before every command
- [ ] CODE node + `tools/sandbox.py` — Admin/Power only, single-agent in Phase 3
- [ ] MEMORY node — explicit query/forget, all tiers
- [ ] MEMORY_RETRIEVE node
- [ ] `memory/persist.py` background task
- [ ] `GET /memory` — stub returning `[]` in Phase 3
- [ ] ROUTER updated — `needs_memory` per intent, skills check, sets `tier_gate` list for any tier-gated intents
- [ ] RESPONDER updated — checks `error`, formats for `client_type`, derives and sets `refresh`, formats tier-gate step results using hardcoded per-capability messages from `config.yaml`
- [ ] CONSTITUTIONAL check — `api/constitutional.py` — concurrent async coroutine, watches token buffer, fires `truncate` frame on ethics violation, silent on happy path
- [ ] TUI rewritten — connects to FastAPI WebSocket, opens on startup, reconnects on drop
- [ ] `tui/auth.py` — `~/.jarvis/auth.json`, silent refresh, deletes on logout
- [ ] TUI handles `confirm_request` (disable input), `done` (re-fetch `refresh` panels)
- [ ] Unit tests alongside every node — pre-commit hook runs `pytest tests/unit/`

---

## Session Log

| Date | What happened |
|---|---|
| 2026-03-12 (1) | Architecture planned, spec written |
| 2026-03-13 (1) | Phase 1 complete |
| 2026-03-19 (1) | Phase 2 complete |
| 2026-04-08 (1) | nomadbaker env set up, phase-3 branch opened |
| 2026-04-08 (2) | Architecture rewritten — server-first, multi-user, repository pattern |
| 2026-04-09 (1) | Spec review rounds begin |
| 2026-04-10 (1) | Spec locked at rev 10 |
| 2026-04-11 (1) | Spec airtight, dev context rewritten |
| 2026-04-12 (1) | Auth repository + schema + seed_db complete |
| 2026-04-12 (2) | Auth endpoints written |
| 2026-04-12 (3) | Auth cleanup — profile routes, profile push wired |
| 2026-04-13 (1) | Chat WebSocket complete and verified end-to-end |
| 2026-04-13 (2) | tokens, maintenance, llm.py written; spec rev 25 (DAG orchestration) |
| 2026-04-13 (3) | Spec audit rev 26; codebase audit — 5 issues fixed |
| 2026-04-13 (4) | Spec revs 27–29 — forced deauth (3-step), clients planned, phases reordered |
| 2026-04-13 (5) | CLAUDE.md and jarvis-dev-context reorganised — clear separation of concerns |
| 2026-04-21 (1) | Moved to pearlybaker — full GPU, vault, ChromaDB now available |
| 2026-04-21 (2) | pearlybaker server setup — systemd user unit, venv, models pulled, server live on 0.0.0.0:8000 |
| 2026-04-21 (3) | Tailscale setup — both machines on tailnet, nomadbaker→pearlybaker test verified end-to-end |
| 2026-04-21 (4) | Spec updates — persist.py→vault→ChromaDB flow, dream mode defined, vault structure cleaned up, file watcher added |
| 2026-04-21 (5) | Bug fixes — seed_db missing disabled field, .env inline comment parsing, test script --host arg |
| 2026-04-21 (6) | WebSocket logs now show client hostname and IP (Tailscale MagicDNS reverse lookup) |
| 2026-04-21 (7) | SSH configured — nomadbaker→pearlybaker key auth, password auth disabled on pearlybaker, SSH config added on nomadbaker |
| 2026-04-22 (1) | Spec additions — "Augment, don't replace" core principle, Code of Ethics section, constitutional check node, truncate/retract frame types; jarvis-ideas.md created; spec Future Work section trimmed |
| 2026-04-23 (1) | Spec reorganised — jarvis-spec.md split into spec/ (12 files: north-star, architecture, auth, api, ai, memory, deployment, server, testing, phases, structure, ideas). server-specs.md → spec/server.md, jarvis-ideas.md → spec/ideas.md, jarvis-spec.md deleted. CLAUDE.md updated — spec pointer and stale directory tree removed. |
| 2026-04-23 (2) | Full spec audit — 11 issues resolved. PLANNER + ORCHESTRATOR added to checklists. tier_gate redesigned as list[str] with ORCHESTRATOR pre-blocking. active_project moved to message envelope. CONSTITUTIONAL owns truncate + retract, signals chat.py. spec/improvement.md created — persistent improve.jsonl with 10 event types for fine-tuning. Maintenance split into light/heavy tiers, activity-gated via ConnectedClient.last_activity. Per-node model keys added. History write ordered before done frame. Client frame dispatch clarified. |
