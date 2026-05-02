# JARVIS — Testing Context

## Three Tiers

| Tier | Lives in | Ollama | SQLite | When to run |
|---|---|---|---|---|
| Unit | `tests/unit/` | mocked | mocked | every commit (pre-commit hook) |
| Integration | `tests/integration/` | mocked | real (temp file) | manually, when verifying a data layer |
| E2E | `tests/e2e/` | real | real | milestones only |

Full details in `spec/testing.md`.

## Running Tests

```bash
# Unit only (fast — what the pre-commit hook runs)
pytest tests/unit/

# Integration only
pytest tests/integration/

# Unit + integration
pytest tests/unit/ tests/integration/

# Full suite including e2e (requires Ollama running)
pytest tests/
```

## Shared Fixtures (`tests/conftest.py`)

- **`user_standard`** — `teststandard`, standard tier `User` dataclass
- **`user_power`** — `testpower`, power tier `User` dataclass
- **`user_admin`** — `testadmin`, admin tier `User` dataclass
- **`test_db`** — fresh SQLite file in a temp directory, all tables created, wiped after each test; path passed to the repository under test
- **`mock_ollama`** — patches `stream_chat` so it never calls Ollama; returns a `StreamResult` with whatever tokens you configure

Fixtures return objects only — tests that need a user in the database insert explicitly via the repository.

## Coverage Tracker

### Unit Tests

| Source file | Test file | Status |
|---|---|---|
| `graph/nodes/prompt_engineer.py` | `tests/unit/test_prompt_engineer.py` | ✅ |
| `graph/nodes/router.py` | `tests/unit/test_router.py` | ✅ |
| `graph/nodes/planner.py` | `tests/unit/test_planner.py` | ✅ |
| `tools/llm.py` | `tests/unit/test_llm.py` | ✅ |
| `tools/history.py` | `tests/unit/test_history.py` | ✅ |
| `tools/tokens.py` | `tests/unit/test_tokens.py` | ✅ |
| `notifications/notify.py` | `tests/unit/test_notify.py` | ✅ |
| `api/connections.py` | `tests/unit/test_connections.py` | ✅ |
| `api/dependencies.py` | `tests/unit/test_dependencies.py` | ✅ |

### Integration Tests

| Source file | Test file | Status |
|---|---|---|
| `db/auth/sqlite.py` | `tests/integration/test_auth_sqlite.py` | ❌ |
| `db/history/sqlite.py` | `tests/integration/test_history_sqlite.py` | ❌ |
| `db/tasks/sqlite.py` | `tests/integration/test_tasks_sqlite.py` | ❌ |
| `api/routes/auth.py` | `tests/integration/test_auth_routes.py` | ❌ |
| `api/routes/chat.py` | `tests/integration/test_chat_ws.py` | ❌ |
| `api/routes/profile.py` | `tests/integration/test_profile_routes.py` | ❌ |
| `maintenance/cleanup.py` | `tests/integration/test_cleanup.py` | ❌ |

### E2E Tests

| Scenario | Test file | Status |
|---|---|---|
| Full message flow — auth, WebSocket, graph, history | `tests/e2e/test_full_flow.py` | ❌ (Mk1 end) |

### Not Tested Directly (N/A)

| File | Reason |
|---|---|
| `config.py` | no logic — reads files and env vars only |
| `graph/state.py` | TypedDicts — no logic |
| `graph/graph.py` | stub — graph wiring tests added here once real nodes replace the stub |
| `graph/nodes/skills.py` | stub — no logic yet |
| `db/schema.py` | DDL only — covered implicitly by integration test setup |
| `db/*/repository.py` | abstract base classes |
| `db/*/models.py` | dataclasses — no logic |
| `db/*/postgres.py` | stubs — Mk2 |
| `db/*/factory.py` | env switch only — no logic |
| `api/routes/tasks.py` | deferred — add to integration when TASKS node is implemented |
| `api/server.py` | wiring only — exception handler covered implicitly by integration tests |

## Pre-Commit Hook

Configured — `.git/hooks/pre-commit` activates `~/.venvs/jarvis` and runs `pytest tests/unit/`. Blocks commits on failure.
