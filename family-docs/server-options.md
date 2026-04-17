# JARVIS — Server Options

As we discussed, JARVIS is a private home AI assistant that runs entirely on our own hardware — no subscriptions, no data leaving the house, available to all six of us simultaneously. This document lays out the four hardware configurations I've put together, what each one means in practice, and a recommendation.

The server will sit at home and be accessible to everyone over a private network connection, wherever they are.

You may remember an earlier estimate of around $4,000. That figure was based on a single-user setup. Once the design was expanded to handle six people simultaneously — ensuring that one person's heavy workload never slows down anyone else — the hardware requirements changed significantly. The options below reflect what's actually needed to do that well.


## What Everyone Gets

All four options run the same software and support all six users. The differences are about how well it handles everyone at once, how capable the AI responses are, and how much room there is to grow.

| User | Primary use |
| - | - |
| Clarke | Agentic coding, university work, daily life management |
| Charlie | Fintech analysis, client tracking, light coding |
| Grace | Insurance work, documents, spreadsheets |
| Lilly | PhD research, dissertation writing, long document analysis |
| Mom | Interior design research, creative queries |
| You | Spreadsheets, documents, productivity, Family Admin |


The system is designed so that even a heavy coding session never slows down anyone else asking a question. That separation is built into all four options.


## Why Home Hardware

A comparable subscription service (ChatGPT Plus, Claude Pro, Copilot, etc.) costs roughly $20–30/month per person. For six people that's $1,440–$2,160/year, indefinitely, with data going to third-party servers and usage caps. The trend also shows that these prices will only rise as the companies gain a greater hold on their consumers. The home server pays for itself within a few years and has no ongoing cost beyond electricity (~$15–25/month estimated).


## The Four Options

### Option 1 — Entry Level (~$7,500)

Uses consumer-grade AI chips (the same type found in high-end gaming PCs) and a consumer processor platform. Handles the family's day-to-day workload without issue.

The limitation is longevity: gaming chips aren't designed to run 24 hours a day, 7 days a week without breaks, which is what a home server does. They'll work, but they're not built for it. There's also less room to grow — adding a third AI chip later would require compromises.

**Best for:** Getting a capable system up and running at the lowest cost, accepting that it may need replacing sooner.


### Option 2 — Mid Range (~$13,000) — Recommended

Uses professional-grade AI chips rated for continuous 24/7 operation. The main chip has 48GB of dedicated memory, which allows it to run larger and more capable AI models — meaningfully better responses for complex tasks like coding work and deep research.

The processor is a workstation-class chip with significantly more bandwidth than the consumer platform — this is what allows all six users to be active simultaneously without anyone waiting.

This is the configuration I've been designing against. It hits the right balance between capability, reliability, and cost for what we're actually using it for.

**Best for:** A system built to last, handle everyone comfortably, and run serious workloads without compromise.


### Option 3 — High-A (~$18,800) — Three AI Chips

Same platform as Option 2 but with three AI chips instead of two — the primary chip is also upgraded to a newer generation. The two secondary chips mean the rest of the family each have dedicated hardware that coding sessions can never touch, even in theory. The newer primary chip is also noticeably faster for deeper work like coding and research.

Requires a larger power backup unit due to the three-chip draw.

**Best for:** Maximum headroom and no possibility of any user ever waiting, plus a future-proofed primary chip. Perfect if you genuinely expect all 6 people to be hammering it simultaneously and zero wait time is the priority.


### Option 4 — High-B (~$20,600) — Matched Pair

Same platform as Option 2 but both AI chips are the top-of-the-line newer generation — identical cards, 48GB each. The secondary chip's extra memory means the AI models available to the whole family are larger and more capable. Simpler long-term maintenance since both chips are the same hardware. 

**Best for:** The best possible AI quality for everyone, with a clean and elegant setup.    



## Summary

| Option | Price | Reliability | AI Quality | Handles 6 users | Room to grow |
| - | - | - | - | - | - |
| Entry | ~$7,500 | Consumer grade | Good | Yes | Limited |
| Mid | ~$13,000 | Professional 24/7 | Very good | Comfortably | Yes |
| High-A | ~$18,800 | Professional 24/7 | Excellent | Easily | Already done |
| High-B | ~$20,600 | Professional 24/7 | Best across all users | Easily | Yes |



## Recommendation

**Option 2 (Mid, ~$13,000)** is the right call. The jump from Entry to Mid is the most important one — it's the difference between consumer hardware being asked to do a server's job and hardware that was built for it. Options 3 and 4 are incredible, but the concurrency problem (six people using it at once) is already mostly solved at Mid — the upgrade buys speed, headroom, and meaningfully better AI quality. The high-end chips have more memory, which allows the system to run larger and more capable AI models — better answers, better reasoning, better results for everyone. That's a real benefit, just not a necessity.

If the budget is flexible and the goal is to build it once and not think about it again for a long time, High-B is the cleanest choice. But Mid is the honest recommendation.

