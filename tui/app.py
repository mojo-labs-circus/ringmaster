"""
tui/app.py
The JARVIS terminal user interface built with Textual.
Displays conversation history and handles user input.
"""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
import asyncio
from textual.worker import Worker, get_current_worker
from langchain_core.messages import HumanMessage, AIMessage
from graph.graph import jarvis_graph

class JarvisApp(App):
    """The main JARVIS TUI application."""

    CSS = """
    RichLog {
        height: 1fr;
        border: solid green;
        padding: 1;
    }

    Input {
        dock: bottom;
    }
    """
    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def __init__(self):
        super().__init__()
        self.messages = [] # conversation history passed to the graph

    def compose(self) -> ComposeResult:
        """Defines the layout of the TUI."""
        yield Header()
        yield RichLog(wrap=True, highlight=True, markup=True)
        yield Input(placeholder="Talk to Jarvis...")
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Fires when the user presses enter in the input box."""

        user_input = event.value.strip()

        if not user_input:
            return

        # Clear the input box
        self.query_one(Input).value = ""

        # Display the user's message in the chat log
        log = self.query_one(RichLog)
        log.write(f"[bold cyan]You:[/bold cyan] {user_input}")

        # Add to conversation history
        self.messages.append(HumanMessage(content=user_input))

        # Run the graph in a background thread so the TUI doesn't freeze
        self.run_worker(self.get_response(), exclusive=True)

    async def get_response(self) -> None:
        """Runs the graph in a background thread and displays the response."""

        log = self.query_one(RichLog)
        log.write(f"[bold yellow]JARVIS is thinking... [/bold yellow]")


        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: jarvis_graph.invoke({
                "messages": self.messages,
                "mode": "",
                "context": "",
                "response": ""
            })
        )


        response_text = result["response"]
        self.messages.append(AIMessage(content=response_text))

        # Remove the thinking message and display the response with the model used to search
        model_name = "deepseek-coder-v2" if result.get("mode") == "coding" else "qwen2.5"
        log.write(f"[bold green]JARVIS[/bold green] [dim](via {model_name}):[/dim] {result['response']}\n")

if __name__ == "__main__":
    app = JarvisApp()
    app.run()