"""graph/graph.py
Wires the JARVIS nodes together into a LangGraph graph.
This file defines the flow: START → router → responder → END"""

from langgraph.graph import StateGraph, START, END
from graph.nodes import router_node, responder_node
from typing import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.state import CompiledStateGraph

class JarvisState(TypedDict):
    """The state object that flows through the entire graph."""
    messages: list[BaseMessage]  # full conversation history
    mode: str                    # 'general' or 'coding', set by router
    response: str                # final response, set by responder

def build_graph() -> CompiledStateGraph:
    """Builds and compiles the JARVIS LangGraph graph."""

    # Initialise the graph with our state definition
    graph = StateGraph(JarvisState)

    # Register the nodes
    graph.add_node("router", router_node)
    graph.add_node("responder", responder_node)

    # Define the flow
    graph.add_edge(START, "router")
    graph.add_edge("router", "responder")
    graph.add_edge("responder", END)

    return graph.compile()

# Compile the graph once at module level so it's ready to import anywhere
jarvis_graph = build_graph()