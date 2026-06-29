# ringmaster

> **Archived.** Superseded by [mojo-agent](https://github.com/mojo-labs-circus/mojo-agent).

Ringmaster was R&D for a personal AI hub — a self-hosted server running local models via Ollama (Mistral, Qwen2.5, DeepSeek Coder) with a LangGraph orchestration layer, FastAPI backend, ChromaDB for memory, and a WebSocket chat interface. The idea was a central AI server running on home hardware that multiple people in a household could connect to.

It worked well as a learning exercise and proved out the core architecture: local model routing, persistent memory, multi-user auth, and a structured graph approach to agent orchestration.

The scope eventually grew past what made sense for a single repo, and the design evolved into a cleaner system. The concepts here — local-first, sovereign, persistent context — live on in the [mojo-labs-circus](https://github.com/mojo-labs-circus) stack.
