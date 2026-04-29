# Testing Strategy

## Philosophy
Tests are written alongside implementation — never deferred. The goal is confidence that the system works correctly, not coverage for its own sake.

## Three-Tier Structure

```
tests/
├── conftest.py          # Shared fixtures — test users, test_db, mock_ollama
├── unit/                # All mocked — pre-commit hook, must pass before every commit
│   ├── test_prompt_engineer.py
│   ├── test_router.py
│   ├── test_connections.py    # connection registry — register/deregister/push_profile
│   ├── test_dependencies.py   # security-critical — token rejection logic
│   └── ...
├── integration/         # Real SQLite + FastAPI TestClient, Ollama mocked — run manually
│   ├── test_auth_routes.py
│   ├── test_chat_ws.py
│   ├── test_auth_sqlite.py
│   └── ...
└── e2e/                 # Full stack, real Ollama — run at milestones only
    └── test_full_flow.py
```

## Unit Tests (`tests/unit/`)
All external dependencies mocked. Tests verify that nodes read from state correctly, call the right functions with the right arguments, handle `error` state properly, and produce correctly structured output. Also covers security-critical dependency logic — token rejection conditions are tested here because they are pure conditional branches that do not require a real DB or real tokens.

**Cadence:** pre-commit hook — `pytest tests/unit/` blocks every commit.

## Integration Tests (`tests/integration/`)
Real SQLite test database (temp file, wiped per test). FastAPI TestClient for route tests. Ollama replaced with `mock_ollama` fixture (hardcoded responses). Tests verify the repository layer end to end and full auth and WebSocket flows — data goes in, comes back out correctly, `user_id` scoping holds, history budget trimming works, login/refresh/logout/invite/register behave correctly under both happy path and rejection conditions, WebSocket frame protocol produces the right frame types in the right order.

**Cadence:** run manually when verifying a full data layer, repository change, or route behaviour.

## End-to-End Tests (`tests/e2e/`)
Full stack — real SQLite, real Ollama running. Tests a complete user flow: authenticate, send a message over WebSocket, graph runs all nodes, frames arrive in the correct order, history is persisted. Assertions are structural (did a `done` frame arrive, did the right frame types appear, was a history row written) — not on model output content, which is non-deterministic.

**Cadence:** milestones only — end of Mk1, before family onboarding, before major releases.

## Shared Fixtures (`tests/conftest.py`)
- `user_standard` — `teststandard`, standard tier `User` dataclass
- `user_power` — `testpower`, power tier `User` dataclass
- `user_admin` — `testadmin`, admin tier `User` dataclass
- `test_db` — fresh SQLite database at a temp file path, all tables created, wiped after each test
- `mock_ollama` — patches `stream_chat` to return hardcoded `StreamResult` objects; never calls Ollama

Fixtures return objects only — tests that need a user in the database insert explicitly via the repository.

## Pre-Commit Hook
`pytest tests/unit/` runs automatically before every commit. Commits are blocked if any unit test fails. Integration and e2e tests are not in the pre-commit hook. Hook must be configured before the first unit test is written.
