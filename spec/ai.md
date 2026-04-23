# JARVIS — AI: Model Stack & Agent Nodes

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
- **Phase 8: Coding Team subgraph replaces the internals** — the node's external interface (inputs/outputs to the graph) stays identical, so no graph rewiring is needed
- Coding Team architecture is subject to a dedicated planning session before Phase 8 implementation begins

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

### CONSTITUTIONAL
- Runs as a concurrent async task launched by FastAPI at the moment token streaming begins — not a LangGraph node in the graph, but a parallel coroutine
- Consumes the token buffer as it fills, reading ahead of what has been sent to the client
- When a violation is detected mid-stream: FastAPI sends a `truncate` frame with `token_count` set to the number of clean tokens already sent, halts the current stream, generates a corrected continuation, and streams it as normal `token` frames from that point
- When no violation is detected: the coroutine completes silently — no frame sent, no latency added
- Uses the lightweight/fast model from `config.yaml` — watching a stream for ethics violations is a simple binary task, not a reasoning task
- The ethics principles are hardcoded in this node — not loaded from config or any user-editable source. Changing them requires a code change, by design
- `retract` (post-stream async correction) is a separate mechanism owned by individual nodes — CONSTITUTIONAL only ever fires `truncate`
- Admin-tier status messages surface the check result (`"Constitutional check: passed"` or `"Constitutional check: violation at token 12 — truncating"`). Power and Standard tiers see nothing — invisible on the happy path, `truncate` handles the violation case without surfacing internals

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
