"""
main.py
Entry point for JARVIS.
Initialises the graph and starts the TUI.
For now: runs a simple terminal loop to test the graph before the TUI is built.
"""

from langchain_core.messages import HumanMessage
from graph.graph import jarvis_graph


def main():
    """Simple terminal loop to test the graph before the TUI is built."""

    print("JARVIS online. Type 'exit' to quit.\n")

    messages = []

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() == "exit":
            break

        messages.append(HumanMessage(content=user_input))

        result = jarvis_graph.invoke({"messages": messages})

        messages.append(result["messages"][-1])

        print(f"\nJARVIS: {result['response']}\n")


if __name__ == "__main__":
    main()