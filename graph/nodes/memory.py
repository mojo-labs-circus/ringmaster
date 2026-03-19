"""graph/nodes/memory.py
Retrieves relevant context from ChromaDB based on the user's query.

Sits between the router and responder in the graph. Embeds the user's
message, searches ChromaDB for semantically similar chunks, and injects
the results into state as a context string.

The responder then prepends this context as a SystemMessage so the model
has relevant knowledge available when generating its response."""

from memory.retrieval import retrieve_as_context

def memory_node(state: dict) -> dict:
    """Searches ChromaDB for context relevant to the user's latest message."""

    if not state["messages"]:
        return {"context": ""}

    user_message = state["messages"][-1].content

    print(f"[memory] searching for context...")
    context = retrieve_as_context(user_message)

    if context:
        print(f"[memory] context found — injecting into prompt")
    else:
        print(f"[memory] no relevant context found")

    return {"context": context}