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
| Prompt rewriting (PROMPT_ENGINEER node) | `llama3.1:8b` | `qwen2.5:14b` | `qwen2.5:3b` |
| Planning / dependency inference (PLANNER node) | TBD — 32B reasoning model | `qwen2.5:14b` | `qwen2.5:3b` |
| Step decomposition (DECOMPOSER node) | `llama3.1:8b` | `qwen2.5:14b` | `qwen2.5:3b` |
| Reasoning / coding (CODE node) | `deepseek-r1:14b` | `deepseek-coder-v2:16b` | `qwen2.5:3b` |
| Constitutional check (ethics monitor) | `mistral:7b` | `mistral:7b` | `qwen2.5:3b` |
| Embeddings (memory ingest + retrieval) | `nomic-embed-text` | `nomic-embed-text` | `nomic-embed-text` |
| Multimodal / image understanding | `llava:13b` | — | — |
| Fallback (primary model failure) | `mistral:7b` | `mistral:7b` | `qwen2.5:3b` |

**Rules:**
- Every node has its own model key in `config.yaml`, named after the node. Most default to the general model but each is independently overridable — swap one key to point a node at a fine-tuned variant without touching code.
- Model assignments upgrade via `config.yaml` only — no code changes needed as hardware improves or fine-tuned variants are introduced

---

## 🤖 Agent Nodes (LangGraph)

Every node receives a `JarvisState` that includes `user_id`, `tier`, `client_type`, and `assistant_name`. Conversation history is not pre-loaded into state — nodes that need it call `tools/history.py` directly with the limit appropriate for their role. All data operations are scoped to the requesting user via repository interfaces. Nodes never touch raw storage directly and never touch another user's data.

All agent nodes call `should_retrieve()` before their LLM call — whether retrieval actually happens is decided at runtime based on the current `active_step_prompt`. The contract is in `tools/memory.py`. The only exception is MEMORY itself — explicit memory intent always retrieves, so it calls `retrieve_context()` directly without the gate. Coordination and formatting nodes (ROUTER, PLANNER, DECOMPOSER, ORCHESTRATOR, RESPONDER) do not retrieve memory.

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
    intent: str        # the node to dispatch to — "tasks" | "memory" | "code" | "web" | "system" | "conversation" | "skill"
    skill_name: str | None  # populated by ROUTER for skill steps in Phase 8 — registry name of the skill to invoke. None for all other intent types.
    description: str   # plain-language description of this step, used in tier-aware status messages
    depends_on: list[str]  # IDs of steps that must succeed before this one runs. Empty list = no dependencies.
    prompt: str            # written by DECOMPOSER — focused sub-prompt for this step's agent node, derived from engineered_message. ORCHESTRATOR writes this to active_step_prompt on state before dispatch.


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
    client_type: str                # "tui" | "web" (Mk1); more added in Mk3
    assistant_name: str             # per-user, populated by FastAPI from live DB record; client fetches via GET /profile and caches locally
    message_id: str                 # from the client message envelope — forwarded by FastAPI at invocation start. Used by chat.py for all frame building (token, done, error, status, confirm_request, truncate, retract) and by graph nodes that write improvement log events.

    # Conversation
    current_input: str              # the message the user just sent — populated by FastAPI at invocation
    engineered_message: str         # written by PROMPT_ENGINEER — cleaned, expanded version of current_input. All downstream nodes use this instead of current_input as their primary task framing. Zero-initialised to "" by FastAPI.

    # Project context — per-message, never persisted
    active_project: str | None      # read by FastAPI from each message envelope — optional field, None if absent.
                                    # Field present in Mk1 so no state rewiring is needed in Mk2.
                                    # Project-scoped ChromaDB filtering in tools/memory.py is a Mk2 concern —
                                    # always None in Mk1. Zero-initialised to None by FastAPI.

    # Routing
    intent: list[str]               # set by ROUTER — one or more intents. Zero-initialised to [] by FastAPI.
    tier_gate: list[str]            # set by ROUTER — intent names that were tier-gated for this user (e.g. ["code"]).
                                    # ROUTER does not remove these from `intent` — PLANNER plans all steps including blocked ones.
                                    # ORCHESTRATOR pre-blocks any step whose intent appears here before dispatching.
                                    # Zero-initialised to [] by FastAPI. Empty in Mk1.
    detected_skills: list[str]       # skill names identified by ROUTER — PLANNER reads to create one skill Step per entry. Zero-initialised to [] by FastAPI.

    # Output
    active_step_prompt: str | None  # written by ORCHESTRATOR from current_step.prompt before each dispatch — the focused
                                    # sub-prompt DECOMPOSER produced for this step. Agent nodes read this as their primary
                                    # task framing. ORCHESTRATOR clears it after each step. Zero-initialised to None by FastAPI.
    step_response: str              # populated by active agent node — ephemeral per-step scratch field. ORCHESTRATOR reads
                                    # this after each step, saves to step_results, then clears it before the next step.
                                    # Empty by the time RESPONDER runs. Zero-initialised to "" by FastAPI.
    assembled_response: str         # populated by RESPONDER — the final coherent response FastAPI reads to send the done
                                    # frame and to write to conversation history. Always clean markdown — client owns
                                    # rendering. Zero-initialised to "" by FastAPI.

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

    # Constitutional correction (set by chat.py on re-invocation only)
    correction: dict | None         # {clean_prefix, violation, principle} — set by chat.py when CONSTITUTIONAL fires a correction re-invocation. A conditional START edge routes directly to RESPONDER when set. Zero-initialised to None on all normal invocations. Never written by any graph node.
```

**FastAPI is responsible for constructing the full initial state dict before every invocation. All fields are required — node-populated fields are zero-initialised (`""`, `False`, `None`, `[]` as appropriate). No field is ever left absent.**

### PROMPT_ENGINEER
- Model: `models.prompt_engineer` — general model; normalization requires natural language quality, not just classification speed
- Runs before ROUTER — the first node every message touches
- Reads `current_input` only — no history context needed
- Writes `engineered_message`
- What it does: corrects typos and grammar, normalises informal or colloquial vocabulary into phrasing LLMs handle well ("wha i have goin on tmr" → "What do I have going on tomorrow?"), restructures fragmented or incomplete sentences into well-formed prompts. Does not resolve implicit references or add cross-turn context — agent nodes have full `messages` history and handle that themselves.
- Output is always a single message — not a structured object, not a plan
- The user never sees `engineered_message`. `current_input` is stored to history and ChromaDB short-term unchanged. Retrieval queries are always clean because PROMPT_ENGINEER runs before anything else.
- Single model call — the rewrite prompt instructs the model to output the improved message only, no explanation or wrapping
- **Failure handling:** if inference fails or times out, writes `current_input` directly to `engineered_message` (pass-through) and logs at `WARNING` level. Does not set `error` — the rest of the graph continues on the original. A degraded rewrite is never a hard failure.
- Status messages are suppressed for this node by default — the rewrite is invisible to the user. Admin tier sees `"Rewriting message via PROMPT_ENGINEER..."` if `STATUS_MESSAGES["prompt_engineer"]` is set.

### ROUTER
- Model: `mistral:7b`
- Intentionally thin — classify intent, discover skills, check tier. Nothing else.
- Calls `get_history(user_id, limit=config.history_limits.router)` — small window, enough to resolve implicit references in the current message for accurate classification. Does not retrieve from the vault.
- Classifies every input into one or more intents: `memory | tasks | web | conversation` (Mk1). `code`, `system`, and `skill` added in Mk2 when those nodes are built.
- Reads the approved skills registry (personal: `{vault_base}/{user_id}/02-skills/approved/`, shared: `{skills.shared_approved_path}`) — checks whether the directory exists before reading, graceful no-op if absent. Includes skill names and descriptions in the classification prompt so the model can match user intent to a named skill. If a match is found, adds `"skill"` to `intent` and writes matched skill name(s) to `detected_skills` on state. Mk1: no skills exist yet, `detected_skills` always `[]`.
- Checks user tier — if a Standard user's message includes a tier-gated intent, ROUTER leaves `intent` unchanged and appends the gated intent name(s) to `tier_gate` on state. PLANNER plans all steps including blocked ones. ORCHESTRATOR handles blocking at dispatch time. `tier_gate` always `[]` in Mk1.
- Output JSON: `{"intents": ["tasks", "skill"], "detected_skills": ["email_summary"]}` — no memory flag, no context. Memory decisions are each agent node's own responsibility via `tools/memory.py`.
- **Improvement log:** writes a `router_retry` event on retry, `tier_gate_hit` event when a Standard user's intent is gated. See `spec/improvement.md`.
- **ROUTER failure handling:** if the inference call fails or times out, ROUTER retries once. If the retry also fails, sets `error` on state — graph routes immediately to RESPONDER. `tools/llm.py`'s cross-model fallback does not apply to ROUTER since router model and fallback model are the same. A successful retry is logged at `WARNING` level.
- Node-entry status frame sent by FastAPI via `astream_events` if `STATUS_MESSAGES["router"]` is set — ROUTER itself does not send frames

### PLANNER
- Model: `REASONING_MODEL` — dependency inference requires genuine reasoning, not just classification
- Always runs after ROUTER — single-intent messages produce a one-step plan and exit immediately with negligible overhead
- Receives ROUTER's classified intents (`list[str]`) and produces a list of `Step` TypedDicts written to `step_plan` on state — see Supporting TypedDicts above for the full `Step` shape
- Dependency inference is the key responsibility — PLANNER determines which steps are independent and which must wait on others based on semantic reasoning about the user's message
- On PLANNER failure: sets `error` on state — graph routes immediately to RESPONDER per the universal error routing rule
- Node-entry status frame sent by FastAPI if `STATUS_MESSAGES["planner"]` is set

### DECOMPOSER
- Model: `models.decomposer` — general model; crafting focused sub-prompts requires language quality, not heavy reasoning (the hard reasoning was done by PLANNER)
- Runs after PLANNER, before ORCHESTRATOR
- Reads `engineered_message` and `step_plan` from state; writes a `prompt: str` to each `Step` in `step_plan`
- Each sub-prompt is self-contained: the relevant slice of the task, the step's specific intent, and any cross-step context needed to avoid ambiguity. Agent nodes receive only what they need — no noise from unrelated steps.
- ORCHESTRATOR writes `current_step.prompt` to `active_step_prompt` on state before dispatching each step. Agent nodes read `active_step_prompt` as their primary task framing.
- Single-step plans: DECOMPOSER still runs; the sub-prompt is trivially derived from `engineered_message`. Near-instant overhead.
- **Failure handling:** sets `error` on state — graph routes immediately to RESPONDER per the universal error routing rule
- Node-entry status frame sent by FastAPI if `STATUS_MESSAGES["decomposer"]` is set

### `tools/memory.py`

Not a graph node — a shared tool imported and called directly by agent nodes. Memory retrieval decisions are made per-node at runtime, not globally by ROUTER.

**`MemoryResult` dataclass:**
```python
@dataclass
class MemoryResult:
    context: str   # merged retrieved text — empty if nothing relevant found or if retrieval failed
    success: bool  # False = ChromaDB unavailable. True = ChromaDB worked (context may still be empty).
```

**`should_retrieve(history: list[dict], user_id: str, message_id: str) -> bool`**
- Lightweight yes/no LLM call using `models.memory_check` (`mistral:7b`) — a fast always-loaded model dedicated to this binary classification task
- Takes the history the calling node already fetched via `tools/history.py` — does not make its own DB call
- Asks: given this conversation, does answering accurately require looking up stored memories?
- On inference failure: returns `False` (conservative default — proceed without context rather than blocking)

**`retrieve_context(user_id, query, active_project) -> MemoryResult`**
- Always queries both `memory_{user_id}` (personal) and `memory_shared` (family)
- Merges results, deduplicates by chunk ID, takes top-k by score
- Tags memories: `#note #task #fact #code #person #project`
- **`active_project` filtering:** Mk2 concern — ignored in Mk1 (`active_project` is always `None`). When implemented: if set but no chunks tagged with that project name exist, returns unfiltered results — graceful no-op, not an error
- **ChromaDB unavailable:** returns `MemoryResult(context="", success=False)`, calls `notify_admin("chromadb_unavailable", ...)`
- Returns `MemoryResult(context=merged_text, success=True)` on success — `context` may be empty string if nothing relevant found, which is not a failure

**Node usage pattern:**

Every agent node follows this sequence:
1. Call `get_history(user_id, limit=config.history_limits.<node>)` — fetch conversational context
2. Pass that history directly into `should_retrieve(history, user_id, message_id)` — same object, no second fetch
3. If `True`, call `retrieve_context()` for vault context

`should_retrieve` sees exactly the history the node is working with — no more, no less. If `result.success is False`, the node:
- Writes a tier-aware `status_message`: Admin: `"ChromaDB unavailable — continuing without memory context"`, Power: `"Couldn't access your memories — response may lack context"`, Standard: `"I couldn't access my memory for this — my response may be incomplete"`
- Calls `notify_admin("chromadb_unavailable", ...)`
- Continues with empty context

`memory/persist.py` is a separate async background task fired by FastAPI after every successful exchange — unchanged by this design.

### `tools/history.py`

Not a graph node — a shared tool imported and called directly by nodes that need conversational context. History is never pre-loaded into state; nodes opt in by calling this tool.

**`get_history(user_id: str, limit: int) -> list[dict]`**
- Returns the last `limit` turns of conversation history for `user_id`, ordered oldest-first
- Each dict is `{"role": str, "content": str}` — ready to pass directly to Ollama
- Returns an empty list if no history exists — not an error
- **Failure handling:** on DB error, returns an empty list and logs at `WARNING` level — never blocks the calling node

**Limits by node** — configured in `config.yaml` under `history_limits`:

| Node | Default limit | Reason |
|---|---|---|
| ROUTER | 5 | Enough to resolve implicit references for classification — not a dialogue node |
| CONVERSATION | 20 | Dialogue node — needs substantial thread for coherent responses |
| TASKS | 10 | Enough to understand task context without full history |
| MEMORY | 10 | Query context for retrieval and management operations |
| WEB | 5 | Query clarification only |
| CODE | 10 | Enough to understand the coding task in context |

Coordination and formatting nodes (PLANNER, DECOMPOSER, ORCHESTRATOR, RESPONDER) do not call `get_history` — they operate on message structure, not content. PROMPT_ENGINEER does not call `get_history` — it normalises `current_input` as a standalone, context-free operation.

### ORCHESTRATOR
- Executes the `StepPlan` from state reactively — one step at a time, result of each step informs the next
- Each iteration:
  1. Find all steps whose `depends_on` are fully satisfied (all named steps completed successfully)
  2. **Tier-gate check:** if the step's `intent` appears in `state.tier_gate`, immediately write a `StepResult` with `status: "blocked"`, `blocked_by: None`, `reason: "tier_gate:{intent}"` — do not dispatch to the agent node
  3. Write `current_step.prompt` to `active_step_prompt` on state, then dispatch to the appropriate agent node. Agent nodes read `active_step_prompt` as their primary task framing.
  4. After the agent node completes, save `step_response` into `step_results` before looping
  5. Mark the step `success` or `failure` based on whether `error` was set on state
  6. Clear `error`, `step_response`, and `active_step_prompt` on state before the next iteration
- A failed or tier-gated step marks all steps with `depends_on` pointing to it as `blocked` — they are skipped
- Independent steps (no `depends_on` pointing to a failed or tier-gated step) always run regardless of other step outcomes
- Loops until no ready or pending steps remain, then routes to RESPONDER
- **Improvement log:** writes a `planner_divergence` event when fewer steps executed than planned. See `spec/improvement.md`.
- Writes a tier-aware `status_message` before dispatching each step:
  - Admin: `"Step 2/3: Dispatching to TASKS — add_shampoo (no dependencies)"`
  - Power: `"Step 2 of 3: Adding your task..."`
  - Standard: `"Adding your task... (2 of 3)"`
- Node-entry status frame sent by FastAPI if `STATUS_MESSAGES["orchestrator"]` is set

### Graph Flow

```
PROMPT_ENGINEER → ROUTER → PLANNER → DECOMPOSER → ORCHESTRATOR → [agent node] → ORCHESTRATOR → ... → RESPONDER
```

PROMPT_ENGINEER runs first on every message — it rewrites `current_input` into `engineered_message` before ROUTER ever sees it. DECOMPOSER runs after PLANNER and writes a focused sub-prompt to each `Step` — ORCHESTRATOR passes `active_step_prompt` to each agent node at dispatch time. ORCHESTRATOR loops back through agent nodes until the `StepPlan` is exhausted. Agent nodes call `tools/memory.py` internally when they determine retrieval is needed — there is no separate MEMORY_RETRIEVE graph node. The graph ends at RESPONDER — it is always a pure formatter, never an agent node. After the graph completes, FastAPI sends the `done` frame and then fires `memory/persist.py` as an asyncio background task unconditionally after every exchange.

### CONVERSATION
- The default node for general chat — the most-used node for Standard tier users
- Model: `llama3.1:8b`
- Calls `get_history(user_id, limit=config.history_limits.conversation)`, then calls `should_retrieve()` and optionally `retrieve_context()`. Passes history and retrieved context (if any) to Ollama — writes result to `step_response`
- Available to all tiers
- No node-entry status frame by default (`STATUS_MESSAGES["conversation"]` is empty) — tokens stream directly

### MEMORY
- Handles explicit memory queries and management requests — "what do you remember about me?", "forget what I told you about X"
- All ChromaDB operations go through `tools/memory.py` — `retrieve_context()` for retrieval, `delete_memory()` for forget/delete. The MEMORY node calls tools, it does not touch ChromaDB directly.
- All tiers can query, delete, and forget their own memory — it is the user's data
- Delete/forget operations use the interrupt/confirm pattern — node identifies what will be removed, writes it to `interrupt_payload`, user confirms before the ChromaDB delete executes. On cancel, writes a hardcoded cancellation message to `step_response`, no further action taken.
- **Improvement log:** writes a `memory_forget` event when the user confirms a delete. See `spec/improvement.md`.
- On ChromaDB unavailable at any point — including after the user has confirmed a delete — sets `error` on state, calls `notify_admin("chromadb_unavailable", ...)`. The user's confirmation is consumed; they would need to request the delete again once the service is restored.
- No node-entry status frame by default (`STATUS_MESSAGES["memory"]` is empty)

### TASKS
- Manages per-user to-do list and schedule
- Storage: Postgres (user-scoped) via repository pattern — swappable backend
- All operations receive `user_id` — never queries without it
- Operations: create, update, complete, list, delete
- Task status values: `open | closed`
- Task priority values: `low | medium | high`
- Dev backend: SQLite (same interface, selected via `JARVIS_DB_BACKEND` env var)
- No node-entry status frame by default (`STATUS_MESSAGES["tasks"]` is empty) — writes a specific `status_message` immediately before each operation (before insert, before query, before update, before delete) so the message is accurate for both reads and mutations. The message content is tier-aware: Admin sees technical detail (e.g. "Inserting task into `tasks` via SQLiteTaskRepository..."), Power sees operational detail (e.g. "Adding your task..."), Standard sees plain language (e.g. "Adding task...")
- Delete operations use the interrupt/confirm pattern — node identifies the task, writes it to `interrupt_payload`, user confirms before the delete executes. On cancel, writes a hardcoded cancellation message to `step_response`, no further action taken.
- Any operation on a task that no longer exists (update, complete, delete) is treated as a graceful no-op — the node writes a tier-appropriate message to `step_response` (e.g. "That task has already been deleted") rather than raising an error. This handles the race condition where a REST `DELETE /tasks/{id}` call completes while a chat-initiated delete is sitting at the interrupt/confirm gate.

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
- Node-entry status frame sent by FastAPI via `astream_events` if `STATUS_MESSAGES["web"]` is set — WEB itself does not send frames
- Writes specific `status_message` updates mid-execution — the query currently being searched. Content is tier-aware (Admin: `"Querying DuckDuckGo: '{query}'..."`, Power: `"Searching the web for '{query}'..."`, Standard: `"Searching the web..."`)

### SYSTEM
- Shell command execution and file operations: read, write, move, search
- Sandboxed to approved paths (defined in `config.yaml` under `system.allowed_paths`) — enforced by `tools/shell.py`
- Admin and Power tier only
- No node-entry status frame by default (`STATUS_MESSAGES["system"]` is empty) — writes two `status_message` updates per command: one before calling `interrupt()` while composing the shell command ("Composing command..."), one immediately after the user confirms and before the command executes ("Executing..."). Content for both is tier-aware — see execution sequence below.
- **Execution sequence:** (1) SYSTEM writes a `status_message` — "Composing command..." (tier-aware: Admin: `"Translating request into shell command via tools/llm.py..."`, Power: `"Working out the command..."`, Standard: n/a) — then calls Ollama to translate the natural language request into a concrete shell command. This inference is internal and not streamed as `token` frames. (2) SYSTEM writes the command to `interrupt_payload` and calls `interrupt()`. (3) FastAPI sends `confirm_request` frame — client disables input and renders a confirmation prompt (e.g. a popup with confirm/cancel). Pre-interrupt phase is otherwise silent from a `status_message` perspective — the `confirm_request` frame handles all pre-execution communication. (4) If confirmed, SYSTEM writes a `status_message` immediately before execution — "Executing now..." (tier-aware: Admin: `"Executing: '{command}' via tools/shell.py..."`, Power: `"Running command: '{command}'..."`, Standard: n/a) — then the command executes via `tools/shell.py`. If cancelled, SYSTEM writes a hardcoded cancellation message to `step_response` — no further Ollama call.
- **After confirmed execution:** `tools/shell.py` captures stdout and stderr separately. SYSTEM passes both to Ollama to format and summarise into `step_response` — the response includes context about what came from each channel, with tier-appropriate detail (Admin sees which output came from stdout vs stderr; Standard gets a plain language summary of what happened). Four distinct outcomes: (a) stdout and/or stderr present → Ollama formats both into `step_response`; (b) both empty, exit code 0 → hardcoded "Done. `<command>` completed successfully.", no Ollama call; (c) both empty, non-zero exit code → hardcoded "Command failed with exit code N and produced no output."; (d) `tools/shell.py` itself cannot spawn the subprocess → sets `error` on state, which triggers the universal error routing rule. This last case is the only one that sets `error` — command-level failures (including stderr output) always go through `step_response`.
- The client will never receive `token` frames before a `confirm_request` frame from SYSTEM — all token streaming happens after confirmation, or not at all on cancel. `status_message` frames may arrive before the `confirm_request` (the "Composing command..." phase) and after it (the "Executing now..." phase).

### CONSTITUTIONAL
- Runs as a concurrent async task launched by `chat.py` at the moment RESPONDER begins streaming — not a LangGraph node in the graph, but a parallel coroutine
- Monitor only — CONSTITUTIONAL never touches the WebSocket or calls Ollama directly. It detects violations and signals `chat.py`, which owns all correction logic
- Only RESPONDER's token stream is monitored — agent nodes execute silently so there is no intermediate token output to check

**Three objects created by `chat.py` before launching CONSTITUTIONAL, all passed in at launch:**
- `token_queue: asyncio.Queue` — `chat.py` puts each token into this queue immediately after sending it to the client. When RESPONDER's stream ends, `chat.py` puts `None` as a sentinel so CONSTITUTIONAL knows to stop. CONSTITUTIONAL reads with `await token_queue.get()` — sleeps between tokens, no polling.
- `violation_event: asyncio.Event` — CONSTITUTIONAL sets this when a violation is detected. `chat.py` checks `violation_event.is_set()` after each `websocket.send_json` call in the token loop. The check is a single boolean read — nanoseconds — performed at a natural yield point after network I/O.
- `violation_data: dict | None` — CONSTITUTIONAL writes `{token_count, violation, principle}` here before setting the event. `chat.py` reads it when `violation_event.is_set()` is true.

**`chat.py` captures `step_results` mid-stream** — during the original `astream_events` loop, when ORCHESTRATOR's `on_chain_end` event fires, `chat.py` saves the `step_results` from its output. This happens before RESPONDER starts, so the data is always available if a correction is needed.

- Consumes `token_queue` as it fills with RESPONDER's output, evaluating the accumulated buffer against the hardcoded ethics principles using the `constitutional` model from `config.yaml` — a simple binary classification task, not reasoning

**Violation detected mid-stream (truncate path):**
1. CONSTITUTIONAL writes `{token_count, violation, principle}` to `violation_data` and sets `violation_event`
2. `chat.py` detects it after the next token send, breaks out of the original `astream_events` loop (original graph is abandoned, its `assembled_response` is binned)
3. `chat.py` sends a `truncate` frame with `token_count` — client strips back to the first N clean tokens. No status frame between `truncate` and the correction tokens — the correction is seamless and invisible.
4. `chat.py` immediately re-invokes the graph with a new state carrying: the captured `step_results`, all original identity fields, and `correction: {clean_prefix, violation, principle}`. `clean_prefix` is the joined text of the first N clean tokens — RESPONDER uses it to maintain continuity. A conditional START edge routes directly to RESPONDER when `correction` is set.
5. RESPONDER generates a **full corrected response from scratch** — it has complete context and knows what was already shown. `chat.py` counts incoming tokens from the correction run: the first N are accumulated into `assembled_response` but not forwarded to the client (already on screen). Token N+1 onwards are accumulated and forwarded. Client sees a seamless continuation.
6. Correction graph completes: `assembled_response` is the full corrected response. `chat.py` writes history, sends `done`, fires `memory_persist`. Correction graph owns all post-stream responsibilities — the original graph is fully abandoned.

**Violation detected post-stream (retract path)** — violation in the tail of the response, detected after CONSTITUTIONAL sees the `None` sentinel:
1. CONSTITUTIONAL sets `violation_event` with `violation_data`
2. `chat.py` awaits the CONSTITUTIONAL task after sending `done` — the WebSocket stays open for this window
3. If violation found: `chat.py` re-invokes the graph identically to the truncate path (correction state, straight to RESPONDER, full generation), but with `token_count: 0` — all correction tokens are forwarded to the client. `chat.py` sends a `retract` frame with the complete corrected response as `replacement`. History record is updated with the corrected `assembled_response` before `memory_persist` fires.

**No violation detected:** the coroutine completes silently — no frame sent, no latency added on the happy path.

- **Improvement log:** writes a `constitutional_violation` event on every violation (truncate or retract). Clean passes are not logged — no noise. See `spec/improvement.md`.
- The ethics principles are hardcoded in `api/constitutional.py` — not loaded from config or any user-editable source. Changing them requires a code change, by design
- Admin-tier status messages surface the check result (`"Constitutional check: passed"` or `"Constitutional check: violation at token 12 — truncating"`). Power and Standard tiers see nothing — invisible on the happy path, correction is seamless

### SKILLS
- Dispatched to by ORCHESTRATOR when `current_step.intent == "skill"` — handles all user-defined capabilities that are not built-in nodes
- Reads `current_step.skill_name` and looks it up in the skills registry (`skills/approved/` directory). If found, invokes the skill function with the current step description and state as context. If not found, writes a clean "skill unavailable" message to `step_response`.
- Skills are composed of tools (`tools/llm.py`, SMTP, HTTP clients, etc.) and may issue `confirm_request` interrupts before any irreversible action — the same interrupt/confirm pattern used by SYSTEM and CODE. The user can cancel and follow up conversationally; ORCHESTRATOR re-runs the step with the new instruction.
- **Model selection:** SKILLS node uses `models.skills` from `config.yaml` as the default. Individual skills may specify their own model key in their skill definition — if present, that overrides the default. Model names always come from `config.yaml` via `config.py` — never hardcoded inside a skill function.
- Writes output to `step_response` on success, sets `error` on unexpected failure.
- **Phase 3:** stub only — registry is empty, no skills exist yet. Returns a clean "no skills available" message to `step_response`. ROUTER never produces `intent: "skill"` in Phase 3. The node and conditional edge exist so Phase 8 slots in without graph rewiring.
- **Phase 8:** registry populated with approved skills. ROUTER updated to detect skill intents from user messages and set `skill_name` on the matching Step.

### RESPONDER
- **Sole source of `token` frames.** Agent nodes execute silently — no tokens are forwarded to the client during their LLM calls. RESPONDER is the only node whose LLM output streams to the user. `chat.py` filters `on_chat_model_stream` events to `langgraph_node == "responder"` only.
- Always makes an LLM call — single-step and multi-step alike. Consistent behaviour regardless of plan size; no special-casing needed.
- Always produces clean markdown into `assembled_response` — client owns rendering. `client_type` is not used for formatting decisions.
- Checks `error` field on state first — if set, writes a tier-aware clean error message to `assembled_response` instead of a normal response. Tier-aware content: Admin gets full technical detail (component, error class, what failed and where), Power gets operational detail, Standard gets plain English specific to what the user asked for.
- **Tier-gate steps:** in multi-step results, any `StepResult` with `reason` matching `"tier_gate:{intent}"` is assembled using the hardcoded per-capability message for that intent — no inference call. Each message covers: what the capability is, what it does, why it is not granted to Standard tier, and how to request access (referencing `system.admin_contact` from `config.yaml`). Message content is written by the user and stored in `config.yaml` under `tier_gate_messages` — one entry per gated capability (`system`, `code`). Tunable without a code change. The rest of the step results are assembled normally — successful steps report their output, other blocked steps explain what they were waiting on.
- **Single-step:** reads the single `StepResult` from `step_results` and assembles it into `assembled_response` as clean markdown via LLM call.
- **Multi-step:** summarises all steps into a single coherent `assembled_response` — reports what succeeded, what failed, and what was blocked and why. Tier-aware content: Admin gets full detail per step, Standard gets a plain-language summary of the overall outcome.
- Sets `refresh` list on state derived from the intents that executed — RESPONDER is the sole owner of the `refresh` field, no other node writes to it. For multi-step, unions the refresh targets from all successful steps.
- Does not send WebSocket frames — FastAPI reads `assembled_response` and `refresh` from final state and sends the `done` frame
- No node-entry status frame by default (`STATUS_MESSAGES["responder"]` is empty)
