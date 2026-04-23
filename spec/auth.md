# JARVIS — Auth

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

WebSocket connections are validated at connection time. `token_version` is checked on every new message received over the connection — if the stored version has been incremented since the connection was opened (e.g. an admin forced a full deauth), the connection is closed with a clean `error` frame on the next message. The depth-1 message buffer is cleared on mismatch — any buffered message is dropped and not processed. The `error` frame indicates that re-authentication was required; the user re-authenticates via the normal silent refresh flow and re-sends manually. In practice this scenario is rare since the client disables input during active invocations, meaning the queue will typically have at most one message in it.

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
