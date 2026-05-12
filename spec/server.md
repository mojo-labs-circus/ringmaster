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

> GPU specifications for the Mid tier baseline. The High tiers use the RTX 6000 Ada (48GB, Lovelace) as the primary — same VRAM, newer architecture, better inference throughput. See [Build Tiers](#build-tiers) for full per-tier hardware.

### Primary GPU — NVIDIA RTX A6000 (48GB)

| Spec | Value |
|---|---|
| VRAM | 48GB GDDR6 |
| Architecture | Ampere |

**Why the A6000:**
- 48GB VRAM fits 70B-class models at Q4 quantisation (~38–40GB) — unlocks Qwen2.5-Coder 72B for the CODE node
- Professional card rated for sustained 24/7 workloads — no gaming-driver instability
- Resolves the PLANNER card question: enough headroom to host PLANNER alongside CODE at a smaller model size if needed (see VRAM Strategies)

### Secondary GPU — NVIDIA RTX A5000 (24GB)

| Spec | Value |
|---|---|
| VRAM | 24GB GDDR6 |
| Architecture | Ampere |

**Why the A5000:**
- Professional card — rated for sustained loads, no power throttling, better driver stability than consumer 3090
- 24GB fits all lightweight models simultaneously with headroom for `OLLAMA_NUM_PARALLEL`
- At 24GB, can host a 32B PLANNER (~18–20GB Q4) if that strategy is chosen (see VRAM Strategies)

---

## Model Assignments

Model selection is not finalised — this section captures the constraints and open questions.

### VRAM Strategies

The A6000 (48GB) and A5000 (24GB) open up two viable strategies. The core tension is **biggest possible CODE model** vs **strongest independent PLANNER**.

---

**Strategy A — Maximum coding power**

| Card | Model | Approx VRAM (Q4) |
|---|---|---|
| Primary (A6000) | CODE: Qwen2.5-Coder 72B | ~40GB |
| Primary (A6000) | (8GB headroom — PLANNER cannot fit) | — |
| Secondary (A5000) | PLANNER: 32B reasoning model | ~20GB |
| Secondary (A5000) | Shared lightweight (ROUTER, CONVERSATION, TASKS, etc.): 7–8B | ~5GB |
| Secondary (A5000) | Buffer | ~−1GB (tight) |

Trade-off: best possible coding model, but PLANNER shares the secondary card with all lightweight nodes. Secondary card becomes the bottleneck under concurrent Standard user load — every request hits it (PLANNER) and Standard users also hit it for conversation etc.

---

**Strategy B — Strong independent PLANNER, capable coding**

| Card | Model | Approx VRAM (Q4) |
|---|---|---|
| Primary (A6000) | CODE: 34B coding model (e.g. Qwen2.5-Coder 32B) | ~20GB |
| Primary (A6000) | PLANNER: 32B reasoning model | ~20GB |
| Secondary (A5000) | ROUTER: 3B | ~2GB |
| Secondary (A5000) | CONVERSATION / shared lightweight: 14B | ~8GB |
| Secondary (A5000) | TASKS, MEMORY, WEB, SYSTEM, RESPONDER: shared with CONVERSATION | — |
| Secondary (A5000) | Buffer for `OLLAMA_NUM_PARALLEL` | ~14GB remaining |

Trade-off: secondary card is entirely free for Standard users — they never touch primary. PLANNER is a proper 32B reasoning model. CODE drops from 72B to 32B, which is still excellent.

---

**Recommendation**

Strategy B is architecturally cleaner and matches the original GPU split intent. A 32B coding model is strong enough for most tasks; the cases where 72B would genuinely outperform it are narrow. The real win is Standard users never contending with Admin's sessions on either card. Revisit Strategy A if the 32B CODE model proves insufficient in practice.

---

### Assignment table (Strategy B baseline)

| Node | Card | Model | Notes |
|---|---|---|---|
| ROUTER | Secondary | TBD — 3B, fast | Classification only — speed over capability |
| PLANNER | Primary | TBD — 32B reasoning | Fits alongside 32B CODE in 48GB |
| CONVERSATION | Secondary | TBD — 14B shared | Shared model for all lightweight nodes |
| TASKS | Secondary | Shared with CONVERSATION | |
| MEMORY | Secondary | Shared with CONVERSATION | |
| WEB | Secondary | Shared with CONVERSATION | |
| SYSTEM | Secondary | Shared with CONVERSATION | |
| RESPONDER | Secondary | Shared with CONVERSATION | |
| CODE | Primary | TBD — 32B coding model (e.g. Qwen2.5-Coder 32B) | Step up to 72B under Strategy A |

---

## Platform Decision

### WRX90 (Threadripper PRO) vs TRX50 (Consumer Threadripper)

The CPU platform is the most consequential upstream decision — it determines PCIe headroom, memory type, and sourcing difficulty.

| | WRX90 PRO | TRX50 Consumer |
|---|---|---|
| Example CPU | Threadripper PRO 7945WX | Threadripper 7900 |
| PCIe 5.0 lanes (CPU) | 88 | 48 |
| 3 GPUs at x16 | Yes — 40 lanes spare | No — forces GPUs to x8 |
| ECC RDIMM support | Yes | No |
| Retail availability | OEM-primary — specialist resellers or secondary market | Newegg, Amazon, Micro Center |
| Platform cost vs TRX50 | ~+$1,500 | Baseline |

**PCIe note:** PCIe 5.0 x8 equals PCIe 4.0 x16 in bandwidth. The professional A-series cards are PCIe 4.0 — running them in x8 slots causes no real-world inference performance loss. The concern is architectural headroom: on TRX50 you are designing around a constraint rather than having room to grow.

**ECC note:** ECC silently corrects single-bit memory errors. For a home AI assistant the consequence of a non-ECC error is a garbled response or a restart — not silent data corruption with serious consequences. ECC is a meaningful benefit but not a strict requirement for this use case.

**Which tier uses which:** Entry uses TRX50 — cost is the priority and a third GPU is not planned. Mid and High use WRX90 — the PCIe headroom justifies the premium given a third GPU is a realistic future addition.

---

## OS & Software Stack

### Operating System

Ubuntu Server 24.04 LTS. Minimal install, no GUI. Chosen for first-party NVIDIA driver and CUDA support, 5-year LTS lifecycle, and broad industry adoption.

### Host-Level Dependencies

These are installed directly on the host OS — not containerised.

| Package | Purpose |
|---|---|
| NVIDIA drivers + CUDA | GPU compute — NVIDIA publishes official `.deb` packages targeting Ubuntu directly |
| `nvidia-container-toolkit` | Allows Docker containers to access the GPUs |
| OpenZFS (`zfsutils-linux`) | Storage layer — must run on the host |
| Docker + Docker Compose | Container runtime for all services |
| Tailscale | Private network layer — installed on the host so all containers share the same tunnel |

### ZFS Pool

- **Pool name:** `tank`
- **Config:** RAIDZ2 across 4× Seagate IronWolf 12TB — ~24TB usable
- **Mount root:** `/tank/`
- Auto-snapshots via `zfs-auto-snapshot` or equivalent

### Containerised Services

All services run in Docker containers on an internal bridge network. Only FastAPI and Caddy are reachable from outside that network.

| Service | Purpose | Notes |
|---|---|---|
| Ollama (primary) | Inference — CODE and PLANNER nodes | Bound to primary GPU via `CUDA_VISIBLE_DEVICES=0`, port 11434 |
| Ollama (secondary) | Inference — all lightweight nodes | Bound to secondary GPU via `CUDA_VISIBLE_DEVICES=1`, port 11435 |
| PostgreSQL | User data, tasks, conversation history, auth | |
| ChromaDB | Per-user and shared vector memory collections | |
| Caddy | Reverse proxy, TLS termination | Routes `jarvis.home` to FastAPI |
| JARVIS (FastAPI) | Application server | |
| ntfy | Push notifications | |
| Gitea | Self-hosted git | |
| Prometheus | Metrics collection and storage | Scrapes all exporters |
| Grafana | Dashboard and visualisation | Accessible at `grafana.jarvis.home` over Tailscale, port 3000 |
| node_exporter | Host metrics | CPU, RAM, disk, network |
| DCGM Exporter | GPU metrics | Per-GPU VRAM usage, utilisation, temperature, power draw |
| cAdvisor | Container metrics | Per-container CPU, RAM, network |
| Loki | Log aggregation | Stores logs from all containers |
| Promtail | Log shipping | Collects container logs and forwards to Loki |

---

## Monitoring

Full observability stack running alongside the main services. All dashboards are accessible over Tailscale at `grafana.jarvis.home` — available from any family device on the network.

### What Gets Monitored

| Layer | Tool | Key metrics |
|---|---|---|
| Host | node_exporter | CPU, RAM, disk I/O, network throughput |
| GPUs | DCGM Exporter | VRAM usage, GPU utilisation, temperature, power draw per card |
| Containers | cAdvisor | Per-container CPU, RAM, network |
| Logs | Loki + Promtail | All container logs — searchable in Grafana alongside metrics |

### Grafana Dashboards

Start with community and vendor-provided dashboards:
- NVIDIA provides a pre-built DCGM dashboard — GPU health at a glance
- node_exporter and cAdvisor both have well-maintained community dashboards on grafana.com

Custom admin dashboard (lower priority) — will eventually surface key JARVIS-specific views: active users, inference queue depth per GPU, per-node latency, and memory collection sizes. Built on top of the same Prometheus and Loki data sources.

---

## Storage

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

## Build Tiers

All tiers share the same storage layout, network stack, case, cooler, and boot drive. Only the compute platform and GPUs differ. Prices are USD estimates as of April 2026 and should be verified before purchasing — GPU secondary market prices in particular fluctuate.

| Tier | Primary GPU | Secondary GPU(s) | Platform | Est. Total |
|---|---|---|---|---|
| Entry | RTX 4090 24GB | RTX 3090 24GB | TRX50 consumer | ~$7,500 |
| Mid | RTX A6000 48GB (Ampere) | RTX A5000 24GB (Ampere) | WRX90 PRO | ~$13,000 |
| High-A | RTX 6000 Ada 48GB | 2× RTX A5000 24GB (Ampere) | WRX90 PRO | ~$18,800 |
| High-B | RTX 6000 Ada 48GB | RTX 6000 Ada 48GB | WRX90 PRO | ~$20,600 |

---

### Entry (~$7,500)

Consumer Threadripper platform. Two consumer GPUs. No ECC. Covers the workload as it stands today with no third-GPU headroom.

| Component | Spec | Est. Price |
|---|---|---|
| CPU | AMD Threadripper 7900 (TRX50) | ~$700 |
| Motherboard | ASUS Pro WS TRX50-SAGE WIFI | ~$650 |
| Memory | 128GB DDR5 (non-ECC) | ~$250 |
| Primary GPU | NVIDIA RTX 4090 24GB | ~$2,000 |
| Secondary GPU | NVIDIA RTX 3090 24GB | ~$800 |
| Boot Drive | Samsung 990 Pro 1TB NVMe | ~$140 |
| Storage | 4× Seagate IronWolf 12TB | ~$900 |
| Case | Fractal Define 7 XL | ~$250 |
| PSU | Corsair HX1200 (1200W) | ~$250 |
| Cooling | Noctua NH-U14S TR5-SP6 | ~$150 |
| UPS | CyberPower CP2200PFCLCD | ~$400 |
| **Total** | | **~$7,490** |

**Tradeoffs:** Both GPUs are 24GB — primary can run a 32B model but with no headroom for growth. Consumer cards are not rated for sustained 24/7 operation. TRX50 limits a future third GPU to x8 slots (no real throughput loss at PCIe 4.0 speeds, but a design constraint). CPU and RAM are available off-the-shelf from standard retailers.

---

### Mid (~$13,000) — Recommended

Professional Ampere cards on the WRX90 PRO platform. 48GB primary fits large models comfortably. ECC memory. Rated for continuous 24/7 operation. Clean headroom for a third GPU later.

| Component | Spec | Est. Price |
|---|---|---|
| CPU | AMD Threadripper PRO 7945WX (WRX90) | ~$1,200 |
| Motherboard | ASUS Pro WS WRX90E-SAGE SE | ~$1,290 |
| Memory | 128GB ECC DDR5 RDIMM | ~$600 |
| Primary GPU | NVIDIA RTX A6000 48GB (Ampere) | ~$4,650 |
| Secondary GPU | NVIDIA RTX A5000 24GB (Ampere) | ~$2,800 |
| Boot Drive | Samsung 990 Pro 1TB NVMe | ~$140 |
| Storage | 4× Seagate IronWolf 12TB | ~$900 |
| Case | Fractal Define 7 XL | ~$250 |
| PSU | Corsair AX1600i (1600W) | ~$650 |
| Cooling | Noctua NH-U14S TR5-SP6 | ~$150 |
| UPS | CyberPower CP2200PFCLCD | ~$400 |
| **Total** | | **~$13,030** |

**Tradeoffs:** Professional cards command a significant premium over consumer equivalents but are the correct choice for a machine running 24/7 indefinitely. The 7945WX is not available at standard retail — requires a specialist reseller or the secondary market (see Platform Decision). WRX90 leaves clean PCIe headroom for a third GPU later.

---

### High-A (~$18,800) — Three GPUs from day one

Same CPU and platform as Mid. Ada-generation primary card. Two secondary cards — Standard users are split across dedicated hardware, eliminating any queueing under full 6-user load. Requires a larger UPS due to three-card power draw.

| Component | Spec | Est. Price |
|---|---|---|
| CPU | AMD Threadripper PRO 7945WX (WRX90) | ~$1,200 |
| Motherboard | ASUS Pro WS WRX90E-SAGE SE | ~$1,290 |
| Memory | 128GB ECC DDR5 RDIMM | ~$600 |
| Primary GPU | NVIDIA RTX 6000 Ada 48GB | ~$7,500 |
| Secondary GPU 1 | NVIDIA RTX A5000 24GB (Ampere) | ~$2,800 |
| Secondary GPU 2 | NVIDIA RTX A5000 24GB (Ampere) | ~$2,800 |
| Boot Drive | Samsung 990 Pro 1TB NVMe | ~$140 |
| Storage | 4× Seagate IronWolf 12TB | ~$900 |
| Case | Fractal Define 7 XL | ~$250 |
| PSU | Corsair AX1600i (1600W) | ~$650 |
| Cooling | Noctua NH-U14S TR5-SP6 | ~$150 |
| UPS | CyberPower CP3000PFCLCD (3000VA/1800W) | ~$550 |
| **Total** | | **~$18,830** |

**Tradeoffs:** Three-GPU power draw (~1,230W system, ~1,370W wall) exceeds the CP2200PFCLCD's 1320W rating — the larger CP3000PFCLCD UPS is required. The routing layer in `tools/llm.py` needs extending to support three Ollama instances. Ada primary provides a meaningful inference speed improvement over Ampere at equivalent VRAM.

---

### High-B (~$20,600) — Matched Ada pair

Same CPU and platform as Mid. Both GPUs are RTX 6000 Ada — identical cards, 48GB VRAM on both, maximum headroom for secondary models, simpler long-term maintenance.

| Component | Spec | Est. Price |
|---|---|---|
| CPU | AMD Threadripper PRO 7945WX (WRX90) | ~$1,200 |
| Motherboard | ASUS Pro WS WRX90E-SAGE SE | ~$1,290 |
| Memory | 128GB ECC DDR5 RDIMM | ~$600 |
| Primary GPU | NVIDIA RTX 6000 Ada 48GB | ~$7,500 |
| Secondary GPU | NVIDIA RTX 6000 Ada 48GB | ~$7,500 |
| Boot Drive | Samsung 990 Pro 1TB NVMe | ~$140 |
| Storage | 4× Seagate IronWolf 12TB | ~$900 |
| Case | Fractal Define 7 XL | ~$250 |
| PSU | Corsair AX1600i (1600W) | ~$650 |
| Cooling | Noctua NH-U14S TR5-SP6 | ~$150 |
| UPS | CyberPower CP2200PFCLCD | ~$400 |
| **Total** | | **~$20,580** |

**Tradeoffs:** Most expensive option. The secondary card's 48GB VRAM allows larger models for Standard users — a full 32B secondary model with significant headroom for `OLLAMA_NUM_PARALLEL`. Matched cards simplify driver management and future maintenance. Two-card power draw (~1,070W system, ~1,190W wall) stays within the CP2200PFCLCD envelope.

---

## Future Considerations

### `OLLAMA_NUM_PARALLEL` on secondary card
If monitoring shows concurrent users queuing on the secondary card, enable `OLLAMA_NUM_PARALLEL=2` (or higher). With 24GB VRAM and small models, multiple concurrent generations are viable. Only configure once real usage data justifies it — premature tuning is not worth the complexity.

### Third GPU / second primary card
If Admin and Power tier are both running heavy agentic sessions simultaneously and contention becomes a real problem, a second high-VRAM card for the primary workload is the logical next step. Not anticipated as necessary given brother's infrequent heavy usage — but the architecture supports it cleanly since routing lives entirely in `tools/llm.py`.
