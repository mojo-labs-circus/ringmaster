# JARVIS — Ideas Backlog
> Scratchpad for skills ideas and future work. Lives in the repo for now — will migrate to Jarvis's own vault once the server is up.

---

## 🛠️ Skills Backlog

Ideas for skills Jarvis can invoke on request. These are tools, not automatic behaviours — triggered by the user asking, not by Jarvis deciding.

### Session recap
Summarise what happened in a conversation session — decisions made, code written, problems hit, outcomes. Particularly useful for coding sessions. Pulls from conversation history, structures into a clean writeup. If a project is active, optionally saves to vault under `03-projects/<project>/`. Node: SYSTEM or dedicated MEMORY skill.

---

## 🔮 Future Work

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
