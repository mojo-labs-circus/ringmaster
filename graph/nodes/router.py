"""graph/nodes/router.py
Classifies user intent using mistral:7b.
Determines whether the request is 'general' or 'coding'."""

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

router_model = ChatOllama(model="mistral:7b")

def router_node(state: dict) -> dict:
    """Classifies user intent as 'general' or 'coding' using mistral:7b."""
    if not state["messages"]:
        return {"mode": "general"}

    user_message = state["messages"][-1].content

    classification_prompt = f"""You are a classifier. Respond with exactly one word.
If the user's message is about coding, programming, or software, respond: coding
Otherwise respond: general

User message: {user_message}"""

    response = router_model.invoke([HumanMessage(content=classification_prompt)])
    mode = response.content.strip().lower()

    if mode not in ("coding", "general"):
        mode = "general"

    print(f"[router] mode → {mode}")
    return {"mode": mode}