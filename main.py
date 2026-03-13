"""
main.py
Entry point for JARVIS. Launches the TUI.
"""

from tui.app import JarvisApp

if __name__ == "__main__":
    app = JarvisApp()
    app.run()