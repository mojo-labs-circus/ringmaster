"""graph/state.py
Defines the state object that flows through the entire JARVIS graph.

Every node receives this state, does its work, and returns a dict
containing only the fields it wants to update.

FastAPI constructs the full initial state before every invocation —
all fields are required. Node-populated fields are zero-initialised
("", False, None, [] as appropriate) so nodes can always assume the
field exists."""

from typing import TypedDict


class JarvisState(TypedDict):
    # Identity — populated by FastAPI before invocation
    user_id: str          # always present, never None — hardcoded to "clarkehines" in dev
    tier: str             # "admin" | "power" | "standard" — from live DB record
    client_type: str      # "tui" | "web" | "mobile"
    assistant_name: str   # per-user, from live DB record

    # Conversation
    messages: list[dict]  # history from repository + current_input appended by FastAPI.
                          # Each dict is {"role": str, "content": str} — passed directly to Ollama.
    current_input: str    # the message the user just sent

    # Project context — session-level only, never persisted
    active_project: str | None  # set by client at session start, None if no project selected.
                                # Controls project-scoped vault reads and ChromaDB filtering.
                                # Unrecognised values passed through — MEMORY_RETRIEVE handles
                                # missing project gracefully. Zero-initialised to None by FastAPI.

    # Routing — zero-initialised by FastAPI
    intent: str           # set by ROUTER — "memory" | "tasks" | "code" | "web" | "system" | "conversation"
    needs_memory: bool    # set by ROUTER — controls whether MEMORY_RETRIEVE is invoked

    # Context — zero-initialised to "" by FastAPI
    retrieved_context: str  # populated by MEMORY_RETRIEVE if invoked
    skill_context: str      # populated by ROUTER skills check

    # Output — zero-initialised to "" by FastAPI
    response: str           # populated by active agent node — read by RESPONDER only
    formatted_response: str  # populated by RESPONDER — read by FastAPI to send done frame

    # Status — zero-initialised to None by FastAPI
    status_message: str | None  # written by nodes mid-execution — FastAPI fires status frame on change

    # Error handling — zero-initialised to None by FastAPI
    error: str | None     # set by any node on expected failure, checked by RESPONDER

    # Interrupt / confirm — zero-initialised to None by FastAPI
    interrupt_payload: dict | None  # written by node before interrupt() — FastAPI builds confirm_request frame

    # Refresh signals — zero-initialised to [] by FastAPI
    refresh: list[str]    # populated by RESPONDER only — FastAPI reads to build done frame
