# JARVIS — Project Specification
> Personal AI Assistant Platform — Fully Local, Server-Hosted, Multi-User
>
> *Last updated: 2026-04-13 (rev 26)*

---

## 🎯 North Star

A fully local, privacy-first AI assistant platform running on a dedicated home server. No cloud, no external APIs, no data leaving the home network. JARVIS serves multiple family members simultaneously — each with their own persistent memory, personalised assistant name, and tailored capabilities — all built on shared infrastructure: one Ollama instance, one Postgres database, one ChromaDB cluster, one FastAPI backend.

Every client talks to the same backend over Tailscale. The server is the product. The clients are just windows into it.

**JARVIS is the platform name.** The codebase, Docker stack, repo, config keys, and internal service names are all JARVIS. Each user's assistant name (JARVIS, FRIDAY, ARIA, etc.) is a per-user setting stored in Postgres and served via `GET /profile` — family members never see the platform name unless they want to.

**Core principle: Our AI. Our data. Our server.**

---

## 🏗️ Architecture Overview

```
          ┌──────────────────────────────┐
          │   Clients (6 apps — Phase 5) │
          │   all over Tailscale         │
          └──────────────┬───────────────┘
                         │  HTTPS / WebSocket (Tailscale)
                ┌────────▼──────────┐
                │     FastAPI       │  ← unified interface for all clients
                │   + JWT Auth      │
                └────────┬──────────┘
                         │
           ┌─────────────┼──────────────┐
           │             │              │
    ┌──────▼──────┐  ┌───▼────┐  ┌─────▼─────┐
    │  LangGraph  │  │Database│  │  ChromaDB  │
    │  (ROUTER →  │  │(tasks, │  │ (per-user  │
    │  PLANNER →  │  │ users, │  │  memory)   │
    │  ORCHESTR.) │  │history)│  │            │
    └──────┬──────┘  └────────┘  └───────────┘
           │
     ┌─────┴──────────────────┐
     │                        │
 ┌───▼────────┐        ┌──────▼──────┐
 │Ollama      │        │Ollama       │
 │(primary)   │        │(secondary)  │
 │reasoning + │        │lightweight  │
 │coding      │        │models       │
 └────────────┘        └─────────────┘
```

### Data Flow (per request)
1. Client sends message with JWT access token
2. FastAPI authenticates — validates token, checks `token_version` against database, identifies user, loads their profile and tier
3. FastAPI loads user's recent conversation history from repository
4. LangGraph invocation created — `JarvisState` populated with `user_id`, `tier`, `client_type`, `assistant_name`, `current_input`, and conversation history. FastAPI appends `current_input` as the final `{"role": "user", "content": current_input}` entry to `messages` so agent nodes always receive a complete, ready-to-use messages list. All node-populated fields are zero-initialised (`""`, `None`, `[]` as appropriate) — see JarvisState Fields.
5. ROUTER classifies intent — writes `intent` and `needs_memory` to state
6. PLANNER produces a `StepPlan` from `intent` — writes `step_plan` to state. Single-intent messages produce a one-step plan with negligible overhead.
7. `MEMORY_RETRIEVE` runs if `needs_memory: true` — retrieves relevant context from ChromaDB, writes to `retrieved_context`
8. ORCHESTRATOR begins executing the `StepPlan` — dispatches to the next ready agent node
9. Agent node executes — calls Ollama; FastAPI forwards tokens to client as `token` frames as they arrive
10. ORCHESTRATOR marks the step complete, clears `error` and `response`, dispatches the next ready step — loops until the `StepPlan` is exhausted
11. RESPONDER formats final response into `formatted_response`, sets `refresh` on state
12. Graph returns final state to FastAPI
13. FastAPI sends `done` frame with `refresh` array from state
14. FastAPI fires `memory/persist.py` as an asyncio background task after every exchange that completes with a `done` frame — not fired on `error` frame paths. Unconditional with respect to `needs_memory` (every successful exchange is evaluated), but never fired when the global exception handler handles the request instead of RESPONDER. Runs after `done` frame is sent, does not block the client.
15. FastAPI writes new exchange to conversation history repository

### Key Architecture Principles
- **LangGraph is stateless between requests.** It receives all context it needs at invocation start and returns output. It does not own persistence.
- **FastAPI owns persistence.** Conversation history lives in Postgres. FastAPI loads it before each invocation and writes it back after.
- **FastAPI owns the WebSocket.** FastAPI sends all frames (`token`, `done`, `error`, `status`). LangGraph nodes never touch the WebSocket — they only transform state.
- **FastAPI owns state initialisation.** FastAPI constructs the full `JarvisState` before every invocation, including appending `current_input` to `messages`. Nodes never manipulate the messages list directly.
- **The graph ends at RESPONDER.** MEMORY_PERSIST is a FastAPI background task, not a graph node. The graph's job is done the moment RESPONDER writes `formatted_response` to state.
- **All clients are equal.** All clients connect to FastAPI over Tailscale. No client has a privileged path to LangGraph.
- **All secrets via environment variables.** Nothing sensitive ever touches `config.yaml` or git. See Secrets section.
- **Errors are handled at the node level.** Nodes catch expected failures and write to `JarvisState.error` — RESPONDER formats clean messages for the client. Unexpected exceptions bubble to FastAPI's global handler.
- **Any node setting `error` routes immediately to RESPONDER.** All downstream nodes are skipped. This is a universal graph rule — no node after a failing node ever runs. RESPONDER formats the error with tier-appropriate detail: Admin gets full technical detail (component, error class, what failed and where), Power gets operational detail (what couldn't be completed, plain reason), Standard gets plain English specific to what the user asked for (no technical terms, but not vague — e.g. "I couldn't retrieve your memories for this request" not "something went wrong"). Regardless of tier, the error is always logged at `ERROR` level so full detail is available on the server.
- **One message at a time per connection.** FastAPI processes one invocation per user at a time. Messages received during an active invocation are dropped — the server sends a `status` frame and the client should indicate the busy state visually. No queuing.
- **Abstract repository methods use `...` as the body, not `pass`.** `...` (Ellipsis) signals "intentionally unimplemented — implementation lives elsewhere." `pass` means "do nothing," which is misleading for an interface method. This applies to all `repository.py` files across `db/auth/`, `db/tasks/`, and `db/history/`.
- **Never call `get_auth_repository()`, `get_task_repository()`, or `get_history_repository()` inside a function body.** Repository instantiation always happens at module level or via FastAPI's `Depends()` injection. Constructing a repository inside a function body bypasses dependency injection and makes the code untestable.
- **Prefer dependency injection over manual checks.** Any check performed on more than one endpoint — authentication, tier gating, repository access — must be implemented as a FastAPI dependency in `dependencies.py` and applied via `Depends()`. Never duplicate the same check logic inside multiple function bodies.

---

## 👥 Users & Tenancy

JARVIS is a multi-user platform. All data is scoped by `user_id`. Infrastructure is shared. Privacy between users is enforced at the data layer — no user can ever access another's data.

### User Tiers

| Tier | Who | Capabilities |
|---|---|---|
| **Admin** | clarkehines | Full access — all nodes, coding team, system shell, skill management, user admin |
| **Power** | brother | Full access — all nodes, coding team, system shell, skill management |
| **Standard** | rest of family | Chat, tasks, memory, web search — no coding team, no shell |

Tiers are a safety boundary, not a feature paywall. Standard tier exists to protect family members who aren't developers from accidentally running shell commands, executing code, or doing anything that could cause damage they don't understand. Admin and Power tier users have opted into that responsibility. The distinction is about protecting people from footguns, not gatekeeping capability.

Tier is stored in the user's Postgres profile and checked by FastAPI on every request. Adjusting a user's capabilities requires only a database update — no code changes.

### Assistant Names

Each user configures their own assistant name. Stored per-user in Postgres and served via `GET /profile`. The client fetches it on login and caches it locally.

Name changes go through `PATCH /profile` — no token invalidation, no forced re-login. The server pushes a `profile` WebSocket frame to all of that user's active connections; each client re-fetches `GET /profile` and updates its local cache.

Tier changes are admin-only and go through a Phase 4 admin endpoint (`PATCH /admin/users/{username}`). The server pushes the same `profile` WebSocket frame to the affected user's active connections — the client responds identically: re-fetches `GET /profile` and updates its local cache. Live within seconds across all devices. No `token_version` increment required.

```yaml
# Example assistant names — stored in Postgres, not config.yaml
clarkehines:  JARVIS
brother:      FRIDAY
mum:          ARIA
```

---

## 🔐 Auth

JARVIS uses a two-token JWT auth pattern. The goal is that family members never see a login prompt during normal use.

### Tokens

| Token | Lifespan | Purpose |
|---|---|---|
| Access token | 24 hours | Sent with every API request — FastAPI validates this |
| Refresh token | 90 days | Stored securely on client — used silently to obtain a new access token |

When the access token expires, the client uses the refresh token to get a new one automatically. The user only sees a login prompt if they have been completely inactive for 90 days, if they explicitly log out, or if an admin has force-revoked their session.

Refresh tokens are stored server-side in a `refresh_tokens` table. The server stores a hash of the token, not the raw value. On logout or forced deauth, the row is marked `revoked = true` — making silent refresh impossible and requiring full re-authentication. This means forced logout actually means forced logout, with no window where a revoked user can keep refreshing.

The server's responsibility on logout is to mark the refresh token `revoked = true`. Client-side credential cleanup is each client's own responsibility — token storage and cleanup behaviour per client is covered in Phase 5.

### WebSocket and Token Invalidation

WebSocket connections are validated at connection time. `token_version` is checked on every new message received over the connection — if the stored version has been incremented since the connection was opened (e.g. an admin forced a full deauth), the connection is closed with a clean `error` frame on the next message. The queue is cleared on mismatch — any pending messages are dropped and not processed. The `error` frame indicates that re-authentication was required; the user re-authenticates via the normal silent refresh flow and re-sends manually. In practice this scenario is rare since the client disables input during active invocations, meaning the queue will typically have at most one message in it.

The server maintains a connection registry — a dict mapping `user_id` to a list of `ConnectedClient` objects for that user. Each `ConnectedClient` holds the WebSocket object and the `client_type` extracted from the JWT at connection time. This is used to push `profile` frames on assistant name or tier changes, and will be used by the admin dashboard to show active sessions (e.g. "brother — tui × 2").

### Token Contents (JWT payload)
```json
{
  "user_id": "clarkehines",
  "client_type": "tui",
  "token_version": 4,
  "exp": 1234567890
}
```

`client_type` is included so the RESPONDER node always knows what it is talking to without an extra lookup. Valid values: `tui | web | mobile`.

`token_version` is validated against the database on every request. If the stored version is higher than the token's version, the token is rejected and the client must refresh. This allows immediate forced invalidation without waiting for token expiry.

### `GET /profile`

Returns the current user's profile data. Called by the client on login and whenever a profile update is received over WebSocket. The JWT provides identity — `/profile` provides everything the client needs to display and personalise the UI.

```json
{
  "username": "clarkehines",
  "tier": "admin",
  "assistant_name": "JARVIS"
}
```

Future personality settings (response style, verbosity, language preferences, etc.) are added to this response as they are introduced — never to the JWT.

### Token Version & Forced Invalidation

Every user has a `token_version: int` column in the database. The current version is embedded in every issued token. On every request FastAPI checks the token's version against the stored value — if they don't match, the token is rejected.

Incrementing `token_version` immediately invalidates all active tokens for that user across all devices. This is a nuclear option reserved for:
- **Admin-forced deauth** — intentional removal or security incident. Three steps, in order: (1) increment `token_version` in the database — all subsequent HTTP requests with the old access token are rejected immediately; (2) set `disabled = true` — login and refresh are now rejected for this account regardless of credentials, preventing a bad actor with compromised credentials from logging back in; (3) server iterates the connection registry and calls `websocket.close()` on every active WebSocket connection for that user — no frame is sent first, the socket is closed immediately. The client receives a disconnect event and must return the user to the login screen. There is no grace period and no warning. Admin then generates a password reset token for the legitimate user to regain access.

Everything else propagates seamlessly with no re-login:
- **Assistant name changes** — database updates instantly, server pushes to all active WebSocket connections. Token untouched.
- **Tier changes** — server pushes a `profile` frame to all of the user's active connections. Each client calls `GET /profile` and updates its local cache. Live within seconds across all devices.
- **Normal logout** — revokes the current device's refresh token only. Other devices stay active. Token version untouched.

### `users` Table

| Field | Type | Notes |
|---|---|---|
| `username` | string | Primary key — used as `user_id` throughout the system |
| `password_hash` | string | bcrypt hash — never store the raw password |
| `tier` | string | `admin` \| `power` \| `standard` |
| `assistant_name` | string | Per-user display name — served via `GET /profile` |
| `token_version` | integer | Starts at 0, increment to invalidate all active tokens |
| `disabled` | boolean | Default false — set to `true` on forced deauth. Login and refresh are rejected for disabled accounts regardless of credentials |

### `refresh_tokens` Table

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | string | Foreign key → users table |
| `token_hash` | string | SHA-256 hash of the raw token — never store the raw value |
| `expires_at` | datetime | 90 days from issuance |
| `revoked` | boolean | Set to `true` on logout or forced deauth — never delete rows |

On `/auth/refresh`: server looks up the presented token's hash, checks it exists, is not revoked, and has not expired. If any check fails, 401 — login required. On logout or forced deauth: row is marked `revoked = true`. The client cannot silently recover from a revoked refresh token.

### `invites` Table

The `invites` table serves two purposes: onboarding new users and issuing password reset tokens to existing users. Both are one-time tokens generated by the Admin and shared out-of-band. The Admin never knows anyone's password.

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `token_hash` | string | SHA-256 hash of the raw token |
| `type` | string | `invite` \| `password_reset` |
| `username` | string | For `invite`: username pre-assigned by Admin. For `password_reset`: the existing account to unlock |
| `tier` | string | Tier pre-assigned by Admin — `invite` only, null for `password_reset` |
| `assistant_name` | string | Default assistant name pre-assigned by Admin — `invite` only, null for `password_reset`. User can change later |
| `expires_at` | datetime | 48 hours from issuance |
| `used` | boolean | Set to `true` when consumed — cannot be reused |

**Invite flow:**
1. Admin calls `POST /auth/invite` with `username`, `tier`, `assistant_name` — server creates the invite row and returns the raw token
2. Admin shares the token with the new family member (text, WhatsApp, etc.). Future: a client generates a registration link with the token baked in — family member clicks it and lands directly on the registration page.
3. Family member calls `POST /auth/register` with the token and their chosen password — server validates the token, creates the user record, marks the invite `used = true`
4. Account is active — family member can log in immediately

**Password reset flow:**
1. Admin calls `POST /auth/invite` with `type: password_reset` and `username` — server creates the reset row and returns the raw token
2. Admin shares the token with the legitimate user out-of-band
3. User calls `POST /auth/reset` with the token and their new password — server validates the token, rejects the new password if it matches the current `password_hash` (cannot reuse the compromised password), updates `password_hash`, sets `disabled = false`, marks the token `used = true`
4. Account is re-enabled — user can log in immediately with the new password

### Auth Endpoints

- `POST /auth/login` — Open. Request body: `{"username": "...", "password": "..."}`. On success: returns `{"access_token": "eyJ...", "refresh_token": "eyJ...", "access_expires_at": "..."}` and inserts a row into `refresh_tokens`. On failure: 401. Failed login attempts are tracked per IP in an in-memory dict in `api/auth.py` — a simple mapping of IP address to a list of attempt timestamps. 5 failures within 10 minutes triggers an admin notification via ntfy. This state resets on server restart, which is acceptable — the brute-force window simply clears.
- `POST /auth/refresh` — Open (valid refresh token required). See `/auth/refresh` contract below.
- `POST /auth/logout` — Authenticated. Marks the current device's refresh token row `revoked = true`. Does not increment `token_version` — other devices stay active.
- `POST /auth/invite` — Admin only. Accepts `type` (`invite` | `password_reset`), `username`, and for `invite` also `tier` and `assistant_name`. Returns a one-time token valid for 48 hours.
- `POST /auth/register` — Open (invite token required). Consumes the invite, creates the user. Notifies admin via ntfy on success — admin should know when a new user joins the system.
- `POST /auth/reset` — Open (password reset token required). Validates the token, rejects the new password if it matches the current `password_hash`, updates the password, sets `disabled = false`, marks the token used.
- `POST /auth/password` — Authenticated. Self-service password change. Requires current password for verification before accepting the new one.
- `GET /profile` — Authenticated. Returns `username`, `tier`, `assistant_name`. Called by client on login and on receipt of a `profile` WebSocket push.
- `PATCH /profile` — Authenticated. Updates `assistant_name`. Returns updated `ProfileResponse`. Server pushes a `profile` frame to all of the user's active connections after the update.

### Daily Maintenance Job (ofelia)

A daily ofelia job runs a general-purpose maintenance pass. It is intentionally designed to accumulate tasks over time — new maintenance needs get added here rather than spinning up separate scheduled jobs.

**Current tasks:**
- Purge `refresh_tokens` rows where `expires_at < now` (regardless of `revoked` status)
- Purge `invites` rows where `expires_at < now`
- Purge conversation `history` entries older than `retention_days` per user
- Count `ERROR`-level log entries in the current log file from the last 24 hours — if over `log_error_threshold`, notify admin via ntfy

**`/auth/refresh` contract (Phase 3):** The client sends a JSON body with the raw refresh token and its client type:
```json
{"refresh_token": "eyJ...", "client_type": "tui"}
```
`client_type` is sent by the client rather than stored in `refresh_tokens` — the client always knows its own type and this keeps the table simple.
The server validates it (exists, not revoked, not expired), reads the current `token_version` from the `users` table, and issues a new access token.
```json
{
  "access_token": "eyJ...",
  "access_expires_at": "2026-04-11T14:00:00Z"
}
```

On a successful Phase 3 refresh, the client updates only `access_token` and `access_expires_at` in `auth.json` — `refresh_token` is left untouched. The file is not rewritten in full.

Phase 3 does **not** rotate the refresh token — the same refresh token remains valid until it expires or is revoked. Phase 4 adds refresh token rotation: on every `/auth/refresh` call, the old refresh token row is marked `revoked = true`, a new row is inserted, and the response includes a new `refresh_token` alongside the new access token. `auth.json` is updated with both.

### `seed_db.py` Contract

`scripts/seed_db.py` creates the initial `clarkehines` admin account on first-run setup. It is the only account created this way — all subsequent users go through the invite flow.

- **Idempotent** — safe to re-run. If a `clarkehines` record already exists, the script skips creation and prints a message. It never resets an existing password.
- **Interactive password prompt** — `Enter password for clarkehines:` — password never touches disk, a file, or an environment variable
- **Initial state** — creates the record with `tier = "admin"`, `assistant_name = "JARVIS"`, `token_version = 0`
- **Confirmation output** — prints `Created user clarkehines` on success, `User clarkehines already exists, skipping` if already present
- **Requires `JARVIS_SECRET_KEY`** — `seed_db.py` imports `config.py`, which reads `JARVIS_SECRET_KEY` at module import time and hard-fails if it is not set. Export it in your shell (or load your `.env`) before running this script, even though the script itself does not use JWT signing.

### `config.yaml` and `config.py`

`config.yaml` at the project root is the single source of truth for all non-sensitive configuration. `config.py` is the only module that reads it — everything else imports constants from `config.py`. The files themselves are the authoritative reference — read them directly rather than duplicating their contents here.

**Config sections and what they control:**
- `models` — model names for each role (router, general, reasoning, embedding, fallback, multimodal). All model assignments go here — never hardcoded in the codebase. Values differ per machine; see the file for current dev values and comments showing full-system targets.
- `ollama` — base URL and timeout. `base_url` is the key that changes between dev and Docker deployment.
- `server` — host and port. Host differs between dev (`127.0.0.1`) and production (`0.0.0.0`).
- `auth` — token expiry (`access_token_expire_hours`, `refresh_token_expire_days`) and brute force config (`brute_force_limit`, `brute_force_window_minutes`).
- `db` — `path` is dev-only (SQLite files written here). Ignored when `JARVIS_DB_BACKEND=postgres`. All repository factories read `JARVIS_DB_BACKEND` from the environment, defaulting to `sqlite`.
- `history` — `context_window_budget` in tokens. Oldest exchanges dropped first when loading history.
- `maintenance` — `retention_days` (history TTL) and `log_error_threshold` (ERROR count before admin notified).
- `logging` — log file path. Dev default is `~/.jarvis/jarvis.log`.
- `memory` — `vault_base` (differs per machine), `chunk_size`, `chunk_overlap`.
- `skills` — `shared_approved_path` (differs per machine).
- `system` — `allowed_paths` list for SYSTEM node sandboxing. Machine-specific.
- `coding_team` — `max_review_iterations` caps the Reviewer → Coder loop.
- `status_messages` — node-entry status frame text. Empty string = no frame sent. Only governs node-entry frames — mid-node `status_message` updates are dynamic and written by nodes directly.

**`config.py` rules:**
- `JARVIS_SECRET_KEY` is read at module import time — hard-fails immediately with `KeyError` if unset. No silent fallback.
- `get_postgres_url()` reads `JARVIS_DB_URL` at call time, not import time. Only called by Postgres repository factories.
- `ALGORITHM = "HS256"` is hardcoded — not a config key. Changing it would immediately invalidate all active tokens.

---

### Secrets Rule

**No secrets ever touch `config.yaml` or git.** The JWT secret key and any sensitive values are read exclusively from environment variables via `config.py`. On the server these are set in a `.env` file loaded by Docker Compose. `.env` is in `.gitignore`. In dev, export them in the shell or use a local `.env`. `config.yaml` holds only non-sensitive config: paths, model names, feature flags, timeouts.

---

## 📋 Logging

JARVIS uses Python's standard `logging` module throughout. All modules log to a shared rotating file handler — never to stdout in production.

### Log Handler

`RotatingFileHandler` — configured once at application startup in `main.py`:
- Max file size: 10 MB
- Files retained: 5 (50 MB cap total)
- Log path: configured via `logging.path` in `config.yaml` — defaults to `~/.jarvis/jarvis.log` in dev, overridden for Docker deployment
- Log level: `INFO` by default — `ERROR` entries are what the maintenance job counts

### Log Threshold Notification

The daily maintenance job counts `ERROR`-level log entries written in the last 24 hours. If the count exceeds `maintenance.log_error_threshold`, admin is notified via ntfy. This catches silent degradation — a single background task failure is noise, eighty failures in a day is a real signal that something is wrong.

`log_error_threshold` is a config key (default: 50). The maintenance job reads the current log file only — rotated files are not counted.

### What Gets Logged

- `ERROR` — any unexpected failure, caught exception, background task failure after retry, node error written to state
- `WARNING` — degraded behaviour that resolved (e.g. primary model fallback, ROUTER retry that succeeded)
- `INFO` — normal operation milestones (startup, shutdown, invocation start/end)

Admin notifications via ntfy are reserved for acute failures requiring immediate attention. The log is the full record — the notification is just a prompt to go look at it.

---

## 🚨 Error Handling

### Node-Level Errors (Expected Failures)

Nodes catch expected failures — Ollama timeout, ChromaDB unavailable, repository error — and write a structured error onto state rather than raising. The graph continues to RESPONDER, which formats a clean message for the client.

`JarvisState` carries an `error` field for this purpose:

```python
error: str | None   # set by any node on expected failure, checked by RESPONDER
```

RESPONDER checks `error` before formatting — if set, it returns the error message to the client instead of a normal response.

### Unexpected Exceptions

Anything not caught at the node level bubbles up to FastAPI's global exception handler. The handler returns a clean error response to the client — no raw tracebacks, no 500 with stack dumps.

### Ollama Failure Scenarios

Two distinct failure scenarios are handled differently:

**Scenario A — Primary model fails or times out.** For example `llama3.1:8b` errors mid-request or exceeds the timeout in the agent node. This failure happens in the agent node's inference call — not in ROUTER, which has already completed using `mistral:7b`. The node writes a message to `status_message` on state (e.g. `"Primary model unavailable, retrying with fallback..."`) — FastAPI picks this up via `astream_events` and forwards it as a `status` frame in the normal way. The node then starts a fresh inference call using the fallback model (`mistral:7b`). Any partial `token` frames already sent to the client are discarded — the client clears the partial response on receiving the `status` frame and waits for the new stream. The user is told the full assistant is temporarily unavailable but basic responses are still working.

**Scenario B — Ollama process is unreachable.** No model fallback is possible — all models are served by Ollama. JARVIS returns a clean "service temporarily unavailable" message to the user and immediately notifies the admin via ntfy. No inference attempt is made. Note that if Ollama is unreachable, ROUTER itself fails before any agent node runs — the global exception handler catches this and sends the `error` frame directly, bypassing the node-level error pattern entirely. This is the explicit exception to that pattern.

### Admin Notifications — `notifications/notify.py`

A single `notifications/notify.py` module wraps ntfy. Everything that needs to alert the admin calls `notify_admin(error_class, message)` — one place to update if ntfy ever moves.

**Notify admin on:**
- Ollama process unreachable (Scenario B above)
- ChromaDB unavailable
- FastAPI crash / restart
- 5 or more failed login attempts from the same IP within 10 minutes (possible brute force or user locked out)
- Repository errors that affect a user's data

**Log only (no notification):**
- Single request timeouts that resolved on retry
- Primary model fallback to fallback model (Scenario A above)
- ROUTER parse failures that fell back gracefully
- Tier gate hits (user tried a capability they don't have)

**Cooldown:** The `(error_class, message)` tuple is the cooldown key — at most one notification per unique `(class, message)` pair per 10 minutes. Using `error_class` alone would suppress distinct errors that share a class (e.g., two unrelated `ValueError`s). Using the full message text gives the right granularity without the false-suppression risk, since unhandled exceptions at this volume are rare. Cooldown state is tracked in memory — not persisted. This prevents phone-blowing-up scenarios when a service goes down and every request fails.

**Future work:** A `notify_user(user_id, message, type)` function will be added when user-facing async notifications are needed (e.g., background task completion, deadline reminders). User notifications will use a separate channel — likely WebSocket push to the active client, with ntfy as a fallback for offline delivery. `notify_admin` is not extended for this — they are distinct concerns.

---

## 📡 WebSocket Streaming Contract

All real-time communication between FastAPI and clients uses a persistent WebSocket connection with typed JSON frames.

### Connection Model

One WebSocket connection per authenticated session. The client opens it on login and keeps it alive for the duration of the session. Starlette's native ping/pong heartbeat detects silent disconnects automatically — no manual heartbeat implementation required. If the connection drops, clients reconnect automatically.

**One message at a time:** FastAPI processes one invocation per user at a time. If a message arrives during an active invocation, the server sends a `status` frame — `"I'm still working on your last message."` — and drops it. No queuing. The client should visually indicate the busy state so the user knows not to send. This keeps the server simple and the interaction model unambiguous for all clients.

**Future work — TUI interrupt channel:** A `/btw` style mechanism for power TUI users may be added in a later phase, allowing a secondary message to be injected mid-invocation. This is opt-in, TUI-only, and not part of the core contract. All other clients remain strictly one-message-at-a-time with no queuing.

**During interrupt/confirm:** When a `confirm_request` frame is sent, the client must disable the message input field until the confirmation is resolved. The server rejects any non-`confirm`/`cancel` message received while an interrupt is active, responding with a `status` frame: `"Please confirm or cancel the pending action first."` This is enforced at both layers — client disables input as the primary UX, server rejects as a safety net. The confirmation gate is a modal moment by design: consequential actions require explicit user intent before proceeding.

**Reconnect during interrupt:** If the WebSocket drops while a graph is paused at an interrupt, FastAPI discards the paused graph on reconnect. On reconnect, FastAPI sends a `status` frame informing the user that their pending confirmation was cancelled and they should re-request the action if they still want it. No attempt is made to replay the `confirm_request` — the user's session context is gone and the action must be re-initiated from scratch.

### Ownership of Streaming

**FastAPI owns the WebSocket connection and is solely responsible for sending frames.** During a request, FastAPI calls LangGraph via `astream_events` and streams tokens from Ollama to the client as `token` frames as they arrive. When the graph completes at RESPONDER, FastAPI reads `formatted_response` and `refresh` from the final state and sends the `done` frame. LangGraph nodes never touch the WebSocket directly — RESPONDER only transforms state.

### Status Frames — How They Are Sent

FastAPI uses LangGraph's `astream_events` API instead of `ainvoke`. This yields a stream of events as the graph executes — including node entry and exit events — allowing FastAPI to send `status` frames at the right moments without any node touching the WebSocket.

**Two tiers of status frames:**

**Node-entry status** — driven by the `status_messages` block in `config.yaml`, exposed as `STATUS_MESSAGES` in `config.py`. FastAPI reads this dict on startup — if the value for a node is a non-empty string, a `status` frame is sent when that node starts. If the value is empty, the node runs silently. This means status messages are a product decision, not a code decision — change the config, no code changes needed.

| Node | Default message |
|---|---|
| ROUTER | `"Thinking..."` |
| MEMORY_RETRIEVE | `"Searching memory..."` |
| WEB | `"Searching the web..."` |
| TASKS | *(silent by default)* |
| CONVERSATION | *(silent by default)* |
| MEMORY | *(silent by default)* |
| SYSTEM | *(silent by default)* |
| CODE | *(silent by default)* |
| RESPONDER | *(silent by default)* |

**Mid-node status** — nodes write a specific message to `status_message: str | None` on `JarvisState` during execution. FastAPI picks this up via `astream_events` and fires a `status` frame with that message. This allows granular, accurate updates throughout a node's execution:

- SYSTEM reports the specific command it is about to run before executing it
- CODE reports its current reasoning stage as it works through a problem
- WEB reports the specific query it is searching
- Coding Team subgraph nodes each report their stage (Architect planning, Coder implementing, Reviewer checking, Tester running)

Nodes that don't need granular status simply never write to `status_message`.

### Frame Format

Every frame is a JSON object with a `type` field. The client pattern-matches on `type` and handles accordingly.

```json
{"type": "token",           "message_id": "abc123", "content": "You have "}
{"type": "token",           "message_id": "abc123", "content": "three tasks..."}
{"type": "done",            "message_id": "abc123", "refresh": ["tasks"]}
{"type": "error",           "message_id": "abc123", "message": "Service temporarily unavailable"}
{"type": "status",          "message_id": "abc123", "message": "Searching the web..."}
{"type": "confirm_request", "message_id": "abc123", "payload": {"type": "command", "value": "rm -rf /tmp/jarvis-scratch"}}
{"type": "confirm",         "message_id": "abc123"}
{"type": "cancel",          "message_id": "abc123"}
{"type": "profile",         "message_id": "__push__"}
```

**Frame types:**

| Type | Direction | Purpose |
|---|---|---|
| `token` | server → client | Single streaming token — client appends to display. Produces the typewriter effect. |
| `done` | server → client | Stream complete — carries `refresh` array |
| `error` | server → client | Something went wrong — display message to user |
| `status` | server → client | In-progress indicator — node-entry, mid-node update, busy rejection, or interrupt rejection |
| `confirm_request` | server → client | Node is paused awaiting confirmation — carries `payload` describing what requires approval. Client must disable input on receipt. |
| `confirm` | client → server | User approved the pending action — graph resumes. `message_id` correlates to the `confirm_request` that triggered it. |
| `cancel` | client → server | User cancelled the pending action — graph aborts the command cleanly. `message_id` correlates to the `confirm_request` that triggered it. On cancel, control returns to the user — if they want to redirect or explain, their next message handles it naturally. |
| `profile` | server → client | Profile data has changed — client should call `GET /profile` and update its local cache. Sent to all active connections for the user on any `assistant_name` or `tier` change. |

### message_id

Every frame carries a `message_id` generated by the client at request time (short random string — no need for UUID). This allows the client to match response frames to the request that triggered them, and to distinguish them from server-push frames.

**Client → server envelope:**
```json
{"message_id": "abc123", "content": "what's on my task list"}
```

### Server Push

Frames with no `message_id` (or with the reserved value `"__push__"`) are unsolicited server events — a background task completing, a shared task being updated by another family member, etc. Clients should handle these without expecting them to correlate to a pending request.

### Interrupt / Confirm Pattern

Any node can pause graph execution and request confirmation from the user before proceeding. This is a general-purpose mechanism — SYSTEM uses it before executing shell commands, and Coding Team nodes use it before executing plans or running destructive tests.

**How it works:**
1. Node writes `interrupt_payload` to state describing what needs approval, then calls LangGraph's `interrupt()`
2. FastAPI detects the interrupt event via `astream_events` and sends a `confirm_request` frame to the client
3. Graph execution pauses — FastAPI holds the WebSocket open and waits
4. Client disables the message input field and renders the confirmation prompt to the user
5. User responds — client sends a `confirm` or `cancel` frame back to FastAPI
6. Client re-enables the message input field
7. FastAPI calls `graph.resume()` with the user's decision
8. If confirmed, the node proceeds with execution. If cancelled, the node writes a hardcoded cancellation message to `response` — no Ollama call is made for the cancellation. The message includes the cancelled command or action from `interrupt_payload` and hands control back to the user (e.g. "Cancelled: `rm -rf /tmp/jarvis-scratch`. What would you like to do instead?"). The graph then continues to RESPONDER normally.

The same hardcoded cancellation rule applies to Coding Team nodes — on cancel, the node writes a hardcoded message describing what was cancelled, derived from `interrupt_payload`, with no inference call.

**`confirm_request` payload shapes:**
```json
{"type": "command", "value": "rm -rf /tmp/jarvis-scratch"}
{"type": "plan",    "value": "Architect proposes: create auth module, restructure graph.py, add three new nodes"}
{"type": "execute", "value": "Tester about to run full test suite against live database"}
```

The client renders the prompt appropriately based on `payload.type`. The `message_id` on the `confirm_request` frame matches the original request so the client can correlate them.

**`interrupt_payload` on `JarvisState`:** Nodes write to this field before calling `interrupt()`. FastAPI reads it to build the `confirm_request` frame. Zero-initialised to `None` by FastAPI before invocation.

### The `refresh` Array

The `done` frame carries a `refresh` array signalling which data panels the client should re-fetch after the exchange completes. RESPONDER is the sole owner of the `refresh` field — it derives the value from `intent` and writes it to state. No other node writes to `refresh`.

```json
{"type": "done", "message_id": "abc123", "refresh": ["tasks"]}
{"type": "done", "message_id": "abc123", "refresh": []}
```

Valid refresh targets: `tasks`, `memory`. Empty array means no client state has changed. The client fires a `GET` request to the appropriate REST endpoint for each entry in `refresh` and re-renders the relevant panel.

### Token Streaming

Ollama is called in streaming mode (`stream: true`). FastAPI forwards tokens to the client as `token` frames as they arrive — the user sees the response build word by word. The `done` frame is sent once the Ollama stream is exhausted and the graph has completed at RESPONDER.

`status` frames are sent during the pre-token gap while ROUTER, `MEMORY_RETRIEVE`, and skills checks run — so the user sees "Thinking..." or "Searching memory..." rather than silence before the first token arrives.

---

## 🧠 Model Stack

Target hardware: **RTX 4070 Ti Super — 16 GB VRAM** (home server, from summer 2026).
Dev hardware: nomadbaker (Intel Arc 140V, no CUDA) and pearlybaker (RTX 3080, 10 GB VRAM).

| Model | Role | VRAM | Context Window | Notes |
|---|---|---|---|---|
| `mistral:7b` | Router / Classifier | ~5 GB | 32K | Always loaded |
| `llama3.1:8b` | General brain | ~5 GB | 128K | Default for all users |
| `deepseek-r1:14b` | Reasoning / Coding | ~9 GB | 128K | On-demand, displaces general |
| `llava:13b` | Multimodal (future) | ~8 GB | ~4K | On-demand, image understanding |
| `nomic-embed-text` | Embeddings | minimal | n/a | Always available |

**Concurrency:** Ollama queues simultaneous requests natively. The router stays loaded at all times. General and reasoning models hot-swap on demand. As GPU upgrades happen, the model stack upgrades with zero architectural changes — pull new models, update `config.yaml`.

**Dev stand-ins:**
- nomadbaker: `qwen2.5:3b` for all inference roles (no CUDA)
- pearlybaker: `qwen2.5:14b` (general), `deepseek-coder-v2:16b` (coding)

---

## 🎯 Model Usage — Which Model for Which Task

Model names are never hardcoded. All assignments are read from `config.yaml` via `config.py` at runtime. This section is the canonical reference for which model does what.

| Task | Home Server Model | pearlybaker Stand-in | nomadbaker Stand-in |
|---|---|---|---|
| Intent routing / classification | `mistral:7b` | `mistral:7b` | `qwen2.5:3b` |
| General conversation | `llama3.1:8b` | `qwen2.5:14b` | `qwen2.5:3b` |
| Reasoning / coding (CODE node) | `deepseek-r1:14b` | `deepseek-coder-v2:16b` | `qwen2.5:3b` |
| Embeddings (memory ingest + retrieval) | `nomic-embed-text` | `nomic-embed-text` | `nomic-embed-text` |
| Multimodal / image understanding | `llava:13b` | — | — |
| Fallback (primary model failure) | `mistral:7b` | `mistral:7b` | `qwen2.5:3b` |

**Rules:**
- ROUTER always uses the router model — never the general model
- CODE node always uses the reasoning model — never the general model
- Embeddings always use `nomic-embed-text` on all machines — no stand-in
- On nomadbaker, `qwen2.5:3b` fills all roles — expect degraded output quality, this is normal for a dev stand-in
- Model assignments upgrade via `config.yaml` only — no code changes needed as hardware improves

---

## 🤖 Agent Nodes (LangGraph)

Every node receives a `JarvisState` that includes `user_id`, `tier`, `client_type`, `assistant_name`, and conversation history loaded from the repository. All data operations are scoped to the requesting user via repository interfaces. Nodes never touch raw storage directly and never touch another user's data.

### Tier-Aware Status Messages

All `status_message` writes — both node-entry frames and mid-node updates — are tier-aware. Nodes read `tier` from state and write the appropriate level of detail. FastAPI fires whatever `status_message` it sees without translation — the node owns the content.

| Tier | Status detail level | Style |
|---|---|---|
| **Admin** | Full technical detail | Node names, model names, collection names, repository class names, file paths, tool names — everything |
| **Power** | Operational detail | What is happening without the internal plumbing — e.g. "Searching your memory..." not "Querying `memory_clarkehines` in ChromaDB..." |
| **Standard** | Task-relevant only | Plain language, no technical terms — e.g. "Adding task...", "Searching the web...", "One moment..." |

This applies to every node that writes `status_message`. Examples per tier for a memory retrieval:
- Admin: `"Querying memory_clarkehines and memory_shared in ChromaDB..."`
- Power: `"Searching your memory..."`
- Standard: `"One moment..."`

### Supporting TypedDicts

```python
class Step(TypedDict):
    id: str            # short unique identifier within this plan (e.g. "delete_ring", "add_shampoo")
    intent: str        # the node to dispatch to — "tasks" | "memory" | "code" | "web" | "system" | "conversation"
    description: str   # plain-language description of this step, used in tier-aware status messages
    depends_on: list[str]  # IDs of steps that must succeed before this one runs. Empty list = no dependencies.


class StepResult(TypedDict):
    step_id: str               # matches the Step.id this result belongs to
    status: str                # "success" | "failure" | "blocked"
    response: str              # the agent node's response for this step
    blocked_by: str | None     # step_id of the failed step that caused this block. None if not blocked.
    reason: str | None         # failure or block reason. None on success.
```

### JarvisState Fields

```python
class JarvisState(TypedDict):
    # Identity — populated by FastAPI before invocation
    user_id: str                    # always present, never None — hardcoded to "clarkehines" in dev
    tier: str                       # "admin" | "power" | "standard" — populated by FastAPI from live DB record
    client_type: str                # "tui" | "web" | "mobile"
    assistant_name: str             # per-user, populated by FastAPI from live DB record; client fetches via GET /profile and caches locally

    # Conversation
    messages: list[dict]            # history loaded from repository + current_input appended by FastAPI.
                                    # Each dict is {"role": str, "content": str}. Agent nodes pass this
                                    # directly to Ollama — no manipulation required.
    current_input: str              # the message the user just sent — populated by FastAPI at invocation

    # Project context — session-level only, never persisted
    active_project: str | None      # set by client at session start, None if no project selected.
                                    # Controls project-scoped vault reads and ChromaDB filtering in
                                    # MEMORY_RETRIEVE and CODE. Never touches the database.
                                    # Unrecognised values are passed through — FastAPI does not validate
                                    # whether the project folder exists. MEMORY_RETRIEVE handles this
                                    # case and emits a tier-aware status message if no chunks are found
                                    # for the named project. Zero-initialised to None by FastAPI.

    # Routing
    intent: list[str]               # set by ROUTER — one or more intents. Zero-initialised to [] by FastAPI.
    needs_memory: bool              # set by ROUTER — controls retrieval only. Zero-initialised to False by FastAPI.

    # Context
    retrieved_context: str          # populated by MEMORY_RETRIEVE if invoked — zero-initialised to "" by FastAPI
    skill_context: str              # populated by ROUTER skills check — zero-initialised to "" by FastAPI

    # Output
    response: str                   # populated by active agent node — read by RESPONDER only, never by FastAPI directly. Zero-initialised to "" by FastAPI.
    formatted_response: str         # populated by RESPONDER — read by FastAPI to send done frame. Zero-initialised to "" by FastAPI.

    # Status
    status_message: str | None      # written by nodes mid-execution for granular status updates — FastAPI fires status frame on change. Zero-initialised to None by FastAPI.

    # Error handling
    error: str | None               # set by any node on expected failure, checked by RESPONDER. Zero-initialised to None by FastAPI.

    # Interrupt / confirm
    interrupt_payload: dict | None  # written by node before calling interrupt() — FastAPI builds confirm_request frame from this. Zero-initialised to None by FastAPI.

    # Multi-step execution
    step_plan: list[Step] | None    # produced by PLANNER — zero-initialised to None by FastAPI.
    step_results: list[StepResult]  # accumulated step outcomes written by ORCHESTRATOR after each agent node completes.
                                    # Zero-initialised to [] by FastAPI.

    # Refresh signals
    refresh: list[str]              # populated by RESPONDER only — read by FastAPI to build done frame. Zero-initialised to [] by FastAPI.
```

**FastAPI is responsible for constructing the full initial state dict before every invocation. All fields are required — node-populated fields are zero-initialised (`""`, `False`, `None`, `[]` as appropriate). No field is ever left absent.**

### ROUTER
- Model: `mistral:7b`
- Classifies every input into one or more intents: `memory | tasks | code | web | system | conversation` — writes result as `list[str]` to `intent` on state
- Classification only — ROUTER does not produce a step plan. Step decomposition and dependency inference is PLANNER's responsibility.
- Checks user tier — Standard users cannot be classified into `code` or `system`. If a Standard user's message maps to a tier-gated intent, ROUTER downgrades it to `conversation` and sets a tier-gate flag on state so RESPONDER can explain the limitation.
- Checks personal skills collection (`skills_{user_id}`) then shared skills collection (`skills_shared`) for relevant procedural context — graceful no-op if either collection does not exist yet. Personal skills path derived at runtime: `{memory.vault_base}/{user_id}/02-skills/approved/`. Before reading from either skills path, ROUTER checks whether the directory exists on disk — if it doesn't, that source is treated as empty with no error, matching the behaviour of a missing ChromaDB collection. The skills check is intent-scoped — ROUTER fetches skills relevant to the classified intent(s), not a general sweep. This means `skill_context` on state is already targeted at the destination node(s) before they run.
- Sets `needs_memory: bool` on state — controls whether `MEMORY_RETRIEVE` is invoked. If any classified intent requires memory, `needs_memory` is set to `true`. Does not control whether `memory/persist.py` runs — that fires unconditionally after every exchange.
- MEMORY is flagged as needed for: `memory`, `conversation`, `code` intents
- MEMORY is flagged as needed for `tasks` intent when the request involves reasoning, prioritisation, summarisation, or advice about the task list — e.g. "what should I focus on today?", "am I on track this week?"
- MEMORY is skipped for `tasks` intent when the request is a pure data mutation or retrieval with no reasoning required — e.g. "add a task", "mark that done", "list my tasks"
- MEMORY is skipped for: `web`, `system` intents
- `memory` intent always sets `needs_memory: true` — the MEMORY node operates on `retrieved_context` already populated by MEMORY_RETRIEVE rather than querying ChromaDB itself
- **ROUTER failure handling:** if the inference call fails or times out, ROUTER retries once via `tools/llm.py`. If the retry also fails, it raises to the global exception handler — clean error frame to client, admin notified via ntfy. `tools/llm.py`'s cross-model fallback logic does not apply to ROUTER: the router model (`mistral:7b`) and the fallback model are the same, so there is nothing to fall back to. A successful retry is logged at `WARNING` level.
- Node-entry status frame sent by FastAPI via `astream_events` if `STATUS_MESSAGES["router"]` is set — ROUTER itself does not send frames

### PLANNER
- Model: `REASONING_MODEL` — dependency inference requires genuine reasoning, not just classification
- Always runs after ROUTER — single-intent messages produce a one-step plan and exit immediately with negligible overhead
- Receives ROUTER's classified intents (`list[str]`) and produces a list of `Step` TypedDicts written to `step_plan` on state — see Supporting TypedDicts above for the full `Step` shape
- Dependency inference is the key responsibility — PLANNER determines which steps are independent and which must wait on others based on semantic reasoning about the user's message
- On PLANNER failure: sets `error` on state — graph routes immediately to RESPONDER per the universal error routing rule
- Node-entry status frame sent by FastAPI if `STATUS_MESSAGES["planner"]` is set

### MEMORY_RETRIEVE
- Only invoked when ROUTER sets `needs_memory: true`
- Always queries both `memory_{user_id}` (personal) and `memory_shared` (family) — no conditional logic
- Merges results from both collections, deduplicates by chunk ID, takes top-k by score
- Injects merged results into `retrieved_context` on state as a single block
- Tags memories: `#note #task #fact #code #person #project`
- On ChromaDB unavailable: sets `error` on state, calls `notify_admin("chromadb_unavailable", ...)`. Per the universal error routing rule, the graph skips all downstream nodes and routes immediately to RESPONDER.
- **Unrecognised `active_project`:** if `active_project` is set but no ChromaDB chunks are found tagged with that project name, MEMORY_RETRIEVE does not set `error` — it treats this as a graceful no-op and returns unfiltered results instead. Before doing so it writes a tier-aware `status_message`: Admin: `"No chunks found for project '{active_project}' in ChromaDB — returning unfiltered results"`, Power: `"Couldn't find project '{active_project}' — showing full memory instead"`, Standard: `"I couldn't find that project — showing everything I know instead"`. Inference continues normally with the unfiltered context.
- Node-entry status frame sent by FastAPI via `astream_events` if `STATUS_MESSAGES["memory_retrieve"]` is set — MEMORY_RETRIEVE itself does not send frames. The node writes a mid-node `status_message` immediately before querying ChromaDB — content is tier-aware (Admin: `"Querying memory_{user_id} and memory_shared in ChromaDB..."`, Power: `"Searching your memory..."`, Standard: `"One moment..."`)

### ORCHESTRATOR
- Executes the `StepPlan` from state reactively — one step at a time, result of each step informs the next
- Each iteration:
  1. Find all steps whose `depends_on` are fully satisfied (all named steps completed successfully)
  2. Execute the next ready step by dispatching to the appropriate agent node
  3. After the agent node completes, save `response` into `step_results` before looping
  4. Mark the step `success` or `failure` based on whether `error` was set on state
  5. Clear `error` and `response` on state before the next iteration
- A failed step marks all steps with `depends_on` pointing to it as `blocked` — they are skipped
- Independent steps (no `depends_on` pointing to a failed step) always run regardless of other failures
- Loops until no ready or pending steps remain, then routes to RESPONDER
- Writes a tier-aware `status_message` before dispatching each step:
  - Admin: `"Step 2/3: Dispatching to TASKS — add_shampoo (no dependencies)"`
  - Power: `"Step 2 of 3: Adding your task..."`
  - Standard: `"Adding your task... (2 of 3)"`
- Node-entry status frame sent by FastAPI if `STATUS_MESSAGES["orchestrator"]` is set

### Graph Flow

```
ROUTER → PLANNER → MEMORY_RETRIEVE → ORCHESTRATOR → [agent node] → ORCHESTRATOR → ... → RESPONDER
```

`MEMORY_RETRIEVE` is skipped when `needs_memory: false`. ORCHESTRATOR loops back through agent nodes until the `StepPlan` is exhausted. The graph ends at RESPONDER — there is no case where RESPONDER acts as an agent node, it is always a pure formatter. After the graph completes, FastAPI sends the `done` frame and then fires `memory/persist.py` as an asyncio background task unconditionally after every exchange.

### CONVERSATION
- The default node for general chat — the most-used node for Standard tier users
- Model: `llama3.1:8b`
- Calls Ollama with `messages`, `retrieved_context`, and `skill_context` (if non-empty) — writes result to `response`
- Available to all tiers
- No node-entry status frame by default (`STATUS_MESSAGES["conversation"]` is empty) — tokens stream directly

### MEMORY
- Handles explicit memory queries and management requests — "what do you remember about me?", "forget what I told you about X"
- Operations: query retrieved context, explicit delete/forget against ChromaDB, scoped strictly to `user_id`
- All tiers can query, delete, and forget their own memory — it is the user's data
- Operates on `retrieved_context` already populated by MEMORY_RETRIEVE — does not query ChromaDB directly for retrieval
- Includes `skill_context` in Ollama prompt if non-empty
- Delete/forget operations use the interrupt/confirm pattern — node identifies what will be removed, writes it to `interrupt_payload`, user confirms before the ChromaDB delete executes. On cancel, writes a hardcoded cancellation message to `response`, no further action taken.
- On ChromaDB unavailable at any point — including after the user has confirmed a delete — sets `error` on state, calls `notify_admin("chromadb_unavailable", ...)`. The user's confirmation is consumed; they would need to request the delete again once the service is restored.
- No node-entry status frame by default (`STATUS_MESSAGES["memory"]` is empty)

### TASKS
- Manages per-user to-do list and schedule
- Storage: Postgres (user-scoped) via repository pattern — swappable backend
- All operations receive `user_id` — never queries without it
- Operations: create, update, complete, list, delete
- Task status values: `open | closed`
- Task priority values: `low | medium | high`
- Includes `skill_context` in Ollama prompt if non-empty
- Dev backend: SQLite (same interface, selected via `JARVIS_DB_BACKEND` env var)
- No node-entry status frame by default (`STATUS_MESSAGES["tasks"]` is empty) — writes a specific `status_message` immediately before each operation (before insert, before query, before update, before delete) so the message is accurate for both reads and mutations. The message content is tier-aware: Admin sees technical detail (e.g. "Inserting task into `tasks` via SQLiteTaskRepository..."), Power sees operational detail (e.g. "Adding your task..."), Standard sees plain language (e.g. "Adding task...")
- Delete operations use the interrupt/confirm pattern — node identifies the task, writes it to `interrupt_payload`, user confirms before the delete executes. On cancel, writes a hardcoded cancellation message to `response`, no further action taken.
- Any operation on a task that no longer exists (update, complete, delete) is treated as a graceful no-op — the node writes a tier-appropriate message to `response` (e.g. "That task has already been deleted") rather than raising an error. This handles the race condition where a REST `DELETE /tasks/{id}` call completes while a chat-initiated delete is sitting at the interrupt/confirm gate.

### `Task` Dataclass

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Primary key — assigned by the database on insert |
| `user_id` | string | Foreign key → users table — always required |
| `title` | string | The task description |
| `status` | string | `open` \| `closed` |
| `priority` | string | `low` \| `medium` \| `high` — required on creation, no default |
| `due_date` | datetime \| None | Optional due date |
| `created_at` | datetime | Set on creation, never updated |

### Task REST Endpoints

- `GET /tasks` — returns all tasks for the authenticated user as a JSON array, both open and closed. Accepts optional query parameters `sort_by` and `order` to control server-side sort before returning. Sortable fields: `created_at`, `priority`, `due_date`, `status`. Valid `order` values: `asc | desc`. Default sort: `created_at DESC`. Filtering is the client's responsibility. Note: `priority` is stored as a string enum (`low | medium | high`) — the server must sort it by semantic rank, not alphabetically (i.e. `high > medium > low`), using a `CASE` expression or equivalent. Note: when sorting by `due_date`, tasks with no due date (`null`) sort last regardless of `order` direction — undated tasks are less time-sensitive than dated ones and should never float above them. Note: `created_by` will become a sortable field when shared tasks are introduced in Phase 8.
- `DELETE /tasks/{id}` — permanently deletes a task. Returns `204 No Content` on success. Returns 404 with a clean message body if the task does not exist or does not belong to the requesting user — the 404-for-wrong-user is intentional by design: the server does not confirm whether a given task ID exists for another user (a 403 would reveal that). Built alongside the TASKS node — endpoint and feature ship together. This is a direct HTTP call with no LangGraph in the loop — the server executes immediately on receipt with no server-side confirmation gate. The client owns the confirmation UX entirely (e.g. a simple "are you sure?" dialog before firing the request) and is responsible for surfacing a 404 response visibly to the user in the appropriate UI channel — a toast notification or inline error on the task item, not a silent failure. No AI involvement — this is a direct UI action, not a chat interaction.

All task mutations other than deletion go through the WebSocket chat interface. There is no `PATCH` endpoint in Phase 3 — this is intentional. All mutations have a natural language equivalent, and a direct edit API is not needed until the web dashboard (Phase 5) makes it obvious. If a `PATCH` endpoint is warranted at that point, it is a trivial addition.

### CODE
- Admin and Power tier only
- Model: `deepseek-r1:14b`
- Operations: generate, explain, review, debug, refactor
- Aware of active project context — reads relevant files and notes from the user's vault under `03-projects/<project>/`, including recent code, architecture notes, and open questions. `[pearlybaker only]` — graceful no-op on nomadbaker where the vault is unavailable.
- Includes `skill_context` in Ollama prompt if non-empty
- Can execute code via sandboxed subprocess — uses `tools/sandbox.py`
- No node-entry status frame by default (`STATUS_MESSAGES["code"]` is empty) — writes granular `status_message` updates throughout execution. Content is tier-aware (Admin: full detail including model name and reasoning stage, e.g. `"Reasoning with deepseek-r1:14b — analysing traceback..."`, Power: `"Analysing the problem..."`, Standard: n/a — Standard tier cannot reach CODE)
- **Phase 3: single-agent only** — uses `deepseek-r1:14b` directly, no subgraph
- **Phase 3.5: Coding Team subgraph replaces the internals** — the node's external interface (inputs/outputs to the graph) stays identical, so no graph rewiring is needed
- Coding Team architecture is subject to a dedicated planning session before Phase 3.5 implementation begins

### CODING TEAM (Subgraph)
Multi-agent team for complex coding tasks. Admin and Power tier only. Full internal architecture, sandbox boundaries, interruption model, and loop behaviour to be defined in a dedicated planning session before implementation.

```
Request
   │
   ▼
ARCHITECT     ← breaks task into subtasks, designs solution
   │
   ▼
CODER(s)      ← implements each subtask in sequence
   │
   ▼
REVIEWER      ← critiques output, flags issues
   │
   ▼
TESTER        ← runs code, reports results
   │
loop (configurable max) or surface to user for a decision
```

| Agent | Responsibility | System Prompt Focus |
|---|---|---|
| Architect | Decompose problem, design structure | Senior software architect — plan before code |
| Coder | Implement assigned subtask | Expert coder — implement exactly what is asked |
| Reviewer | Critique output | Code reviewer — find bugs, bad patterns, edge cases |
| Tester | Validate via execution | Run code and report exactly what happens |

- All agents are LangGraph nodes — same Ollama backend, different prompts
- Each subgraph node writes its own `status_message` — content is tier-aware. Admin sees full technical detail (e.g. `"ARCHITECT decomposing task into subtasks using deepseek-r1:14b..."`, `"REVIEWER flagging edge case in auth.py..."`), Power sees operational detail (e.g. `"Architect planning..."`, `"Reviewer checking..."`). Standard tier cannot reach the Coding Team.
- Single GPU means requests queue, but the multi-agent structure produces meaningfully better output than a single agent
- Uses the interrupt/confirm pattern at key decision points — e.g. Architect presents plan before Coder starts, Tester requests confirmation before running against live data. On cancel, nodes write a hardcoded cancellation message derived from `interrupt_payload` — no inference call is made for the cancellation.
- Reviewer → Coder loop capped at configurable max iterations
- All outputs saved to user's vault under `03-projects/<project>/`

### WEB
- Search: DuckDuckGo (no API key, privacy-respecting) via `tools/search.py`
- Scraping: Playwright (headless) via `tools/search.py`
- Returns summarised results, not raw HTML
- Available to all tiers
- Includes `skill_context` in Ollama prompt if non-empty
- Node-entry status frame sent by FastAPI via `astream_events` if `STATUS_MESSAGES["web"]` is set — WEB itself does not send frames
- Writes specific `status_message` updates mid-execution — the query currently being searched. Content is tier-aware (Admin: `"Querying DuckDuckGo: '{query}'..."`, Power: `"Searching the web for '{query}'..."`, Standard: `"Searching the web..."`)

### SYSTEM
- Shell command execution and file operations: read, write, move, search
- Sandboxed to approved paths (defined in `config.yaml` under `system.allowed_paths`) — enforced by `tools/shell.py`
- Admin and Power tier only
- Includes `skill_context` in Ollama prompt if non-empty
- No node-entry status frame by default (`STATUS_MESSAGES["system"]` is empty) — writes two `status_message` updates per command: one before calling `interrupt()` while composing the shell command ("Composing command..."), one immediately after the user confirms and before the command executes ("Executing..."). Content for both is tier-aware — see execution sequence below.
- **Execution sequence:** (1) SYSTEM writes a `status_message` — "Composing command..." (tier-aware: Admin: `"Translating request into shell command via tools/llm.py..."`, Power: `"Working out the command..."`, Standard: n/a) — then calls Ollama to translate the natural language request into a concrete shell command. This inference is internal and not streamed as `token` frames. (2) SYSTEM writes the command to `interrupt_payload` and calls `interrupt()`. (3) FastAPI sends `confirm_request` frame — client disables input and renders a confirmation prompt (e.g. a popup with confirm/cancel). Pre-interrupt phase is otherwise silent from a `status_message` perspective — the `confirm_request` frame handles all pre-execution communication. (4) If confirmed, SYSTEM writes a `status_message` immediately before execution — "Executing now..." (tier-aware: Admin: `"Executing: '{command}' via tools/shell.py..."`, Power: `"Running command: '{command}'..."`, Standard: n/a) — then the command executes via `tools/shell.py`. If cancelled, SYSTEM writes a hardcoded cancellation message to `response` — no further Ollama call.
- **After confirmed execution:** `tools/shell.py` captures stdout and stderr separately. SYSTEM passes both to Ollama to format and summarise into `response` — the response includes context about what came from each channel, with tier-appropriate detail (Admin sees which output came from stdout vs stderr; Standard gets a plain language summary of what happened). Four distinct outcomes: (a) stdout and/or stderr present → Ollama formats both into `response`; (b) both empty, exit code 0 → hardcoded "Done. `<command>` completed successfully.", no Ollama call; (c) both empty, non-zero exit code → hardcoded "Command failed with exit code N and produced no output."; (d) `tools/shell.py` itself cannot spawn the subprocess → sets `error` on state, which triggers the universal error routing rule. This last case is the only one that sets `error` — command-level failures (including stderr output) always go through `response`.
- The client will never receive `token` frames before a `confirm_request` frame from SYSTEM — all token streaming happens after confirmation, or not at all on cancel. `status_message` frames may arrive before the `confirm_request` (the "Composing command..." phase) and after it (the "Executing now..." phase).

### RESPONDER
- Reads `client_type` from `JarvisState` — formats into `formatted_response` accordingly
  - `tui`: plain text with Textual markup
  - `web` / `mobile`: markdown or structured JSON for frontend rendering
- Checks `error` field on state first — if set, writes a clean error message to `formatted_response` instead of a normal response
- **Single-step:** formats `response` directly into `formatted_response` as normal
- **Multi-step:** when `step_results` is non-empty, summarises all steps into a single coherent `formatted_response` — reports what succeeded, what failed, and what was blocked and why. Tier-aware: Admin gets full detail per step, Standard gets a plain-language summary of the overall outcome.
- Sets `refresh` list on state derived from the intents that executed — RESPONDER is the sole owner of the `refresh` field, no other node writes to it. For multi-step, unions the refresh targets from all successful steps.
- Does not send WebSocket frames — FastAPI reads `formatted_response` and `refresh` from final state and sends the `done` frame
- No node-entry status frame by default (`STATUS_MESSAGES["responder"]` is empty)

---

## 🗃️ Memory Architecture

### Short-Term Memory (Conversation History)
- Owned by FastAPI — not LangGraph
- Uses the same repository pattern as TASKS: `SQLiteHistoryRepository` in dev, `PostgresHistoryRepository` in production, selected via `JARVIS_DB_BACKEND` env var
- FastAPI loads the user's most recent conversation history up to `CONTEXT_WINDOW_BUDGET` tokens, dropping oldest exchanges first, and injects it into `JarvisState.messages`. FastAPI then appends `current_input` as the final entry. 16,000 tokens fits safely within all models' context windows while leaving headroom for system prompt, retrieved context, current input, and response. This value is a config key and straightforward to adjust.
- Each dict in `messages` has the shape `{"role": str, "content": str}` — this matches the Ollama chat API format exactly. The repository's `load` method is responsible for returning this stripped format; `HistoryEntry` retains all storage fields internally.
- At the end of every invocation, FastAPI writes the new exchange back to the repository
- Each user's conversation history is fully isolated by `user_id`
- Retention period configured per `RETENTION_DAYS` — enforced by the daily ofelia maintenance job
- **Message editing** — to edit a past message, the client deletes all history entries at or after the selected message and resends the replacement through the normal WebSocket flow. Discarded history is not recoverable. The repository exposes a `delete_from(user_id, entry_id)` method for this purpose.

### History Repository Interface

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

### `HistoryEntry` Dataclass

| Field | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `user_id` | string | Foreign key → users table |
| `role` | string | `user` \| `assistant` |
| `content` | string | Message text |
| `created_at` | datetime | Used for ordering and retention enforcement |

### Long-Term Memory (ChromaDB)

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

### Memory Persistence — `memory/persist.py`

After the graph completes at RESPONDER and FastAPI has sent the `done` frame, FastAPI fires `memory/persist.py` as an asyncio background task. This fires after every exchange that completes with a `done` frame — it is unconditional with respect to `needs_memory` (every successful exchange is evaluated), but is never scheduled when the global exception handler sends an `error` frame instead. `needs_memory` controls retrieval only. The evaluator inside `memory/persist.py` decides whether anything in the exchange is worth writing to long-term memory; it may determine there is nothing to persist and exit cleanly. This means even exchanges that didn't require memory retrieval (e.g. a simple task mutation) are still evaluated — you never know what might be worth remembering.

`memory/persist.py` evaluates the completed exchange (`current_input` + `response`) and decides whether anything new is worth persisting to ChromaDB — reads `response` not `formatted_response`, which avoids persisting client-specific formatting markup. It then writes to `memory_{user_id}` or `memory_shared` based on the personal → shared classifier. It uses `tools/llm.py` for its inference call and `memory/chroma.py` for the write.

If a `tools/llm.py` inference call fails, `memory/persist.py` retries that call once. The retry applies independently to each inference step — the evaluator and the classifier are each retried once if they fail; a failure in one does not abort the other. If the evaluator fails after one retry, the task exits and the exchange is not persisted. If the classifier fails after one retry, `memory/persist.py` defaults to writing to `memory_{user_id}` (personal) rather than dropping the memory — it is safer to persist to the wrong scope than to lose the memory entirely. All failures at this stage are logged at `ERROR` level with no admin notification per individual failure. Repeated failures will accumulate in the error log and trigger the daily maintenance job threshold notification if the count is high enough.

On ChromaDB unavailable: logs the failure and calls `notify_admin("chromadb_unavailable", ...)`.

**Future work:** Two planned additions to the memory system, to be designed and implemented in later phases:
- **Memory pruning** — a scheduled maintenance pass (added to `maintenance/cleanup.py`) that reviews long-term memory and removes stale or superseded entries. Some memories become irrelevant over time.
- **Dream mode** — a deeper consolidation pass that strengthens important memories, merges redundant entries, and surfaces patterns. Heavier than pruning and intended to run less frequently. Architecture TBD.

### Personal → Shared Classification

When JARVIS learns something new, `memory/persist.py` evaluates whether it belongs in personal or shared memory:

```
Personal → private thoughts, preferences, work, personal matters
Shared   → household info, shared plans, family events, shared resources
Ambiguous → personal (default to private, always)
```

The user can always override explicitly: "add this to the family brain" or "keep this private."

### `db/schema.py`

`db/schema.py` exposes a single `create_tables()` function. It opens connections to all three SQLite files and creates the appropriate tables in each:

- `auth.db` — `users`, `refresh_tokens`, `invites`
- `tasks.db` — `tasks`
- `history.db` — `history`

`create_tables()` is called from FastAPI's lifespan context manager on startup, conditional on `DB_BACKEND == "sqlite"`. It is never called at module import time. Using `CREATE TABLE IF NOT EXISTS` means it is safe to call on every startup — it will not alter or overwrite existing tables. When the schema changes during development, delete the relevant `.db` file and let startup recreate it: delete `~/.jarvis/auth.db` for auth tables, `~/.jarvis/tasks.db` for tasks, `~/.jarvis/history.db` for history. Startup will recreate the file and all tables in it. Proper migrations (Alembic) are introduced in Phase 6.

### Vault Structure

Per-user vault (`{memory.vault_base}/{user_id}/` — on pearlybaker this resolves via the `~/jarvis-brain` symlink to `/mnt/hdd/jarvis/<username>/`):
```
<username>/
├── 00-inbox/          # Unprocessed thoughts
├── 01-knowledge/      # Facts, research, references
├── 02-skills/         # Procedural memory
│   ├── approved/      # Live skills the assistant can use
│   ├── pending/       # Candidate skills awaiting review
│   └── retired/       # Old skills kept for reference
├── 03-projects/       # One folder per project
├── 04-conversations/  # Notable exchanges
├── 05-people/         # Contact notes
├── 06-tasks/          # Task archive
├── 07-system/         # Assistant config, spec
└── 08-journal/        # Daily notes
```

Shared vault (`{memory.vault_base}/shared/` — on pearlybaker: `/mnt/hdd/jarvis/shared/`):
```
shared/
├── 00-inbox/          # Unprocessed shared items
├── 01-knowledge/      # Family-wide facts and reference
├── 02-calendar/       # Shared events and schedules
├── 03-tasks/          # Shared household tasks
├── 04-people/         # Shared contacts
└── 05-skills/         # Shared approved skills
    ├── approved/
    └── pending/
```

---

## 🧠 Skills System

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

---

## 🔧 Full Tech Stack

| Component | Technology | Notes |
|---|---|---|
| TUI framework | Textual (Python) | Power-user client |
| API server | FastAPI | Unified backend for all clients |
| Auth | JWT (python-jose) | Access token (24hr) + refresh token (90 days) + token_version per user |
| Orchestration | LangGraph | Stateless per-request agent graph — context injected at invocation, `astream_events` for streaming, graph ends at RESPONDER |
| LLM inference | Ollama | Local, GPU-accelerated, shared, streaming mode |
| Vector store | ChromaDB | Per-user + shared collections, named by convention |
| Embeddings | nomic-embed-text | Via Ollama |
| Primary database | Postgres | Tasks, users, sessions, refresh_tokens, invites, conversation history |
| Dev database | SQLite | Dev stand-in, identical interface via repository pattern |
| Knowledge base | Obsidian vault (Markdown) | Per-user + shared family vault |
| Web search | DuckDuckGo | No key, no tracking — via `tools/search.py` |
| Web scraping | Playwright | Headless — via `tools/search.py` |
| Notifications | ntfy | Admin error alerts via `notifications/notify.py` |
| Containerisation | Docker + Docker Compose | Server deployment |
| Reverse proxy | Caddy | TLS + routing |
| Remote access | Tailscale | All clients connect via Tailscale |
| ZFS storage | `/tank/docker/jarvis/` | Postgres + ChromaDB + vaults on server |
| Task scheduler | ofelia | Daily maintenance job — purge expired tokens, invites, old history |
| Voice STT | Whisper / TBD at Phase 8 | Phase 8 — separate container, FastAPI proxy |
| Voice TTS | Piper / TBD at Phase 8 | Phase 8 — separate container, FastAPI proxy |
| Language | Python 3.11+ | |
| Dev GPU | NVIDIA RTX 3080 (pearlybaker) | CUDA 12.1 |
| Server GPUs | See `server-specs.md` | Dual-GPU inference split — primary for reasoning/coding, secondary for lightweight models |
| Test runner | pytest | Unit + integration suites |

---

## 🧪 Testing Strategy

### Philosophy
Tests are written alongside implementation — never deferred. The goal is confidence that the system works correctly, not coverage for its own sake.

### Structure

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

### Unit Tests (`tests/unit/`)
All external dependencies mocked. Tests verify that nodes read from state correctly, call repositories with the right arguments, handle `error` state properly, and produce correctly structured output. No services need to be running. Runs in seconds.

### Integration Tests (`tests/integration/`)
Real SQLite test database, wiped between runs. Ollama replaced with `MockOllamaClient` (returns hardcoded responses). Tests verify that the repository pattern works end to end — data goes in, comes back out correctly, `user_id` scoping holds, history is written and loaded correctly. Run manually when verifying a full layer.

### No End-to-End Tests (for now)
Testing against a live Ollama instance is slow and non-deterministic. Not worth the maintenance cost until the platform is mature. Can be added later.

### Shared Fixtures (`tests/conftest.py`)
- `test_user` — standard clarkehines admin user, pre-populated
- `test_db` — fresh SQLite database, wiped after each test
- `mock_ollama` — `MockOllamaClient` returning hardcoded responses

### Pre-Commit Hook
`pytest tests/unit/` runs automatically before every commit. Commits are blocked if unit tests fail. Integration tests are not in the pre-commit hook — they're slower and require more setup.

---

## 📦 Build Phases

### Phase 1 ✅ — Foundation
LangGraph skeleton, TUI, Ollama, routing. Done.

### Phase 2 ✅ — Memory
ChromaDB, vault ingestion pipeline, RAG, MEMORY node. Done.

### Phase 3 — Tools + FastAPI Skeleton *(current)*

All tool nodes built with repository pattern and `user_id` scoping from day one. FastAPI skeleton built alongside the first node — all subsequent nodes go straight against the API, no retrofit later.

**Branch:** `phase-3` — merge to main only when phase is complete and verified.

**`[pearlybaker only]` items require a vault and ChromaDB — do not attempt on nomadbaker.**

**FastAPI skeleton (built first, before any tool node):**
- [ ] Minimal FastAPI server — single `/chat` WebSocket endpoint
- [ ] Auth repository — `db/auth/` with full factory pattern mirroring tasks and history
  - [ ] `db/auth/models.py` — User, RefreshToken, Invite dataclasses
  - [ ] `db/auth/repository.py` — abstract base class
  - [ ] `db/auth/sqlite.py` — SQLiteAuthRepository
  - [ ] `db/auth/postgres.py` — PostgresAuthRepository (stub)
  - [ ] `db/auth/factory.py` — reads `JARVIS_DB_BACKEND` env var, defaults to `sqlite`
  - [ ] `api/routes/auth.py` gets its repository via the factory — never accesses storage directly
- [ ] JWT auth — `POST /auth/login` endpoint. Request: `{"username": "...", "password": "..."}`. Response: `{"access_token": "...", "refresh_token": "...", "access_expires_at": "..."}`. Inserts row into `refresh_tokens` on success. Returns 401 on failure. Tracks failed attempts per IP — 5 failures in 10 minutes triggers `notify_admin`.
- [ ] `/auth/refresh` endpoint — silent token renewal, called by `tui/auth.py`. Validates token hash against `refresh_tokens` table — rejects if revoked or expired.
- [ ] `/auth/logout` endpoint — marks current device's refresh token row `revoked = true`. Does not increment `token_version` — other devices stay active.
- [ ] `GET /profile` endpoint — returns `username`, `tier`, `assistant_name` for the authenticated user
- [ ] `PATCH /profile` endpoint — updates `assistant_name`, returns updated profile. Pushes `profile` frame to all of the user's active connections.
- [ ] `/auth/invite` endpoint — Admin only. Generates one-time invite token (48hr expiry), returns raw token to Admin
- [ ] `/auth/register` endpoint — Open (invite token required). Validates token, creates user record, marks invite `used = true`
- [ ] `users` table — fields: `username` (PK), `password_hash`, `tier`, `assistant_name`, `token_version`
- [ ] `refresh_tokens` table — fields: `id`, `user_id`, `token_hash`, `expires_at`, `revoked`
- [ ] `invites` table — fields: `id`, `token_hash`, `username`, `tier`, `assistant_name`, `expires_at`, `used`
- [ ] `db/schema.py` — exposes `create_tables()` function. Opens connections to `auth.db` (users, refresh_tokens, invites), `tasks.db` (tasks), and `history.db` (history) and runs `CREATE TABLE IF NOT EXISTS` for each. Called from FastAPI's lifespan context manager on startup, conditional on `DB_BACKEND == "sqlite"` — never at module import time. When the schema changes during development, delete the relevant `.db` file and let startup recreate it: `~/.jarvis/auth.db` for auth tables, `~/.jarvis/tasks.db` for tasks, `~/.jarvis/history.db` for history. Proper migrations (Alembic) are introduced in Phase 6.
- [ ] `scripts/seed_db.py` — calls `create_tables()` first, then creates initial `clarkehines` admin record. Idempotent, interactive password prompt, prints confirmation. All other users added via invite flow.
- [ ] `JarvisState` updated — all fields present, node-populated fields zero-initialised by FastAPI at invocation (including `interrupt_payload: None`)
- [ ] FastAPI validates `token_version` against database on every request and on every WebSocket message received
- [ ] FastAPI uses `astream_events` — sends node-entry `status` frames driven by `STATUS_MESSAGES` dict. Forwards mid-node `status_message` updates from state as `status` frames. Sends `"One moment..."` status frame immediately when a message is queued during an active invocation. Rejects non-confirm/cancel messages during active interrupt with `"Please confirm or cancel the pending action first."` status frame. On `token_version` mismatch, clears the queue and sends an `error` frame indicating re-authentication was required.
- [ ] WebSocket streaming — typed JSON frames (`token`, `done`, `error`, `status`) with `message_id`. FastAPI owns all frame sending. One invocation at a time per connection — incoming messages queued until `done` frame is sent.
- [ ] Conversation history repository — `db/history/` with SQLite dev backend, Postgres stub (mirrors `db/tasks/` structure exactly)
- [ ] Conversation history load from repository → inject into state as `list[{"role": str, "content": str}]`, bounded by `CONTEXT_WINDOW_BUDGET` tokens. FastAPI appends `current_input` as the final entry before invocation.
- [ ] Conversation history write back to repository after invocation
- [ ] Secrets via env vars only — `JARVIS_SECRET_KEY` hard-fails if unset, no sensitive values in `config.yaml` or git
- [ ] `main.py` — launches FastAPI via uvicorn, `reload=True` in dev
- [ ] `notifications/notify.py` — ntfy wrapper, `notify_admin(error_class, message)`, 10-minute cooldown keyed on `(error_class, message)` tuple
- [ ] Logging configured in `main.py` — `RotatingFileHandler`, path from `LOG_PATH`, 10 MB max per file, 5 files retained, `INFO` level by default
- [ ] FastAPI global exception handler wired to `notify_admin`
- [ ] Daily ofelia maintenance job — purges expired `refresh_tokens`, expired `invites`, and history entries older than `RETENTION_DAYS`. Counts `ERROR`-level log entries from the last 24 hours — notifies admin if over `LOG_ERROR_THRESHOLD`. Intentionally general-purpose — future maintenance tasks added here.
- [ ] **Verify FastAPI works end to end with a throwaway test client before rewriting TUI**

**Then tool nodes (built against FastAPI from the start):**
- [ ] TASKS node — repository pattern, SQLite dev backend, Postgres interface stubbed
  - [ ] `db/tasks/models.py` — Task dataclass with fields: `id`, `user_id`, `title`, `status` (`open|closed`), `priority` (`low|medium|high`), `due_date`, `created_at`
  - [ ] `db/tasks/repository.py` — abstract base class, all methods require `user_id`
  - [ ] `db/tasks/sqlite.py` — SQLiteTaskRepository
  - [ ] `db/tasks/postgres.py` — PostgresTaskRepository (stub)
  - [ ] `db/tasks/factory.py` — reads `JARVIS_DB_BACKEND` env var, defaults to `sqlite`
  - [ ] `graph/nodes/tasks.py` — calls repository only, never raw SQL. Operations: create, update, complete, list, delete.
  - [ ] `GET /tasks` — returns all tasks for the authenticated user as a JSON array (open and closed). Built alongside the TASKS node — endpoint and feature ship together.
  - [ ] `DELETE /tasks/{id}` — permanently deletes a task scoped to the authenticated user. Returns 404 if not found or not owned by requesting user. Built alongside the TASKS node.
- [ ] `tools/llm.py` — Ollama wrapper. Handles streaming, timeout, fallback model logic. All nodes call this rather than Ollama directly.
- [ ] `tools/search.py` — DuckDuckGo search + Playwright scraping wrapper. WEB node calls this.
- [ ] `tools/shell.py` — subprocess runner with path sandboxing against `ALLOWED_PATHS`. Captures stdout and stderr separately. SYSTEM node calls this.
- [ ] `tools/sandbox.py` — sandboxed code execution subprocess. CODE node calls this.
- [ ] `tools/vault.py` — Obsidian vault file reader. CODE node and memory ingestion call this. `[pearlybaker only]`
- [ ] `tools/tokens.py` — token counting utility. History repository uses this to enforce `CONTEXT_WINDOW_BUDGET`.
- [ ] WEB node — calls `tools/search.py`. Writes specific `status_message` for each query. Includes `skill_context` in Ollama prompt if non-empty.
- [ ] SYSTEM node — calls `tools/shell.py` for execution. Confirmation gate via interrupt/confirm. No Ollama streaming before confirmation. On cancel, writes hardcoded cancellation message. Passes both stdout and stderr to Ollama for formatting. Includes `skill_context` in Ollama prompt if non-empty.
- [ ] CODE node — single-agent, calls `tools/llm.py` with reasoning model directly (Coding Team subgraph wired in Phase 3.5). Calls `tools/sandbox.py` for code execution. Calls `tools/vault.py` for project context `[pearlybaker only]`. Writes granular `status_message` updates throughout. Includes `skill_context` in Ollama prompt if non-empty.
- [ ] CONVERSATION node — `graph/nodes/conversation.py`. General chat for all tiers. Calls `tools/llm.py` with `messages`, `retrieved_context`, and `skill_context`. Writes to `response`.
- [ ] MEMORY node — `graph/nodes/memory.py`. Handles explicit memory queries and delete/forget operations against ChromaDB. All tiers. Scoped to `user_id`. Operates on `retrieved_context` — does not query ChromaDB directly for retrieval. `[pearlybaker only]`.
- [ ] `memory/persist.py` — asyncio background task fired by FastAPI unconditionally after every exchange. Evaluates exchange, classifies personal vs shared, writes to ChromaDB if anything is worth persisting. Uses `tools/llm.py` and `memory/chroma.py`. `[pearlybaker only]`
- [ ] `GET /memory` — stub response in Phase 3 (ChromaDB is `[pearlybaker only]`). Returns an empty JSON array `[]`. Endpoint exists so TUI refresh handling is fully wired and testable.
- [ ] ROUTER updated — `needs_memory` flag per intent controls retrieval only (conditional on request type for `tasks` — see ROUTER spec), skills check with graceful no-op `[pearlybaker only for skills check]`
- [ ] RESPONDER updated — reads `client_type` from state, checks `error` field, derives and sets `refresh` list on state from `intent` (RESPONDER is sole owner of `refresh`)
- [ ] `MEMORY_RETRIEVE` node — queries ChromaDB, populates `retrieved_context` `[pearlybaker only]`
- [ ] TUI rewritten — connects to FastAPI WebSocket instead of local LangGraph (only after FastAPI is verified working). Opens connection on startup, reconnects automatically on drop. Disables input field on `confirm_request` frame, re-enables on resolution.
- [ ] TUI auth client (`tui/auth.py`) — token storage in `~/.jarvis/auth.json`, silent refresh, handles 401 token version mismatch, deletes `auth.json` on logout, login prompt if `auth.json` missing or refresh token expired/revoked. Calls `GET /profile` on startup and after every login/refresh to populate `tier` and `assistant_name` in memory. Handles `profile` WebSocket frames by re-fetching `GET /profile`.
- [ ] TUI listens for `done` frames and re-fetches panels listed in `refresh`
- [ ] Unit tests alongside every node implementation

#### TUI Token Management

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
- [ ] Pre-commit hook configured — `pytest tests/unit/` blocks commits on failure

**Exit criteria:** JARVIS can search the web, manage tasks (create, update, complete, delete), run shell commands, switch into coding mode (single-agent), handle general conversation via CONVERSATION node, and respond to explicit memory queries via MEMORY node `[pearlybaker only]` — on nomadbaker, verify that the `memory` intent returns a clean ChromaDB unavailable error message. TUI connects to FastAPI via WebSocket, tokens stream word by word. Responses arrive as typed JSON frames. Tasks panel updates automatically when tasks are mutated — `GET /tasks` and `DELETE /tasks/{id}` endpoints verified working and TUI re-fetches on `refresh: ["tasks"]`. All data operations go through repository interfaces with `user_id` — including auth. Conversation history correctly written and loaded across multiple exchanges. Admin notified via ntfy on service failures. Secrets are env-var only. Full auth flow verified end to end: login produces a valid JWT, `GET /profile` returns correct user data, `PATCH /profile` updates `assistant_name` and returns the updated profile, silent refresh works, logout revokes the token. Invite+register verified end to end: Admin generates an invite token via `POST /auth/invite`, a second user registers via `POST /auth/register` with that token, that user logs in and receives a valid JWT, and at minimum one WebSocket chat exchange completes successfully as that user with data correctly scoped to their `user_id`. No external services required to run in dev (memory/skills work deferred to pearlybaker). Queuing and interrupt/confirm contracts verified: queued messages receive `"One moment..."` status frame, non-confirm/cancel messages during interrupt are rejected with appropriate status frame, TUI disables input on `confirm_request`.

### Phase 3.5 — Coding Team + Skills System

**Coding Team requires a dedicated planning session before implementation begins.** Internal architecture (sandbox boundaries, interruption model, loop behaviour, Tester constraints) must be fully specified before any code is written.

- [ ] Dedicated Coding Team planning session
- [ ] Architect, Coder, Reviewer, Tester nodes as LangGraph subgraph
- [ ] Each subgraph node writes its own `status_message` — "Architect planning...", "Coder implementing...", "Reviewer checking...", "Tester running..."
- [ ] On cancel at any interrupt point, node writes hardcoded cancellation message derived from `interrupt_payload` — no inference call
- [ ] Tier gate — Admin and Power only
- [ ] Skills vault structure created (personal + shared)
- [ ] Skill ingestion — personal (`skills_{user_id}`) and shared (`skills_shared`) pipelines
- [ ] ROUTER checks personal + shared skills before every action
- [ ] Assistant proposes skills → `pending/` for review
- [ ] Reviewer → Coder loop with configurable max iterations

**Exit criteria:** Complex coding task runs through full team loop. A shared skill is approved and used across multiple users.

### Phase 4 — Multi-User + Full Auth

FastAPI skeleton exists from Phase 3. This phase completes the multi-user platform.

- [ ] Full user management — three test accounts (admin, power, standard) created via invite flow, tiers and assistant names verified
- [ ] All agent nodes accessible via API with tier gating
- [ ] Per-user data scoping verified end-to-end
- [ ] Refresh token rotation
- [ ] User management endpoints (Admin only) — `PATCH /admin/users/{username}` for tier changes and forced deauth (`token_version` increment)
- [ ] Assistant name hotswappable — `PATCH /profile` updates DB, server pushes `profile` frame to all active connections, clients re-fetch `GET /profile`
- [ ] Tier changes hotswappable — admin updates DB via `PATCH /admin/users/{username}`, server pushes `profile` frame to all active connections, clients re-fetch `GET /profile`
- [ ] Multiple concurrent users verified

**Exit criteria:** Three test users exist — one of each tier (admin, power, standard) — all created via invite flow except the admin. All three can chat simultaneously with fully isolated data. Tier gating verified (standard user cannot access code or system nodes). Assistant names and tiers are hotswappable — changes propagate to all active connections via `profile` WebSocket push within seconds, no re-login required.

### Phase 5 — Clients *(developed against local dev setup)*

Six clients, each in its own repo, all connecting to FastAPI over Tailscale. No client has a privileged path to the backend — the API contract is the same for all. Nothing is accessible over the open internet.

Clients are built and tested against the local SQLite dev setup before the server exists. Once Phase 6 brings the server online, all clients point there instead — no client code changes required, just a config update.

#### Client summary

| Repo | Platform | Stack | Tier | Admin panel |
|---|---|---|---|---|
| `jarvis-tui` | Linux + Windows | Python/Textual | Admin/Power | Yes (tier-gated — shown for Admin) |
| `jarvis-desktop-linux` | Linux | Python/GTK4 + libadwaita | All | Yes |
| `jarvis-desktop-windows` | Windows | C#/WinUI 3 | All | No |
| `jarvis-desktop-macos` | macOS | Swift/SwiftUI | All | No |
| `jarvis-ios` | iOS | Swift/SwiftUI | All | Yes |
| `jarvis-web` | Browser | React | All | No |

`jarvis-swift-core` — separate repo, a shared Swift Package consumed by both `jarvis-desktop-macos` and `jarvis-ios`. Contains auth, token refresh, WebSocket client, and API models.

#### Repo extraction (done first)
- [ ] Extract TUI into `jarvis-tui` — own venv + requirements, no imports from backend repo
- [ ] Create `jarvis-swift-core` — shared Swift Package for macOS and iOS
- [ ] Create remaining client repos with basic project scaffolding

#### Features — all clients
- [ ] Login screen — prompts for credentials, stores tokens on success
- [ ] Chat panel — full WebSocket flow, streaming token display
- [ ] Tasks panel — reads `GET /tasks`, updates automatically on `done` frame `refresh` array
- [ ] Memory panel — reads `GET /memory` (stub until Phase 7)
- [ ] Skill approval queue — Admin/Power only, shown based on JWT tier claim
- [ ] User settings — assistant name, preferences
- [ ] Silent token refresh — handled transparently, user never sees it
- [ ] Handles `profile` WebSocket frames — re-fetches `GET /profile` on receipt
- [ ] Reconnects automatically on dropped WebSocket connection

#### Admin panel — TUI, Linux desktop, iOS only
- [ ] User management — invite generation, token invalidation, tier changes
- [ ] System status — active connections, server health
- Intentionally minimal — a full observability and statistics dashboard is a future addition

#### Token storage
Per-client storage is the current approach. Centralised storage via the server's Vaultwarden instance is a planned future upgrade — see Future Work.

| Client | Storage |
|---|---|
| TUI | `~/.jarvis/auth.json` (Linux + Windows) |
| Linux desktop | `~/.jarvis/auth.json` or libsecret keyring |
| Windows desktop | Windows Credential Manager |
| macOS desktop | Keychain |
| iOS | Keychain |
| Web | httpOnly cookie for refresh token, memory-only for access token |

#### Distribution
| Client | Method |
|---|---|
| TUI | Install script — Linux (bash) and Windows (PowerShell) |
| Linux desktop | Install script (clone, venv, deps, optional `.desktop` file) |
| Windows desktop | Installer package (WiX or similar) |
| macOS desktop | `.app` bundle, direct download |
| iOS | TestFlight |
| Web | Deployed at `jarvis.home` via Docker Compose (service definition added in Phase 6) |

Auto-update for desktop apps is a future addition — see Future Work.

**Exit criteria:** All six clients in separate repos with install/setup scripts. Full family accessible via their preferred client over Tailscale. Admin can generate an invite token, change a user's tier, and force-deauth a user from the Linux desktop, TUI, or iOS app. macOS and iOS share `jarvis-swift-core`.

### Phase 6 — Server Deployment + Postgres Migration *(summer 2026)*

Postgres lives on the server — there is no reason to run it locally in dev. SQLite handles development; Postgres is introduced here alongside the server stack.

**Postgres migration:**
- [ ] `PostgresAuthRepository` full implementation
- [ ] `PostgresTaskRepository` full implementation
- [ ] `PostgresHistoryRepository` full implementation
- [ ] `JARVIS_DB_BACKEND=postgres` env var switches all repository backends
- [ ] Alembic introduced — migration tooling for all future schema changes. Replaces drop-and-recreate dev convention. All schema changes from this point forward go through Alembic migrations.
- [ ] Migration script: SQLite → Postgres

**Server deployment:**
- [ ] Docker Compose for full JARVIS stack
- [ ] All services containerised — Postgres, ChromaDB, Ollama (primary), Ollama (secondary), FastAPI, web client
- [ ] Data on `/tank/docker/jarvis/` (ZFS, auto-snapshotted)
- [ ] Caddy entry — `jarvis.home`
- [ ] Tailscale access from all devices
- [ ] ofelia for scheduled tasks including daily maintenance job
- [ ] All clients pointed at server — config update only, no code changes
- [ ] Voice container placeholders in Docker Compose (STT + TTS service definitions, no implementation yet)

**Dual-GPU inference split:**
- [ ] Second GPU installed — cheaper secondary card dedicated to lightweight inference
- [ ] Two Ollama instances: primary (4070 Ti Super) serves reasoning and coding models, secondary serves lightweight models (ROUTER, CONVERSATION, TASKS, MEMORY, WEB, SYSTEM, RESPONDER)
- [ ] `config.yaml` — `ollama_url_primary` and `ollama_url_secondary`
- [ ] `tools/llm.py` — model-based routing: checks requested model name, routes to the correct Ollama instance. No tier logic needed — the model encodes the workload type.

**Exit criteria:** JARVIS running on server against Postgres. All clients connect over Tailscale. All data on ZFS. All schema changes go through Alembic. Lightweight inference (chat, tasks, routing) never contends with heavy inference (planning, coding).

**Note:** Post-deployment, all development runs against the live server stack over Tailscale. The SQLite dev backends (`auth.db`, `tasks.db`, `history.db`), local vault paths, and `[pearlybaker only]` annotations become redundant at this point and may be retired.

**Post-Phase-6 cleanup task:** Once the server is running and all clients are connecting to it, do a full cleanup pass: remove all `[pearlybaker only]` annotations and conditional code paths, retire nomadbaker stand-in model config, consolidate all vault and data paths to `/tank/docker/jarvis/`, and remove the SQLite dev scaffolding from the spec, codebase, and databases.

### Phase 7 — Multi-User Onboarding
- [ ] Family member accounts created via invite flow
- [ ] Per-user vaults initialised
- [ ] Shared family vault populated with household knowledge
- [ ] Shared vault ingested — `memory_shared` ChromaDB collection populated
- [ ] Shared skills ingested — `skills_shared` ChromaDB collection populated
- [ ] ROUTER verified to query `skills_shared` and return relevant results
- [ ] Personal → shared memory classifier tuned
- [ ] Each user sets their assistant name

**Exit criteria:** All family members using JARVIS daily. Shared and personal memory working correctly. ROUTER successfully retrieves from both personal and shared skills collections.

### Phase 8 — Voice

Voice is an add-on — the rest of the platform is fully functional without it. The specific STT/TTS software may change before this phase is reached given the pace of progress in the voice AI space; the architecture below is the current best guess but should be revisited at Phase 8 planning time.

**Planned architecture:**
- STT and TTS each run as separate Docker containers with internal API endpoints
- FastAPI proxies STT/TTS requests to these containers — clients never call them directly
- Phase 6's Docker Compose will include placeholder service definitions for both containers so the internal network topology is correct from the start, even before Phase 8 implements them properly

**Checklist:**
- [ ] STT container — Whisper (or equivalent at time of implementation)
- [ ] TTS container — Piper (or equivalent at time of implementation)
- [ ] FastAPI STT/TTS proxy endpoints
- [ ] Wake word detection (optional)
- [ ] Voice mode in TUI and web client

**Exit criteria:** Hands-free JARVIS interaction.

---

## 📁 Project Directory Structure

```
~/projects/jarvis/
├── config.yaml              # Non-sensitive config — single source of truth
├── config.py                # Reads config.yaml + env vars — only file that touches either
├── main.py                  # Dev entry point — launches FastAPI via uvicorn (reload=True)
├── .env                     # Actual secret values — never committed, listed in .gitignore
├── .env.example             # Canonical list of required env vars with empty values — committed to git
│                            #   JARVIS_SECRET_KEY=        # JWT signing secret — required always, including before running scripts (config.py hard-fails on import if unset)
│                            #   JARVIS_DB_BACKEND=sqlite  # sqlite | postgres — defaults to sqlite
│                            #   JARVIS_DB_URL=            # Postgres connection URL — required when DB_BACKEND=postgres
├── scripts/
│   └── seed_db.py           # First-run setup — creates initial clarkehines admin record only. All other users via invite flow.
├── tui/                     # Textual client
│   ├── app.py
│   ├── auth.py              # Token manager — silent refresh, 401 handling, ~/.jarvis/auth.json (deleted on logout). Opens WebSocket on startup, reconnects on drop. Disables input on confirm_request, re-enables on resolution.
│   ├── panels/
│   └── styles/
├── api/                     # FastAPI server
│   ├── server.py
│   ├── schemas.py           # Pydantic models for API request/response shapes
│   ├── dependencies.py      # get_current_user, get_connected_client_ws, ConnectedClient, tier checks
│   ├── connections.py       # Connection registry — maps user_id to active WebSockets, profile push
│   └── routes/
│       ├── auth.py          # JWT auth — access + refresh tokens, token_version validation, invite + register flow. Gets auth repository via db/auth/factory.py.
│       ├── chat.py          # WebSocket streaming endpoint — owns all frame sending, uses astream_events, drops messages during active invocation, fires memory/persist.py as background task after every exchange
│       ├── profile.py       # GET /profile, PATCH /profile
│       ├── tasks.py         # GET /tasks, DELETE /tasks/{id}
│       └── memory.py        # GET /memory (stub in Phase 3)
├── graph/                   # LangGraph — graph ends at RESPONDER
│   ├── graph.py
│   ├── state.py             # JarvisState — all fields required, node-populated fields zero-initialised by FastAPI
│   ├── nodes/
│   │   ├── router.py        # Sets intent + needs_memory (retrieval only), checks skills (intent-scoped), populates skill_context
│   │   ├── memory_retrieve.py  # Runs only when needs_memory=True — retrieves from ChromaDB
│   │   ├── conversation.py  # General chat — all tiers, calls tools/llm.py with messages + retrieved_context + skill_context
│   │   ├── memory.py        # Explicit memory queries and delete/forget — all tiers, scoped to user_id
│   │   ├── tasks.py         # Task management — calls db/tasks/ repository
│   │   ├── code.py          # Coding — calls tools/llm.py, tools/sandbox.py, tools/vault.py
│   │   ├── web.py           # Web search — calls tools/search.py
│   │   ├── system.py        # Shell execution — calls tools/shell.py, interrupt/confirm before every command, stdout+stderr both passed to Ollama for formatting
│   │   └── responder.py     # Pure formatter — checks error field, formats for client_type, derives and sets refresh list on state. Never an agent node. Graph ends here.
│   └── coding_team/         # Subgraph — architecture TBD in planning session
│       ├── subgraph.py
│       ├── architect.py
│       ├── coder.py
│       ├── reviewer.py
│       └── tester.py
├── tools/                   # Utility wrappers — stateless callables used by graph nodes. Add new capabilities here.
│   ├── llm.py               # Ollama wrapper — streaming, timeout, fallback model logic. All nodes call this.
│   ├── search.py            # DuckDuckGo search + Playwright scraping. Used by WEB node.
│   ├── shell.py             # Subprocess runner with path sandboxing against ALLOWED_PATHS. Captures stdout and stderr separately. Used by SYSTEM node.
│   ├── sandbox.py           # Sandboxed code execution subprocess. Used by CODE node.
│   ├── vault.py             # Obsidian vault file reader. Used by CODE node and memory ingestion. [pearlybaker only]
│   └── tokens.py            # Token counting utility. Used by history repository to enforce CONTEXT_WINDOW_BUDGET.
├── db/                      # All persistence — repositories, models, factories, schema
│   ├── schema.py            # Exposes create_tables() — called from FastAPI lifespan on startup (sqlite only)
│   ├── auth/
│   │   ├── models.py        # User, RefreshToken, Invite dataclasses
│   │   ├── repository.py    # Abstract base class
│   │   ├── sqlite.py        # SQLiteAuthRepository
│   │   ├── postgres.py      # PostgresAuthRepository (stub in Phase 3, full in Phase 6)
│   │   └── factory.py       # Reads JARVIS_DB_BACKEND env var, defaults to sqlite
│   ├── tasks/
│   │   ├── models.py        # Task dataclass — id, user_id, title, status, priority, due_date, created_at
│   │   ├── repository.py    # Abstract base class — all methods require user_id
│   │   ├── sqlite.py        # SQLiteTaskRepository
│   │   ├── postgres.py      # PostgresTaskRepository (stub in Phase 3, full in Phase 6)
│   │   └── factory.py       # Reads JARVIS_DB_BACKEND env var, defaults to sqlite
│   └── history/
│       ├── models.py        # HistoryEntry dataclass — id, user_id, role, content, created_at
│       ├── repository.py    # Abstract base class — load(user_id) -> list[dict], save(user_id, role, content)
│       ├── sqlite.py        # SQLiteHistoryRepository
│       ├── postgres.py      # PostgresHistoryRepository (stub in Phase 3, full in Phase 6)
│       └── factory.py       # Reads JARVIS_DB_BACKEND env var, defaults to sqlite
├── memory/                  # ChromaDB operations and long-term memory persistence
│   ├── chroma.py            # ChromaDB client — collections named by convention
│   ├── ingest.py            # Vault ingestion pipeline
│   ├── retrieval.py         # Queries memory_{user_id} + memory_shared
│   └── persist.py           # Background task — fired unconditionally after every exchange. Evaluates exchange, classifies personal vs shared, writes to ChromaDB if worth persisting.
├── notifications/
│   └── notify.py            # ntfy wrapper — notify_admin(error_class, message), 10-min cooldown per (error_class, message)
├── maintenance/
│   └── cleanup.py           # Daily maintenance job — purge expired tokens, invites, old history
├── tests/
│   ├── conftest.py          # Shared fixtures — test_user, test_db, mock_ollama
│   ├── unit/                # Fast, mocked — run on every commit via pre-commit hook
│   │   ├── test_router.py
│   │   ├── test_tasks_node.py
│   │   ├── test_responder.py
│   │   └── ...
│   └── integration/         # Real SQLite, Ollama mocked — run manually
│       ├── test_tasks_repository.py
│       ├── test_history_repository.py
│       └── ...
```

---

## 🔮 Future Work

Additions planned after all phases are complete. Not tied to any specific phase — these get tackled once the core platform is stable and the priority feels right.

### Client auto-update
Desktop clients (Linux, Windows, macOS) have no auto-update mechanism — users reinstall manually when a new version is available. A lightweight solution: the app pings a version endpoint on the server at startup, and prompts the user to re-download if behind. Applies to `jarvis-desktop-linux`, `jarvis-desktop-windows`, and `jarvis-desktop-macos`. iOS (TestFlight) and web handle updates automatically.

### Centralised token storage via Vaultwarden
Per-client token storage (auth.json, Keychain, Credential Manager) works but means credentials are siloed per device. Future: clients authenticate against Vaultwarden on the server, so tokens are centralised and consistent across all devices. Requires Vaultwarden API integration in each client.

### Admin observability dashboard
The Phase 5 admin panel is intentionally minimal (user management, system status). A full dashboard — usage metrics, per-user activity, model performance, memory growth over time — is a post-base-development addition once the platform has enough runtime data to make it useful.

### User notifications (`notify_user`)
A `notify_user(user_id, message, type)` function for user-facing async notifications — background task completion, deadline reminders, etc. Delivery via WebSocket push to the active client, with ntfy as a fallback for offline delivery. Distinct from `notify_admin`.

### Secondary GPU parallel inference (`OLLAMA_NUM_PARALLEL`)
If monitoring shows the secondary Ollama instance bottlenecking under simultaneous lightweight requests, enable `OLLAMA_NUM_PARALLEL=2` on that instance. Both small models (mistral:7b ~4GB, llama3.1:8b ~5GB) fit simultaneously in 12GB VRAM, leaving headroom for two concurrent generations. Only worth configuring if real usage data shows it is necessary.

### TUI interrupt channel (`/btw`)
A secondary input channel for power TUI users — allows a message to be injected mid-invocation without cancelling the current one. Opt-in, TUI-only. All other clients remain strictly one-message-at-a-time.

### Dream mode (memory)
A deeper memory consolidation pass that strengthens important memories, merges redundant entries, and surfaces patterns across a user's history. Heavier than the daily pruning pass — intended to run less frequently (weekly or on demand). Architecture TBD at design time.

### `PATCH /tasks/{id}`
A direct task edit REST endpoint. Not needed while all mutations go through the chat interface, but may become obvious once the web dashboard is built. Trivial to add at that point.

### Voice mode in all clients
Phase 8 adds STT/TTS infrastructure and voice mode to the TUI. Extending voice input/output to the desktop and iOS clients is left for after Phase 8 proves the architecture.
