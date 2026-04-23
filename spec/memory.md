# Memory Architecture

## Short-Term Memory (Conversation History)
- Owned by FastAPI — not LangGraph
- Uses the same repository pattern as TASKS: `SQLiteHistoryRepository` in dev, `PostgresHistoryRepository` in production, selected via `JARVIS_DB_BACKEND` env var
- FastAPI loads the user's most recent conversation history up to `CONTEXT_WINDOW_BUDGET` tokens, dropping oldest exchanges first, and injects it into `JarvisState.messages`. FastAPI then appends `current_input` as the final entry. 16,000 tokens fits safely within all models' context windows while leaving headroom for system prompt, retrieved context, current input, and response. This value is a config key and straightforward to adjust.
- Each dict in `messages` has the shape `{"role": str, "content": str}` — this matches the Ollama chat API format exactly. The repository's `load` method is responsible for returning this stripped format; `HistoryEntry` retains all storage fields internally.
- At the end of every invocation, FastAPI writes the new exchange back to the repository
- Each user's conversation history is fully isolated by `user_id`
- Retention period configured per `RETENTION_DAYS` — enforced by the daily ofelia maintenance job
- **Message editing** — to edit a past message, the client deletes all history entries at or after the selected message and resends the replacement through the normal WebSocket flow. Discarded history is not recoverable. The repository exposes a `delete_from(user_id, entry_id)` method for this purpose.

## History Repository Interface

```python
def load(self, user_id: str) -> list[dict]:
    # Returns the user's recent history as [{"role": ..., "content": ...}, ...]
    # Bounded by CONTEXT_WINDOW_BUDGET tokens — oldest exchanges dropped first
    # Reads CONTEXT_WINDOW_BUDGET from config internally

def save(self, entry: HistoryEntry) -> None:
    # Appends a single exchange turn to the history for this user

def delete_from(self, user_id: str, entry_id: int) -> None:
    # Deletes all entries for this user with id >= entry_id
    # Used for message editing — truncates history at the edit point
```

## `HistoryEntry` Dataclass

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | string | Foreign key → users table |
| `role` | string | `user` \| `assistant` |
| `content` | string | Message text |
| `created_at` | datetime | Used for ordering and retention enforcement |

## Long-Term Memory (ChromaDB)

**Collection naming convention — used everywhere, no exceptions:**

| Collection | Contents |
|---|---|
| `memory_{user_id}` | Personal long-term memory for this user |
| `skills_{user_id}` | Personal skills for this user |
| `memory_shared` | Shared family memory |
| `skills_shared` | Shared family skills |

**Personal memory** — per user, fully private:
- ChromaDB collection: `memory_{user_id}`
- Source of truth: user's personal vault
- Embedding model: `nomic-embed-text` via Ollama

**Shared family memory** — readable by all users, written by JARVIS via classifier:
- ChromaDB collection: `memory_shared`
- Source of truth: shared family vault
- Contains: household info, shared calendar events, family notes, shared tasks
- Always queried alongside `memory_{user_id}` when `needs_memory=True` — results merged and deduplicated by chunk ID, top-k by score

## Memory Persistence — `memory/persist.py`

After the graph completes at RESPONDER and FastAPI has sent the `done` frame, FastAPI fires `memory/persist.py` as an asyncio background task. This fires after every exchange that completes with a `done` frame — it is unconditional with respect to `needs_memory` (every successful exchange is evaluated), but is never scheduled when the global exception handler sends an `error` frame instead. `needs_memory` controls retrieval only. The evaluator inside `memory/persist.py` decides whether anything in the exchange is worth writing to long-term memory; it may determine there is nothing to persist and exit cleanly. This means even exchanges that didn't require memory retrieval (e.g. a simple task mutation) are still evaluated — you never know what might be worth remembering.

`memory/persist.py` evaluates the completed exchange (`current_input` + `response`) and decides whether anything new is worth persisting — reads `response` not `formatted_response`, which avoids persisting client-specific formatting markup. If worth persisting, it:

1. Writes a raw dated markdown capture to `00-inbox/` under the appropriate personal or shared vault path, based on the personal → shared classifier. One file per memory unit — minimal formatting, just the captured fact or exchange and a timestamp.
2. Immediately ingests that file into ChromaDB via `memory/ingest.py` so it is queryable right away. The raw capture is usable immediately even before dream has run.

The vault is the source of truth — users can read, edit, or delete any vault file in Obsidian. ChromaDB is always derived from the vault.

It uses `tools/llm.py` for inference calls, `tools/vault.py` for the vault write, and `memory/chroma.py` for the ChromaDB write.

**Improvement log:** writes a `persist_decision` event for every exchange evaluated — both "persist" and "skip" verdicts. See `spec/improvement.md`.

If a `tools/llm.py` inference call fails, `memory/persist.py` retries that call once. The retry applies independently to each inference step — the evaluator and the classifier are each retried once if they fail; a failure in one does not abort the other. If the evaluator fails after one retry, the task exits and the exchange is not persisted. If the classifier fails after one retry, `memory/persist.py` defaults to writing to `memory_{user_id}` (personal) rather than dropping the memory — it is safer to persist to the wrong scope than to lose the memory entirely. All failures at this stage are logged at `ERROR` level with no admin notification per individual failure. Repeated failures will accumulate in the error log and trigger the daily maintenance job threshold notification if the count is high enough.

On ChromaDB unavailable: logs the failure and calls `notify_admin("chromadb_unavailable", ...)`.

**Future work:** Two planned additions to the memory system, to be designed and implemented in later phases:
- **Memory pruning** — a scheduled maintenance pass (added to `maintenance/cleanup.py`) that reviews long-term memory and removes stale or superseded entries. Some memories become irrelevant over time.
- **Dream mode** — a consolidation pass that runs on a schedule (e.g. nightly). Reads raw captures from `00-inbox/`, consolidates them into well-structured, human-readable markdown files in the appropriate vault folders (`01-knowledge/`, `04-conversations/`, etc.) with clear headings and sections — organised by topic, not a flat list of facts. Clears the inbox once consolidated. Then triggers a full re-ingest of the affected ChromaDB collections so the clean structured versions replace the raw captures. The result is a vault you can open in Obsidian and actually understand — a living picture of what JARVIS knows about you.

## Personal → Shared Classification

When JARVIS learns something new, `memory/persist.py` evaluates whether it belongs in personal or shared memory:

```
Personal → private thoughts, preferences, work, personal matters
Shared   → household info, shared plans, family events, shared resources
Ambiguous → personal (default to private, always)
```

The user can always override explicitly: "add this to the family brain" or "keep this private."

## `db/schema.py`

`db/schema.py` exposes a single `create_tables()` function. It opens connections to all three SQLite files and creates the appropriate tables in each:

- `auth.db` — `users`, `refresh_tokens`, `invites`
- `tasks.db` — `tasks`
- `history.db` — `history`

`create_tables()` is called from FastAPI's lifespan context manager on startup, conditional on `DB_BACKEND == "sqlite"`. It is never called at module import time. Using `CREATE TABLE IF NOT EXISTS` means it is safe to call on every startup — it will not alter or overwrite existing tables. When the schema changes during development, delete the relevant `.db` file and let startup recreate it: delete `~/.jarvis/auth.db` for auth tables, `~/.jarvis/tasks.db` for tasks, `~/.jarvis/history.db` for history. Startup will recreate the file and all tables in it. Proper migrations (Alembic) are introduced in Phase 6.

## Vault File Watcher

persist.py keeps ChromaDB in sync for writes JARVIS makes. But users may also edit or delete vault files directly in Obsidian — ChromaDB won't know about those changes until something triggers a re-ingest.

A background file watcher handles this. Using `watchfiles` (already a dependency via uvicorn), FastAPI starts a watcher on `{vault_base}` at startup that monitors for `.md` file changes. On change or deletion, it triggers a targeted re-ingest of the affected file into the appropriate ChromaDB collection. This runs as an asyncio background task — it does not block the server.

The watcher starts only when a vault path exists — graceful no-op on nomadbaker where no vault is present. It is a permanent feature of the system, running on pearlybaker and the home server alike.

## Vault Structure

Per-user vault (`{memory.vault_base}/{user_id}/` — on pearlybaker this resolves via the `~/jarvis-brain` symlink to `/mnt/hdd/jarvis/<username>/`):
```
<username>/
├── 00-inbox/          # Raw memory captures from persist.py — cleared by dream mode
├── 01-knowledge/      # Consolidated knowledge — structured by dream mode, human-readable
├── 02-skills/         # Procedural memory
│   ├── approved/      # Live skills the assistant can use
│   ├── pending/       # Candidate skills awaiting review
│   └── retired/       # Old skills kept for reference
├── 03-projects/       # One folder per project
├── 04-conversations/  # Notable exchanges — consolidated by dream mode
├── 05-people/         # Contact notes
├── 06-system/         # Assistant config, spec
└── 07-journal/        # Daily notes
```

**Note:** Tasks are not in the vault — they live in the tasks database. The vault holds unstructured knowledge and memory only.

Shared vault (`{memory.vault_base}/shared/` — on pearlybaker: `/mnt/hdd/jarvis/shared/`):
```
shared/
├── 00-inbox/          # Raw shared memory captures — cleared by dream mode
├── 01-knowledge/      # Consolidated family knowledge — structured by dream mode
├── 02-calendar/       # Shared events and schedules
├── 03-people/         # Shared contacts
└── 04-skills/         # Shared approved skills
    ├── approved/
    └── pending/
```

**Note:** Shared tasks are not in the vault — they live in the tasks database.

---

# Skills System

Skills are procedural memory — not facts but *how to do things*. Two scopes exist: personal (one user's preferences) and shared (consistent behaviour across all users).

| Type | Scope | Approval |
|---|---|---|
| Personal skill | One user only | That user approves |
| Shared skill | All users | Admin approves |

**Skill format:**
```markdown
# Skill: Debug Python Traceback
tags: [coding, python, debugging]
scope: personal                    # or: shared
version: 1.2
approved: true
approved_by: clarkehines
approved_date: 2026-04-09

## Trigger
When asked to debug a Python error or traceback.

## Process
1. Extract the exception type and message
2. Identify the deepest frame in user code (skip stdlib)
3. Check ChromaDB for similar past errors in this project
4. Hypothesise root cause before suggesting fix
5. Propose fix with explanation, not just code

## Notes
- Always ask to see surrounding context if traceback is partial
```

**Skills paths:**
- Personal skills: derived at runtime — `{memory.vault_base}/{user_id}/02-skills/approved/`
- Shared skills: explicit config key — `skills.shared_approved_path`

**Approval flow:**
```
Assistant proposes skill
        │
        ▼
  02-skills/pending/     ← user reviews (Obsidian or future web UI)
        │
   approved (shared: Admin only)
        │
        ▼
  02-skills/approved/    ← assistant can now use it
        │
        ▼
  ChromaDB ingestion     ← immediately queryable
```

ROUTER checks `skills_{user_id}` then `skills_shared` before every action. Personal skills take precedence over shared ones when there is a conflict. Both checks are graceful no-ops if the collection does not exist yet.
