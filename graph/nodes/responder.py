"""graph/nodes/responder.py
Generates a response using the model appropriate for the detected mode.
Injects memory context into the prompt if available."""

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

general_model = ChatOllama(model="qwen2.5:14b")
coding_model = ChatOllama(model="deepseek-coder-v2:16b")

def responder_node(state: dict) -> dict:
    """Generates a response, incorporating memory context if present."""
    mode = state.get("mode", "general")
    context = state.get("context", "")
    model = coding_model if mode == "coding" else general_model

    messages = list(state["messages"])

    # If memory retrieved relevant context, prepend it as a system message.
    # System messages set background knowledge without appearing as part of
    # the conversation — the model treats it as things it already knows.
    if context:
        messages = [SystemMessage(content=context)] + messages

    response = model.invoke(messages)

    print(f"[responder] using {'deepseek' if mode == 'coding' else 'qwen'}")
    return {"response": response.content}