"""graph/nodes.py
Defines the nodes (processing steps) in the JARVIS LangGraph pipeline.
Each node receives the graph state, does something, and returns updates to that state. """

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage


# Models are defined once at module level so they're reused across calls.
# To swap a model, change the model= string to anything in `ollama list`.
router_model = ChatOllama(model="mistral:7b")
general_model = ChatOllama(model="qwen2.5:14b")
coding_model = ChatOllama(model="deepseek-coder-v2:16b")

def router_node(state: dict) -> dict:
    """Classifies user intent as 'general' or 'coding' using mistral:7b."""

    # Guard against empty message history
    if not state["messages"]:
        return {"mode": "general"}

    user_message = state["messages"][-1].content

    classification_prompt = f"""You are a classifier. Respond with exactly one word.
If the user's message is about coding, programming, or software, respond: coding
Otherwise respond: general

User message: {user_message}"""

    response = router_model.invoke([HumanMessage(content=classification_prompt)])
    mode = response.content.strip().lower()

    # Default to general if mistral returns anything unexpected
    if mode not in ("coding", "general"):
        mode = "general"

    print(f"[router] mode → {mode}")
    return {"mode": mode}

def responder_node(state: dict) -> dict:
    """Generates a response using the model appropriate for the detected mode."""

    mode = state.get("mode", "general")
    model = coding_model if mode == "coding" else general_model

    response = model.invoke(state["messages"])

    print(f"[responder] using {'deepseek' if mode == 'coding' else 'qwen'}")
    return {"response": response.content}




