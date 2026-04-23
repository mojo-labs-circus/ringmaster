# JARVIS — API: Logging, Error Handling & WebSocket Contract

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

`notify_admin` is fire-and-forget — it never raises. If ntfy is unreachable, the failure is caught, logged at `WARNING` level, and the caller continues normally. Logging at `WARNING` (not `ERROR`) is intentional — ntfy being down is an infrastructure issue, not a code bug. Logging at `ERROR` would cause those entries to accumulate against the log threshold, which would then trigger `notify_admin`, which would fail, creating a feedback loop.

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

**One message at a time, depth-1 queue:** FastAPI processes one invocation per user at a time. If a message arrives during an active invocation, it is held in a depth-1 buffer — last message wins. If a second message arrives before the first queued one is processed, it replaces it. When the active invocation completes, the buffered message is processed automatically. The server sends a `"One moment..."` status frame when a message is queued. The client should visually indicate the busy state. This is a safety net, not a feature — in normal use messages arrive when the assistant is idle.

**Future work — TUI interrupt channel:** A `/btw` style mechanism for power TUI users may be added in a later phase, allowing a secondary message to be injected mid-invocation without displacing the queue. This is opt-in, TUI-only, and not part of the core contract.

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
{"type": "truncate",        "message_id": "abc123", "token_count": 12}
{"type": "retract",         "message_id": "abc123", "replacement": "...corrected response..."}
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
| `truncate` | server → client | Constitutional check detected a violation mid-stream — client strips back to `token_count` tokens already displayed. Corrected continuation follows immediately as normal `token` frames. Only sent during active streaming; the happy path produces no truncate frame. |
| `retract` | server → client | Constitutional check detected a violation after `done` was already sent (violation was in the tail of the response). Client replaces the full displayed response with `replacement`. Owned by `chat.py` — fired after awaiting the CONSTITUTIONAL task post-`done`. Distinct from `truncate` — this fires after the stream has closed, not during it. |

### message_id

Every frame carries a `message_id` generated by the client at request time (short random string — no need for UUID). This allows the client to match response frames to the request that triggered them, and to distinguish them from server-push frames.

**Client → server — two message shapes:**

Regular messages (no `type` field):
```json
{"message_id": "abc123", "content": "what's on my task list"}
{"message_id": "abc123", "content": "what's on my task list", "active_project": "jarvis"}
```

Interrupt responses (`type` field present):
```json
{"type": "confirm", "message_id": "abc123"}
{"type": "cancel",  "message_id": "abc123"}
```

FastAPI dispatches on the presence of `type` — `confirm` or `cancel` routes to `graph.resume()`, no `type` means a regular message. No other client-originated `type` values are valid.

`active_project` is optional on regular messages — omit when no project is selected. The client owns this state: when the user selects a project (web: project selector button, TUI: `/project <name>` slash command), the client stores it and includes it in every subsequent message until changed or cleared. FastAPI reads it from each message envelope and passes it to `JarvisState` — no per-connection storage needed. If absent, FastAPI sets `active_project: None` on state.

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
