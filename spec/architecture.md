# JARVIS — Architecture & Users

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
9. Agent node executes — calls Ollama silently, writes output to `step_response`. No `token` frames are sent during agent node execution. Status frames keep the user informed (`status_message` updates, node-entry `STATUS_MESSAGES`).
10. ORCHESTRATOR marks the step complete, clears `error` and `step_response`, dispatches the next ready step — loops until the `StepPlan` is exhausted
11. RESPONDER makes an LLM call to assemble all `step_results` into a single coherent `assembled_response` (clean markdown). RESPONDER is the sole source of `token` frames — `chat.py` only forwards `on_chat_model_stream` events where `langgraph_node == "responder"`. Sets `refresh` on state.
12. Graph returns final state to FastAPI
13. FastAPI writes new exchange to conversation history repository — synchronous, happens before `done` is sent. A single SQL INSERT, negligible latency. Writing before `done` guarantees conversation continuity — a crash after this point cannot lose the exchange from history.
14. FastAPI sends `done` frame with `refresh` array from state
15. FastAPI fires `memory/persist.py` as an asyncio background task — not fired on `error` frame paths. Unconditional with respect to `needs_memory` (every successful exchange is evaluated), but never fired when the global exception handler handles the request instead of RESPONDER. Runs after `done` frame is sent, does not block the client.

### Key Architecture Principles
- **LangGraph is stateless between requests.** It receives all context it needs at invocation start and returns output. It does not own persistence.
- **FastAPI owns persistence.** Conversation history lives in Postgres. FastAPI loads it before each invocation and writes it back after.
- **FastAPI owns the WebSocket.** FastAPI sends all frames (`token`, `done`, `error`, `status`). LangGraph nodes never touch the WebSocket — they only transform state.
- **FastAPI owns state initialisation.** FastAPI constructs the full `JarvisState` before every invocation, including appending `current_input` to `messages`. Nodes never manipulate the messages list directly.
- **The graph ends at RESPONDER.** MEMORY_PERSIST is a FastAPI background task, not a graph node. The graph's job is done the moment RESPONDER writes `assembled_response` to state.
- **All clients are equal.** All clients connect to FastAPI over Tailscale. No client has a privileged path to LangGraph.
- **All secrets via environment variables.** Nothing sensitive ever touches `config.yaml` or git. See Secrets section.
- **Errors are handled at the node level.** Nodes catch expected failures and write to `JarvisState.error` — RESPONDER formats clean messages for the client. Unexpected exceptions bubble to FastAPI's global handler.
- **Any node setting `error` routes immediately to RESPONDER.** This applies at the top-level graph — ROUTER, PLANNER, MEMORY_RETRIEVE, and ORCHESTRATOR itself route directly to RESPONDER when `error` is set, skipping all downstream nodes. Agent nodes dispatched within ORCHESTRATOR's reactive loop (CONVERSATION, TASKS, MEMORY, WEB, SYSTEM, CODE, SKILLS) are the exception: their outbound edge always routes back to ORCHESTRATOR regardless of error state. ORCHESTRATOR reads the error, marks the step failed, clears `error`, and continues the loop. RESPONDER formats the error with tier-appropriate detail: Admin gets full technical detail (component, error class, what failed and where), Power gets operational detail (what couldn't be completed, plain reason), Standard gets plain English specific to what the user asked for (no technical terms, but not vague — e.g. "I couldn't retrieve your memories for this request" not "something went wrong"). Regardless of tier, the error is always logged at `ERROR` level so full detail is available on the server.
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
