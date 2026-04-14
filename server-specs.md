# JARVIS Server Specification

Planning document for the home server build (summer 2026). Companion to `jarvis-spec.md` — hardware and infrastructure detail lives here, keeping the spec focused on software architecture.

---

## Overview

The JARVIS server is the backbone of the platform — a single home server running the full stack (FastAPI, Ollama, Postgres, ChromaDB, Caddy) accessible to all family members over Tailscale. No cloud, no external APIs. All compute, storage, and inference is local.

**Goal:** Seamless AI assistant experience for all 6 users simultaneously, across two timezones, with no perceptible degradation when multiple people are active at once.

---

## Users & Usage Profiles

| User | Tier | Location | Workload | Inference tier |
|---|---|---|---|---|
| clarkehines | Admin | UK | Heavy agentic coding, uni work, running daily life through JARVIS | Primary + Secondary |
| brother | Power | UK | Fintech analysis, light coding (client tracking systems etc.) | Primary (occasional) + Secondary |
| sister 1 | Standard | UK | Insurance work, documents, spreadsheets | Secondary only |
| sister 2 | Standard | UK | PhD research, dissertation writing, long document analysis | Secondary only |
| mum | Standard | US | Interior design research, creative queries | Secondary only |
| dad | Standard | US | Spreadsheets, documents, productivity | Secondary only |

### Timezone split

UK siblings (clarkehines, brother, sister 1, sister 2) and US parents (mum, dad) operate on different schedules. Meaningful overlap is roughly **2pm–10pm GMT** — US afternoon, UK evening. Outside this window the active user count roughly halves. True simultaneous 6-user load is rare in practice.

---

## GPU Architecture

### The problem

All Ollama inference runs on shared hardware. Without a deliberate split, a long agentic coding session (30–60s per agent call) blocks every other user's request for its duration — a Standard user asking a simple question could wait minutes.

### The solution — model-based GPU routing

Two Ollama instances, each bound to a different GPU. `tools/llm.py` routes each call to the correct instance based on the model name requested. No tier logic needed — the model encodes the workload type.

**Primary GPU — reasoning and coding models:**
- PLANNER node (open question — see Model Assignments)
- CODE node
- Coding team sub-agents

**Secondary GPU — all lightweight models:**
- ROUTER
- CONVERSATION, TASKS, MEMORY, WEB, SYSTEM, RESPONDER
- PLANNER (if a capable mid-tier model proves sufficient — see Model Assignments)

Standard tier users hit the secondary card only. Admin/Power users hit the primary only when doing reasoning or coding work.

### Why this eliminates the bottleneck

Long agentic coding sessions are physically isolated to the primary card. Standard users' requests run independently on the secondary card regardless of what is happening on the primary. The two cards never contend.

### Routing config (`config.yaml`)

```yaml
ollama_url_primary: "http://localhost:11434"   # reasoning + coding models
ollama_url_secondary: "http://localhost:11435"  # lightweight models
```

`tools/llm.py` maps model name → Ollama instance at call time.

---

## Inference Hardware

### Primary GPU — TBD

*To be confirmed once full server plan is reviewed.*

**Requirements:**
- 16GB+ VRAM to fit large reasoning and coding models
- Strong CUDA compute for sustained agentic coding sessions

### Secondary GPU — NVIDIA RTX 3090

| Spec | Value |
|---|---|
| VRAM | 24GB GDDR6X |
| Approx cost (used) | ~$450 |

**Why the 3090:**
- 24GB means all lightweight models stay loaded simultaneously — no swap delays between user requests
- Handles 3–4 concurrent users smoothly, covering the realistic overlap window
- Sister 2's PhD workload (long document analysis, dissertation writing) means sustained secondary card usage — 24GB gives headroom for long contexts without evicting other models
- `OLLAMA_NUM_PARALLEL` headroom if monitoring shows it is needed — see Future Considerations
- Cost spread across 6 users replacing commercial AI subscriptions pays back quickly

---

## Model Assignments

Model selection is not finalised — this section captures the constraints and open questions.

### Key open question — PLANNER card

PLANNER runs on **every single request** from every user. If it lives on the primary card, Standard users queue against Admin's coding sessions on every message they send — defeating the purpose of the split. The goal is to find a model capable enough for multi-step dependency inference that can live on the secondary card, so Standard users never touch the primary card at all.

- **If a capable mid-tier model suffices for PLANNER:** put it on the secondary card — Standard users never touch primary. Clean.
- **If PLANNER genuinely needs the full reasoning model:** it stays on primary, but inference is short (one-step plans finish fast) so the queue impact is minimal compared to CODE.

This is the most important model decision in the system.

### Assignment table

| Node | Card | Model | Notes |
|---|---|---|---|
| ROUTER | Secondary | TBD — small, fast | Classification only — speed over capability |
| PLANNER | TBD | TBD — mid-tier reasoning | Key open question above |
| CONVERSATION | Secondary | TBD | Good general chat quality |
| TASKS | Secondary | TBD | Instruction following |
| MEMORY | Secondary | TBD | General |
| WEB | Secondary | TBD | General |
| SYSTEM | Secondary | TBD | General |
| RESPONDER | Secondary | TBD | General |
| CODE | Primary | TBD — best coding model that fits in primary VRAM | Largest model on the system |

### Secondary card VRAM budget (24GB)

All secondary models should fit simultaneously in 24GB to keep all of them resident and avoid load delays. Model sizes at Q4 quantization are approximate:

| Model slot | Approx VRAM (Q4) |
|---|---|
| ROUTER | ~2–4GB |
| PLANNER (if secondary) | ~4–8GB |
| CONVERSATION / shared lightweight | ~4–5GB |
| Buffer for `OLLAMA_NUM_PARALLEL` | ~5GB |

---

## Storage

*Architecture confirmed — hardware TBD once server plan is reviewed.*

All persistent data on ZFS, auto-snapshotted.

```
/tank/docker/jarvis/
├── postgres/           # User data, tasks, history, auth tables
├── chromadb/           # Per-user and shared memory collections
├── vaults/             # Obsidian vaults — per-user + shared family vault
│   ├── shared/
│   ├── clarkehines/
│   ├── brother/
│   ├── sister1/
│   ├── sister2/
│   ├── mum/
│   └── dad/
└── logs/
```

---

## Network

- **Tailscale** — all client connections. Nothing exposed to the open internet.
- **Caddy** — reverse proxy, TLS, routes `jarvis.home` to FastAPI and web client
- **Internal Docker network** — FastAPI, Ollama (×2), Postgres, ChromaDB communicate internally. Only FastAPI and Caddy are externally reachable.

---

## Full Hardware BOM

*Partially confirmed — to be completed once server plan is reviewed.*

| Component | Spec | Status | Notes |
|---|---|---|---|
| Primary GPU | TBD | TBD | 16GB+ VRAM, reasoning + coding |
| Secondary GPU | NVIDIA RTX 3090 (used) | Decided | 24GB, lightweight inference |
| ... | TBD | TBD | |

---

## Future Considerations

### `OLLAMA_NUM_PARALLEL` on secondary card
If monitoring shows concurrent users queuing on the secondary card, enable `OLLAMA_NUM_PARALLEL=2` (or higher). With 24GB VRAM and small models, multiple concurrent generations are viable. Only configure once real usage data justifies it — premature tuning is not worth the complexity.

### Third GPU / second primary card
If Admin and Power tier are both running heavy agentic sessions simultaneously and contention becomes a real problem, a second high-VRAM card for the primary workload is the logical next step. Not anticipated as necessary given brother's infrequent heavy usage — but the architecture supports it cleanly since routing lives entirely in `tools/llm.py`.
