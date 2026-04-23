# Testing Strategy

## Philosophy
Tests are written alongside implementation — never deferred. The goal is confidence that the system works correctly, not coverage for its own sake.

## Structure

```
tests/
├── conftest.py          # Shared fixtures — test_user, test_db, mock_ollama
├── unit/                # Fast, no services required — run on every commit
│   ├── test_router.py
│   ├── test_tasks_node.py
│   ├── test_responder.py
│   └── ...
└── integration/         # Real SQLite test DB, Ollama mocked — run manually
    ├── test_tasks_repository.py
    ├── test_history_repository.py
    └── ...
```

## Unit Tests (`tests/unit/`)
All external dependencies mocked. Tests verify that nodes read from state correctly, call repositories with the right arguments, handle `error` state properly, and produce correctly structured output. No services need to be running. Runs in seconds.

## Integration Tests (`tests/integration/`)
Real SQLite test database, wiped between runs. Ollama replaced with `MockOllamaClient` (returns hardcoded responses). Tests verify that the repository pattern works end to end — data goes in, comes back out correctly, `user_id` scoping holds, history is written and loaded correctly. Run manually when verifying a full layer.

## No End-to-End Tests (for now)
Testing against a live Ollama instance is slow and non-deterministic. Not worth the maintenance cost until the platform is mature. Can be added later.

## Shared Fixtures (`tests/conftest.py`)
- `test_user` — standard clarkehines admin user, pre-populated
- `test_db` — fresh SQLite database, wiped after each test
- `mock_ollama` — `MockOllamaClient` returning hardcoded responses

## Pre-Commit Hook
`pytest tests/unit/` runs automatically before every commit. Commits are blocked if unit tests fail. Integration tests are not in the pre-commit hook — they're slower and require more setup.
