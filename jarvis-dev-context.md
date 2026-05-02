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
- **Active branch:** `phase-3` (rename to `mk1` when convenient)
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

## Mk Status

| Mark | Name | Target | Status |
|---|---|---|---|
| Foundation | Phase 1 (LangGraph/TUI) + Phase 2 (Memory/ChromaDB) | — | ✅ Done |
| Mk1 | Family product — core nodes, web client, server, family onboarded | Summer 2026 | 🔜 **Current** |
| Mk2 | Dev tool — SYSTEM, CODE, Coding Team, admin, tier gating | End of 2027 | ⏳ Pending |
| Mk3 | Complete — native clients, voice | End of 2029 | ⏳ Pending |

---

## Mk1 Checklist

**FastAPI skeleton — complete ✅**
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

**Tool layer:**
- [x] `tools/llm.py` — Ollama wrapper, streaming, fallback logic, `StreamResult` dataclass
- [x] `tools/tokens.py` — token counting for history budget
- [x] Full spec audit of DAG orchestration section (PLANNER + ORCHESTRATOR)

**Remaining nodes:**
- [x] PROMPT_ENGINEER node — `graph/nodes/prompt_engineer.py`
- [x] ROUTER node — `graph/nodes/router.py`
- [x] PLANNER node — `graph/nodes/planner.py` — calls REASONING_MODEL via `tools/llm.py`, receives `intent: list[str]`, produces `step_plan: list[Step]`, sets `error` on failure
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
- [ ] TUI rewritten — connects to FastAPI WebSocket, opens on startup, reconnects automatically on drop
- [ ] `tui/auth.py` — `~/.jarvis/auth.json`, silent refresh, handles 401, deletes on logout, login prompt if missing or expired
- [ ] TUI handles `done` frames and re-fetches panels listed in `refresh`
- [ ] Unit tests alongside every node implementation
- [ ] Pre-commit hook configured — `pytest tests/unit/` blocks commits on failure

**Multi-user verification:**
- [ ] Three test accounts created via invite flow
- [ ] Per-user data scoping verified end-to-end
- [ ] Refresh token rotation
- [ ] Assistant name hotswappable — `PATCH /profile` updates DB, `profile` frame pushed, clients re-fetch `GET /profile`
- [ ] Multiple concurrent users verified

**Web client:**
- [ ] Login screen — prompts for credentials, stores tokens on success
- [ ] Chat panel — full WebSocket flow, streaming token display
- [ ] Tasks panel — reads `GET /tasks`, updates automatically on `done` frame `refresh` array
- [ ] Memory panel — reads `GET /memory` (stub)
- [ ] User settings — assistant name
- [ ] Silent token refresh — transparent, user never sees it
- [ ] Handles `profile` WebSocket frames — re-fetches `GET /profile` on receipt
- [ ] Reconnects automatically on dropped WebSocket connection

**Server deployment:**
- [ ] `PostgresAuthRepository`, `PostgresTaskRepository`, `PostgresHistoryRepository` — full implementations
- [ ] Alembic introduced — all schema changes from this point forward go through migrations
- [ ] Migration script: SQLite → Postgres
- [ ] Docker Compose — Postgres, ChromaDB, Ollama, FastAPI, web client
- [ ] Data on `/tank/docker/jarvis/` (ZFS, auto-snapshotted)
- [ ] Caddy — `jarvis.home`
- [ ] Tailscale access from all devices
- [ ] ofelia for daily maintenance job
- [ ] All clients pointed at server — config update only

**Family onboarding:**
- [ ] Family on Tailscale — invite link per person
- [ ] Family accounts created via invite flow, all register via `jarvis.home`
- [ ] Per-user vaults initialised
- [ ] Shared family vault populated with household knowledge
- [ ] Shared vault ingested — `memory_shared` ChromaDB collection populated

---

## TUI Token Management

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
| 2026-04-23 (1) | Spec reorganised — jarvis-spec.md split into spec/ (12 files). CLAUDE.md updated. |
| 2026-04-23 (2) | Full spec audit — 11 issues resolved. PLANNER + ORCHESTRATOR added. tier_gate redesigned. |
| 2026-04-24 (1) | Second spec audit — 13 issues resolved. CONSTITUTIONAL fully specced. SKILLS node architecture added. |
| 2026-04-27 (1) | Project reframed — Mk1/Mk2/Mk3 replacing phases. Mk1 = family product by summer 2026. SYSTEM, CODE, CONSTITUTIONAL, SKILLS, tier gating moved to Mk2. spec/phases.md, jarvis-dev-context.md, CLAUDE.md updated. |
| 2026-04-28 (1) | Architecture overhaul before nodes — MEMORY_RETRIEVE node replaced with tools/memory.py (per-node retrieval, should_retrieve() + retrieve_context()); ROUTER thinned to intent + skills discovery + tier only; skill_context removed, pending_skills added for ROUTER→PLANNER skill handoff; needs_memory + retrieved_context removed from JarvisState; tier_gate added (was missing); memory_check model added to config; spec/ai.md + spec/architecture.md updated throughout. ROUTER pseudocode is next. |
| 2026-04-28 (2) | PROMPT_ENGINEER and ROUTER nodes complete. tools/log.py (log_improvement), tools/history.py (get_history) written. _write_improve_event moved out of llm.py. intent_tiers + TIER_RANK added to config — replaces hardcoded _GATED_INTENTS set, supports per-intent and per-skill lowest_tier in Mk2. PLANNER is next. |
| 2026-04-29 (1) | PLANNER node complete. pending_skills renamed to detected_skills throughout (state, router, chat.py, both spec files). Design discussions: DAG as list[Step] adjacency list, intent list as type guide not step count, skill_name assigned by LLM with no validation (tiny context window, hallucination risk negligible in Mk1). DECOMPOSER is next. |
| 2026-04-29 (2) | Test suite — pure unit tests complete (test_tokens, test_notify, test_log, test_history). Moved notify_cooldown_seconds, chars_per_token, invite_expire_hours into config.yaml. Key testing principle established: tests assert on concrete expected values, never on mock internals. |
| 2026-05-02 (1) | test_llm.py complete — 4 tests covering happy path, primary fallback, double failure propagation, and _stream chunk yielding. Went through each test case step by step. |
| 2026-05-02 (2) | test_prompt_engineer.py complete — 5 tests covering token join/strip, fallback on exception, correct model, node kwarg, user_id/message_id forwarding. |
| 2026-05-02 (3) | test_router.py complete — 7 tests. Two bugs fixed: router failure now sets error on state (was defaulting to conversation, spec deviation); _BASE_PROMPT curly braces escaped (caused KeyError on .format()). |
| 2026-05-02 (4) | test_planner.py complete — 6 tests. Dropped prompt-content inspection tests (mock call_args = testing mock structure, not behaviour). Tests cover: valid step list, stream_chat exception, invalid JSON, missing required field, depends_on default, skill_name default. |
| 2026-05-02 (5) | test_connections.py complete — 8 tests. autouse fixture clears module-level _registry between tests. AsyncMock used for websocket so push_profile's await send_json works. asyncio.run() used for async push_profile calls instead of pytest-asyncio. |
| 2026-05-02 (6) | test_dependencies.py complete — 12 tests. Fixed client_type validation in dependencies.py (tui/web only for Mk1, mobile is Mk3). spec/auth.md and spec/ai.md updated to match. All unit tests now complete. |
