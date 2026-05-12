# JARVIS — Improvement & Fine-Tuning Log

## Purpose

The improvement log is a persistent, structured record of every event in the system that indicates where JARVIS underperformed or where the model produced output the user rejected. It is entirely separate from the operational log (`jarvis.log`) — different purpose, different audience, different retention policy.

**Operational log** — for debugging live issues. Rotating, bounded, wiped on a schedule.  
**Improvement log** — for accumulating fine-tuning training data over months and years. Never wiped. Every event is a labelled data point.

When the time comes to fine-tune a local model (see `spec/ideas.md` — last-mile fine-tuning), this log is the primary data source. It accumulates a record of what the model got right and wrong, what users rejected, and what violated the ethics principles — all with enough context to construct input/output/label training pairs.

---

## Log File

- **Path:** configured via `logging.improve_log_path` in `config.yaml` — default `~/.jarvis/improve.jsonl`
- **Format:** JSON lines — one JSON object per line, one event per line
- **Retention:** never wiped. The maintenance job explicitly excludes this file. It grows indefinitely and is only cleared by deliberate manual action.
- **Access:** admin only — the file contains user message content

---

## Event Schema

Every event shares a common envelope:

```json
{
  "ts": "2026-04-23T14:32:01Z",
  "event": "<event_type>",
  "user_id": "clarkehines",
  "message_id": "abc123",
  "data": { ... }
}
```

`ts` — ISO 8601 UTC timestamp  
`event` — event type string (see table below)  
`user_id` — who triggered it  
`message_id` — correlates to the original request  
`data` — event-specific payload (see per-event schemas below)

---

## Event Types

| Event | Source | Fine-tuning value | Description |
|---|---|---|---|
| `constitutional_violation` | `api/constitutional.py` | High | Ethics principle violated — explicit label with original content and correction |
| `confirm_cancelled` | `api/routes/chat.py` | High | User reviewed a proposed action and cancelled — explicit rejection of the model's plan |
| `memory_forget` | `graph/nodes/memory.py` | Medium | User asked Jarvis to forget something — signal that persist.py persisted something wrong or stale |
| `persist_decision` | `memory/persist.py` | Medium | Evaluator verdict on whether an exchange was worth persisting — builds picture of memory quality over time |
| `skill_proposed` | skills system (Phase 8) | Medium | Skill proposed by Jarvis, awaiting approval — implicit rejection if never moved to approved/ |
| `router_retry` | `graph/nodes/router.py` | Medium | ROUTER failed first attempt and retried — the input that caused classification difficulty |
| `model_fallback` | `tools/llm.py` | Low-medium | Primary model failed, fell back — which prompts stress the primary model |
| `tier_gate_hit` | `graph/nodes/router.py` | Low | Standard user requested a tier-gated capability — usage pattern signal |
| `planner_divergence` | `graph/nodes/orchestrator.py` | Low-medium | PLANNER produced N steps but fewer executed (blocked/failed) — plan quality signal |

---

## Per-Event Data Schemas

### `constitutional_violation`
```json
{
  "token_count": 45,
  "violation": "suggested the user outsource a decision without thinking it through",
  "principle": "Augment, don't replace",
  "action": "truncate",
  "original_tokens": "...the clean tokens before the violation point...",
  "corrected_continuation": "...what was streamed after correction..."
}
```
`action` is `"truncate"` (mid-stream) or `"retract"` (post-stream).

### `confirm_cancelled`
```json
{
  "node": "system",
  "proposed_action": "rm -rf /tmp/jarvis-scratch",
  "payload_type": "command",
  "original_input": "clean up the jarvis scratch directory"
}
```

### `memory_forget`
```json
{
  "chunk_ids": ["abc", "def"],
  "user_description": "what I told you about my old job"
}
```

### `persist_decision`
```json
{
  "decision": "persist",
  "scope": "personal",
  "exchange_summary": "user mentioned they prefer async Python patterns",
  "vault_path": "clarkehines/00-inbox/2026-04-23-143201.md"
}
```
`decision` is `"persist"` or `"skip"`. `vault_path` is omitted when `decision` is `"skip"`.

### `router_retry`
```json
{
  "input": "can you help me sort out the thing from earlier",
  "first_attempt_result": null,
  "retry_result": "conversation",
  "failure_reason": "timeout"
}
```

### `model_fallback`
```json
{
  "node": "conversation",
  "primary_model": "llama3.1:8b",
  "fallback_model": "mistral:7b",
  "failure_reason": "timeout"
}
```

### `tier_gate_hit`
```json
{
  "blocked_intent": "system",
  "user_tier": "standard",
  "original_input": "can you run a script that backs up my files"
}
```

### `planner_divergence`
```json
{
  "planned_steps": 3,
  "executed_steps": 1,
  "blocked_steps": 2,
  "block_reasons": ["tier_gate:code", "depends_on:step_1_failed"]
}
```

---

## Future Work

### User correction detection
The highest-value fine-tuning signal is a user explicitly correcting Jarvis mid-conversation — "no that's wrong", "you misunderstood", "actually...". These are implicit negative labels on the previous response. Detecting them automatically requires a lightweight classifier watching the start of each user message. When detected, the event would log the original exchange + the correction as a labelled pair.

Not implemented in Phase 3 — the detection classifier adds latency and complexity. Add once the platform is stable and the improve log has enough data to validate the approach.

---

## Building a Fine-Tuning Dataset

The improvement log is not itself a training dataset — it is raw labelled event data. When the time comes to fine-tune (see `spec/ideas.md`), a preprocessing step reads the log, filters by event type and quality threshold, and constructs (input, output, correction) triples in the format required by the fine-tuning tooling (e.g. Unsloth, LLaMA-Factory).

The `constitutional_violation` and `confirm_cancelled` events are the highest-quality signal — they have explicit correct/incorrect labels. The rest are softer signals useful for understanding model behaviour patterns rather than direct training labels.
