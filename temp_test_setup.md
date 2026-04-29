# Test Suite Setup — Mk1

Work in progress across multiple sessions. Check off items as they land.

---

## Step 0 — Infrastructure

- [x] `pytest.ini` (or `pyproject.toml` `[tool.pytest.ini_options]`) — `testpaths`, `pythonpath = .`
- [x] `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/e2e/__init__.py`
- [x] `tests/conftest.py` — shared fixtures (see below)
- [x] `.git/hooks/pre-commit` — runs `pytest tests/unit/`, blocks commits on failure

### `conftest.py` fixtures
- `user_standard` — `teststandard`, standard tier `User` dataclass (no DB insert)
- `user_power` — `testpower`, power tier `User` dataclass
- `user_admin` — `testadmin`, admin tier `User` dataclass
- `test_db` — temp SQLite file, `create_tables()` called, wiped after each test
- `mock_ollama` — patches `tools.llm.stream_chat`; returns a `StreamResult` with configurable tokens

---

## Step 1 — Unit Tests (`tests/unit/`)

All external dependencies mocked. Pre-commit hook runs these on every commit.

### `test_tokens.py`
- [ ] `count_tokens("")` returns 1 (min clamp)
- [ ] `count_tokens("abcd")` returns 1 (exactly 4 chars)
- [ ] `count_tokens("abcde")` returns 1 (5 chars, floor div)
- [ ] `count_tokens` scales linearly for longer strings
- [ ] `count_messages` sums role + content across multiple dicts
- [ ] `count_messages([])` returns 0

### `test_notify.py`
- [ ] First call fires (logger.warning called)
- [ ] Second call within cooldown suppressed (logger.warning NOT called again)
- [ ] Two distinct `(error_class, message)` pairs each fire independently
- [ ] After cooldown expires, same key fires again (mock `time.monotonic`)
- [ ] `notify_admin` never raises even if internal state is unexpected

### `test_log.py`
- [ ] `log_improvement` writes a valid JSON line to the target file
- [ ] Written entry has correct keys: `ts`, `event`, `user_id`, `message_id`, `data`
- [ ] Extra kwargs land in `data`
- [ ] `OSError` on file write is caught — no exception raised, `notify_admin` called

### `test_history.py` (tools/history.py)
- [ ] Returns last `limit` items from repo result
- [ ] Returns full list when `limit` >= length
- [ ] Returns `[]` when repo raises an exception
- [ ] Calls repo with correct `user_id`

### `test_llm.py`
- [ ] Happy path: returns `StreamResult` with correct model name and token generator
- [ ] Primary model raises → fallback attempted, `log_improvement("model_fallback", ...)` called
- [ ] Fallback succeeds → returns `StreamResult` with `FALLBACK_MODEL`
- [ ] Fallback also raises → exception propagates to caller
- [ ] `_stream` yields tokens from `ChatOllama.stream` chunks

### `test_prompt_engineer.py`
- [ ] `stream_chat` returns tokens → `engineered_message` is joined/stripped result
- [ ] `stream_chat` raises → returns `{"engineered_message": state["current_input"]}` (fallback)
- [ ] Correct model (`PROMPT_ENGINEER_MODEL`) passed to `stream_chat`
- [ ] `node="prompt_engineer"` passed to `stream_chat`
- [ ] `user_id` and `message_id` forwarded correctly

### `test_router.py`
- [ ] Valid JSON from model → correct `intent`, `detected_skills`, `tier_gate`
- [ ] Duplicate intents deduplicated, order preserved
- [ ] Tier gate: standard user + power intent → intent appears in `tier_gate`
- [ ] Tier gate: admin user → `tier_gate` empty for all intents
- [ ] JSON parse failure → defaults `{"intent": ["conversation"], "detected_skills": [], "tier_gate": []}`
- [ ] Parse failure → `log_improvement("router_failure", ...)` called
- [ ] `_format_history` with empty list → returns `"None"`
- [ ] `_format_history` with turns → formats as `"User: ..."` / `"Assistant: ..."` lines

### `test_planner.py`
- [ ] Valid step list from model → `step_plan` list of `Step` dicts with all fields
- [ ] `detected_skills` empty → `skills_block` is `"None"` in prompt
- [ ] `intent` empty → `intents_block` defaults to `"conversation"`
- [ ] Inference exception → `{"error": "PLANNER failed to produce a step plan"}`
- [ ] Valid JSON but missing required step field → `{"error": "PLANNER output was malformed"}`
- [ ] `depends_on` defaults to `[]` when absent from step data
- [ ] `skill_name` defaults to `None` when absent from step data

### `test_connections.py`
- [ ] `register` adds client to registry under correct `user_id`
- [ ] Second `register` for same user appends (two clients)
- [ ] `deregister` removes client; entry deleted when list empty
- [ ] `deregister` unknown `user_id` is no-op (no exception)
- [ ] `push_profile` calls `send_json` with correct frame on each registered client
- [ ] `push_profile` swallows exception from dead connection (send raises)
- [ ] `push_profile` for unknown `user_id` is no-op

### `test_dependencies.py`
- [ ] `_get_user_from_payload`: missing `user_id` → raises `HTTPException` with given status
- [ ] `_get_user_from_payload`: missing `token_version` → raises `HTTPException`
- [ ] `_get_user_from_payload`: user not found in repo → raises `HTTPException`
- [ ] `_get_user_from_payload`: `user.disabled` → raises `HTTPException`
- [ ] `_get_user_from_payload`: token_version mismatch → raises `HTTPException`
- [ ] `_get_user_from_payload`: all valid → returns `User`
- [ ] `get_connected_client_ws`: invalid `client_type` → raises 403
- [ ] `get_connected_client_ws`: valid `client_type` (`tui`) → returns `ConnectedClient`
- [ ] `require_admin`: non-admin user → raises 403
- [ ] `require_power_or_above`: standard user → raises 403

---

## Step 2 — Integration Tests (`tests/integration/`)

Real SQLite (`test_db` fixture). FastAPI `TestClient`. Ollama replaced by `mock_ollama`.

### `test_auth_sqlite.py`
- [ ] `create_user` + `get_user` round-trip
- [ ] `get_user` returns `None` for unknown username
- [ ] `increment_token_version` increments by 1
- [ ] `update_assistant_name` persists change
- [ ] `disable_user` / `enable_user` toggle `disabled`
- [ ] `create_refresh_token` stamps `id` back on dataclass
- [ ] `get_refresh_token_by_hash` returns correct row
- [ ] `revoke_refresh_token` sets `revoked = True`
- [ ] `create_invite` stamps `id` back on dataclass
- [ ] `get_invite_by_hash` returns correct row
- [ ] `mark_invite_used` sets `used = True`

### `test_history_sqlite.py`
- [ ] `save` + `load` round-trip returns same messages
- [ ] User A cannot read user B's history (scoping)
- [ ] `load` returns `[]` for unknown user
- [ ] Multiple saves accumulate correctly

### `test_tasks_sqlite.py`
- [ ] Create + read round-trip
- [ ] User A cannot read user B's tasks (scoping)
- [ ] Delete removes the row
- [ ] List returns only tasks for given user

### `test_auth_routes.py`
- [ ] `POST /auth/login` — valid credentials → access + refresh tokens returned
- [ ] `POST /auth/login` — wrong password → 401
- [ ] `POST /auth/login` — unknown user → 401
- [ ] `POST /auth/login` — disabled user → 401
- [ ] `POST /auth/refresh` — valid token → new access token
- [ ] `POST /auth/refresh` — revoked token → 401
- [ ] `POST /auth/refresh` — expired token → 401
- [ ] `POST /auth/logout` — valid token → token revoked in DB
- [ ] `POST /auth/invite` — admin user → invite token returned
- [ ] `POST /auth/invite` — non-admin → 403
- [ ] `POST /auth/register` — valid invite → user created, invite marked used
- [ ] `POST /auth/register` — used invite → 400
- [ ] `POST /auth/register` — expired invite → 400

### `test_chat_ws.py`
- [ ] Connect with valid token → accepted
- [ ] Connect with invalid token → 403
- [ ] Send message → frames arrive in order: at least one `status`, then `token` frames, then `done`
- [ ] `done` frame contains `message_id` matching request
- [ ] Second message while first in-progress → busy `status` frame, first not interrupted
- [ ] History written after invocation completes

### `test_profile_routes.py`
- [ ] `GET /profile` → returns `assistant_name` and `tier`
- [ ] `PATCH /profile` → updates `assistant_name`, persisted in DB
- [ ] `PATCH /profile` → triggers `push_profile` (profile frame sent to active connections)
- [ ] Unauthenticated `GET /profile` → 401

### `test_cleanup.py`
- [ ] Expired refresh tokens deleted
- [ ] Non-expired refresh tokens preserved
- [ ] Expired invites deleted
- [ ] Non-expired invites preserved
- [ ] History rows older than threshold deleted
- [ ] Recent history rows preserved

---

## Step 3 — E2E (`tests/e2e/`)

Real SQLite, real Ollama. Run at Mk1 end only.

### `test_full_flow.py`
- [ ] Authenticate → get token
- [ ] Connect WebSocket with token
- [ ] Send message → `status` frames arrive, `token` frames arrive, `done` frame arrives
- [ ] Frame types appear in correct order
- [ ] `done` frame has correct `message_id`
- [ ] History row written to DB after completion
- [ ] Assertions structural only — no assertions on model output content

---

## Completion Checklist (mirrors `jarvis-testing-context.md`)

Update both files when a test file is marked done.

### Unit
- [ ] `test_tokens.py`
- [ ] `test_notify.py`
- [ ] `test_log.py`
- [ ] `test_history.py`
- [ ] `test_llm.py`
- [ ] `test_prompt_engineer.py`
- [ ] `test_router.py`
- [ ] `test_planner.py`
- [ ] `test_connections.py`
- [ ] `test_dependencies.py`

### Integration
- [ ] `test_auth_sqlite.py`
- [ ] `test_history_sqlite.py`
- [ ] `test_tasks_sqlite.py`
- [ ] `test_auth_routes.py`
- [ ] `test_chat_ws.py`
- [ ] `test_profile_routes.py`
- [ ] `test_cleanup.py`

### E2E
- [ ] `test_full_flow.py`
