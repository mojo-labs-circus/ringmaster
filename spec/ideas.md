# JARVIS — Ideas Backlog
> Scratchpad for skills ideas and future work. Lives in the repo for now — will migrate to Jarvis's own vault once the server is up.

---

## 🛠️ Skills Backlog

Ideas for skills Jarvis can invoke on request. These are tools, not automatic behaviours — triggered by the user asking, not by Jarvis deciding.

### Collaborative development partner (full lifecycle)
Jarvis walks through development projects from start to finish as a genuine partner — deep interactive planning, architecture decisions, implementation, review, deployment. Not a code generator; a collaborator who ensures the user understands and drives every decision. Applies to personal projects and uni work alike.

**Uni mode** — optional pacing layer for academic projects. Jarvis ensures work progresses at a realistic human pace (not suspiciously fast) and that the user can genuinely explain everything produced. Nothing about hiding AI involvement — just making sure the collaboration is honest and appropriately paced. Uni only; personal projects don't need it.

### Dynamic project planning
Distinct from the tasks system (which is a to-do list) — this is higher-level phase and milestone tracking for ongoing projects. Jarvis understands where a project is, what phase comes next, and adjusts the roadmap as things change. Works for any type of project: a coding project, my mum planning a room redesign, a home renovation, etc. Jarvis acts as a proactive project manager who always knows the current state and what should happen next.

### Feature rollout convention
New features that interact with real-world systems (devices, messages, finances, etc.) should default to admin-only on release. Once stable and tested, promote to power and standard tiers. This gives a safe testing window without exposing unproven features to all users. Apply this pattern consistently across the platform.

### Device control (SSH + power management)
Jarvis can SSH into any device on the network and run commands. Can also power devices off, and power them on via Wake-on-LAN (works over Tailscale with a subnet router — so remote power-on is doable for supported devices). Long-term available to all family members ("Jarvis, turn off the TV"), but admin-only until stable. Confirmation gate required for any destructive or irreversible actions.

### Voice/personality presets (fun mode)
Per-user switchable personality presets for how Jarvis speaks — respond in the style of a specific character or person (Yoda, Jarvis from Iron Man, a comedian, etc.). Purely for fun, late stage development. Part of the voice mode system, not the humaniser (which is about making Jarvis's text output sound like the user — this is about Jarvis's own personality in speech). Requires enough voice/text data on the character to build a convincing style.

### Photos tool
Jarvis can search and retrieve photos from the user's image libraries — iCloud and self-hosted options (Jellyfin, Immich, etc.). Used by other tools: messaging tools can attach a photo to send, document tools can pull an image in, etc. Requires read access to the library; any action beyond retrieval (deleting, sharing) needs a confirmation gate.

### Finance integration
Broad future capability — Jarvis has access to financial data and can reason over it. Specific use cases to be defined as the platform matures (tracking spending, billing people, splitting costs, generating invoices, etc.). Confirmation gate required before any financial action is taken. Research open banking APIs and account aggregation options when the time comes.

### Screen and UI control layer
Open research question — find an open source Cursor-style tool that lets Jarvis interact with whatever is on screen: click, scroll, fill forms, control apps that have no API. This fills the gaps in the life operating layer where API-based tools can't reach. To be researched and implemented once the core platform is stable.

### Confirmation gate pattern
Many of Jarvis's actions have real-world consequences and need user confirmation before proceeding — sending messages, making purchases, deleting things, running commands, etc. Build a single reusable confirmation gate pattern (like Claude Code's approval flow) rather than implementing it ad-hoc per tool. Every tool that touches the outside world should use it.

### Email and messaging tools
Tools for sending emails and texts on the user's behalf. Output goes through the humaniser node so it sounds like the user wrote it. Requires confirmation gate before anything is sent — no silent outbound messages ever. Integration paths: SMTP/IMAP for email, iMessage via Mac or SMS gateway for texts, WhatsApp (via API or open source client library).

### OS and device awareness tool
A tool Jarvis calls when needed — not queried at session start. When someone asks for help with a tech problem, Jarvis calls the tool to get the user's current OS, version, and relevant hardware info, then gives precise device-specific troubleshooting. Long-term: once the screen/shell control layer exists, Jarvis can apply the fix directly rather than walking the user through it. Particularly valuable for less technical family members.

### Style database + humaniser node
Two connected pieces:
1. **Style database** — user uploads writing samples (emails, messages, documents) and Jarvis builds a per-user style profile: vocabulary, sentence structure, tone, cadence. Jarvis actively maintains and refines the profile over time as it sees more of the user's writing — primarily through file uploads rather than prompts (prompts are often full of typos for speed, not representative of real writing style).
2. **Humaniser node** — transforms Jarvis's output into the user's voice using that profile. Runs automatically whenever document-style output is being generated (emails, reports, formal messages), not on regular chat responses. Can also be explicitly requested.

The goal: anything Jarvis writes on the user's behalf sounds like they wrote it themselves.

### Per-user behavioural config file (CLAUDE.md equivalent)
Each user gets a personalised instruction file named after their assistant (e.g. `JARVIS.md`). Jarvis builds and maintains it automatically over time — the user never writes it manually. Captures structured behavioural patterns: "when this user starts a new project, always do X, Y, Z" and "at the end of every session, always do A, B, C". Distinct from personality/style (which is about tone and voice) — this is about workflow preferences and session structure. Gets loaded into context at the start of every session, same way CLAUDE.md works here.

### Session recap
Summarise what happened in a conversation session — decisions made, code written, problems hit, outcomes. Particularly useful for coding sessions. Pulls from conversation history, structures into a clean writeup. If a project is active, optionally saves to vault under `03-projects/<project>/`. Node: SYSTEM or dedicated MEMORY skill.

---

## 🔮 Future Work

### Last-mile fine-tuning
Fine-tune an existing open source model (e.g. a 7B–34B Llama or Qwen variant) on personal data — writing samples, coding patterns, conversation history, notes — to produce a model that genuinely behaves like a personal assistant rather than a generic one shaped by prompting. The home server A6000 (48GB VRAM) is capable of LoRA/QLoRA fine-tuning at this scale. Tools like Unsloth and LLaMA-Factory have made this accessible to individual developers.

The result: a base model that already knows your style, your domain, your preferences, and how you think — before any system prompt is applied. Layered on top of the existing JARVIS memory and skills system, this is the endgame for a truly personal AI. No platform code changes needed — swap the model name in `config.yaml` and the rest of the system works as-is.

Once fine-tuning is working well, the constitutional check shifts from active enforcement to audit layer — the principles are baked into the weights, so CONSTITUTIONAL rarely fires. Its firing history also becomes a useful training signal for the next fine-tuning pass.

Revisit once the home server is live and the platform has accumulated enough personal data to make a fine-tuning dataset meaningful.

Product ideas and infrastructure improvements with no assigned phase. Not tied to any specific implementation task — revisit once the core platform is stable.

### Tailscale ACL groups
Three ACL groups (admin / power / standard) map to the three Jarvis user tiers and give network-level enforcement before requests reach FastAPI. Planned uses:
- SSH access — admin group only
- Database port — admin group only, even on Tailscale
- Maintenance endpoints — Tailscale admin group + app-level admin role as a double gate
- Future services (Gitea, dashboards) — inherit the same group topology automatically
- TUI client — admin/power only at the network layer before auth runs

Defense-in-depth: Tailscale ACL is the outer ring, app-level role checks are the inner ring.

### Admin observability dashboard
Full dashboard — usage metrics, per-user activity, model performance, memory growth over time. Post-base-development addition once the platform has enough runtime data to make it useful. The Phase 9 admin panel is intentionally minimal; this is the grown-up version.

### Life operating layer — service integrations
The long-term goal is for Jarvis to be the operating layer for your entire life. You shouldn't need to open an app to do anything — you just tell Jarvis and it handles it. Example: walking downstairs, say "turn the Masters on in the basement" and it's playing by the time you get there.

This requires two things working together:
1. **API-based tool wrappers** — one tool per service (Jellyfin, Spotify, Home Assistant, calendar, etc.), all living in `tools/`. Jarvis composes these to fulfil requests.
2. **Screen/UI control** — for services that don't have APIs, a cursor/screen-control layer (see separate idea). This fills the gaps.

Applies to everyone on the platform, not just admin. A family member should be able to ask Jarvis to do something without knowing what's running under the hood. Build the tool wrapper pattern early so adding new services is just adding a new file — not a re-architecture.

### External AI escape hatch (highly constrained)
Jarvis is fully local — Ollama is the AI backbone, no data leaves the home network. However, in rare cases (a task genuinely requires a capability the local model can't handle, or a major Claude update makes it temporarily worth it), there should be a tightly contained, opt-in escape hatch to route a single request to an external model.

Hard constraints:
- Explicit user confirmation required before any data leaves the network — no silent cloud calls ever
- Only the minimum necessary data for that specific request is sent — no memory, no history, no profile data unless the user explicitly includes it
- The user is told exactly what is being sent and to where before it goes
- Disabled by default, behind a config flag
- Scoped to a single request only — no persistent external session

This is an emergency valve, not a feature. The north star is always fully local.

### GPU/CPU workload splitting
On the home server, route AI workloads by urgency:
- **GPU** — anything the user is actively waiting on: chat, code generation, real-time reasoning
- **CPU** — background tasks where latency doesn't matter: memory indexing, batch processing, maintenance jobs, storage condensation passes

Keeps interactive response times fast by not letting background work starve the GPU. Implement once the server is up and there's enough load to make scheduling meaningful.

### Active storage condensation (global principle)
Jarvis should actively work to keep all stored data summarised and compressed where possible — this applies at every layer:
- **Memory** — regularly consolidate and merge redundant entries (see Dream mode)
- **Conversation history** — summarise old sessions rather than storing verbatim transcripts indefinitely
- **Mid-conversation context** — as the context window fills during a long session, Jarvis condenses earlier parts of the conversation so the full session context is preserved within the window limit

The goal across all storage is to hit the maximum point where condensation and accuracy meet — maintain the integrity of the data but keep it as compact as possible. Condensed versions always replace the originals in storage; nothing is permanently lost, just distilled.

### Dream mode (memory)
A deeper memory consolidation pass — strengthens important memories, merges redundant entries, surfaces patterns across a user's history. Heavier than the daily pruning pass, intended to run weekly or on demand.

### Centralised token storage via Vaultwarden
Per-client token storage works but silos credentials per device. Future: clients authenticate against Vaultwarden on the server for centralised, consistent tokens across all devices.

### User notifications (`notify_user`)
User-facing async notifications — background task completion, deadline reminders, etc. Delivery via WebSocket push to the active client, ntfy as fallback for offline. Distinct from `notify_admin`.

### TUI interrupt channel (`/btw`)
Secondary input channel for power TUI users — inject a message mid-invocation without cancelling the current one. Opt-in, TUI-only.

### Voice mode in all clients
Phase 10 adds STT/TTS to the TUI. Extending to desktop and iOS clients follows once that architecture is proven.

### Client auto-update
Desktop clients have no auto-update mechanism. Lightweight solution: ping a version endpoint at startup, prompt to re-download if behind. iOS (TestFlight) and web handle updates automatically.

### Custom watch client (microcontroller)
A hardware client built on a microcontroller worn on the wrist — microphone + speaker, speech-only interface. Long-term goal. Use cases are read-only/conversational: "what's on my calendar today", "what tasks do I have", "remind me about X". No code output, no text editing. Connects back to the Jarvis server over Tailscale like any other client. This is the most constrained point in the multi-client family — proves that the API is client-agnostic.

### TUI — evolve into a Claude Code-style power interface
Long-term the TUI becomes a full development and operations environment, not just a chat panel. Two axes:
- **UX/visual** — inline diffs, file tree, split panes, rich output rendering (tables, code blocks, task lists)
- **Agent capability** — Jarvis can read/write files, run shell commands, operate on a codebase directly from within the conversation

Effectively: Claude Code, but it's Jarvis, running against your server, with your memory and task context baked in.

### Multi-client philosophy ("dispatch")
Jarvis is accessible from anywhere via whatever client fits the context — web, TUI, iOS, iPad, watch. There's no separate "dispatch mode"; the multi-client architecture *is* the dispatch layer. Each client exposes a subset of functionality appropriate to its form factor.

### Offline mode (very long term)
Once everything is stable and the family is using Jarvis daily, explore a lightweight offline mode — a self-contained local build that works without the home server (e.g. on a plane). Data syncs back to the server when reconnected. Not worth thinking about until everything else is solid.

### Inline editing for skill confirmation gates
When Jarvis proposes content before sending (email, message, calendar event), the client renders an editable form so the user can tweak the draft directly before confirming. `confirm` frame carries optional `data` with the edited content. Action-type confirmations (shell commands, plans) stay as plain confirm/cancel — no inline editing. Mk1 handles this conversationally (cancel → "I liked that but include X" → Jarvis redrafts → new confirm gate). Inline editing is a client UX improvement for mk2.

### Post-stream correctness watcher
A second concurrent task alongside CONSTITUTIONAL that checks factual correctness of RESPONDER's output after the stream completes — not ethics violations, but factual errors, hallucinations, or claims that contradict the user's known context. Would run post-stream only (retract path) since correctness can only be evaluated on the complete response. Lower priority than ethics checking; only worth adding once the platform is stable and CONSTITUTIONAL is well-validated. Could log to the improve log as a new event type for fine-tuning signal.

### Autonomous self-improvement loop
Jarvis runs overnight as an autonomous agent to improve its own graph behaviour — refining intent descriptions, validating that generated DAGs are correct, and modifying planner prompts where it detects systematic failures. Rather than waiting for a user to notice that routing went wrong, Jarvis observes its own outputs, identifies patterns (e.g. `tasks` intent consistently dropped on conditional requests), proposes and applies fixes, and logs what changed and why.

Key open problems to solve before this is viable:
- **Correctness definition** — what does a "correct DAG" mean formally? The loop needs an evaluator, not just a generator.
- **Scope guardrails** — define exactly which files and prompts Jarvis is allowed to touch unsupervised. Changes outside that scope require user approval.
- **Audit trail** — every self-modification logged with before/after and the reasoning, so the user can review and roll back.

The groundwork is the clean intent description contract being built now — the self-improvement loop automates what is currently manual prompt tuning.

### Multimodal file input
Two distinct use cases:
1. **In-chat attachment** — user attaches a file to a message and Jarvis processes it in context (read, summarise, reason over it). Text and code files first, then images, then audio/video.
2. **Permanent knowledge ingestion** — user uploads a file to be stored in Jarvis's long-term memory/knowledge base, queryable across future sessions.

Both are post-core features. Implement in-chat attachment first (simpler, no storage design needed), then build the ingestion pipeline once the memory layer is solid.
