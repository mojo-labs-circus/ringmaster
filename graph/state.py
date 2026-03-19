"""graph/state.py
Defines the state object that flows through the entire JARVIS graph.

Every node receives this state, does its work, and returns a dict
containing only the fields it wants to update."""

from typing import TypedDict
from langchain_core.messages import BaseMessage

class JarvisState(TypedDict):
    """The state object that flows through the entire graph."""
    messages: list[BaseMessage]  # full conversation history
    mode: str                    # 'general' or 'coding', set by router
    context: str                 # relevant vault chunks, injected by memory node
    response: str                # final response, set by responder