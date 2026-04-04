"""graph/nodes/responder.py
Generates a response using the model appropriate for the detected mode.
Injects memory context into the prompt if available."""

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage
from config import GENERAL_MODEL, CODING_MODEL

general_model = ChatOllama(model=GENERAL_MODEL)
coding_model = ChatOllama(model=CODING_MODEL)

def responder_node(state: dict) -> dict:
    """Generates a response, incorporating memory context if present."""
    mode = state.get("mode", "general")
    context = state.get("context", "")
    model = coding_model if mode == "coding" else general_model

    messages = list(state["messages"])

    if context:
        messages = [SystemMessage(content=context)] + messages

    response = model.invoke(messages)
    print(f"[responder] using {CODING_MODEL if mode == 'coding' else GENERAL_MODEL}")
    return {"response": response.content}