"""scripts/test_node_prompt_engineer.py
Manual output test for the PROMPT_ENGINEER node.
Runs against real Ollama — no mocks.

Usage:
    python scripts/test_node_prompt_engineer.py             # run predefined cases
    python scripts/test_node_prompt_engineer.py -m "msg"    # run a single custom message
"""

import argparse
import os
import sys
from pathlib import Path

_root = Path(__file__).parent.parent
_env = _root / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

sys.path.insert(0, str(_root))

from config import PROMPT_ENGINEER_MODEL
from graph.nodes.prompt_engineer import prompt_engineer

CASES = [
    "wanna kno whats the weather gonna be tmrw",
    "add milk eggs and bread to the shopping list",
    "i need help figuring out how to setup my python dev env for this project",
]

SEP = "─" * 60


def run_case(message: str) -> None:
    result = prompt_engineer({"current_input": message})
    print(f"  Input:  {message}")
    print(f"  Output: {result['engineered_message']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--message", help="Run a single custom message")
    args = parser.parse_args()

    print(f"PROMPT_ENGINEER — model: {PROMPT_ENGINEER_MODEL}")
    print(SEP)

    if args.message:
        print()
        run_case(args.message)
        print()
    else:
        for i, msg in enumerate(CASES, 1):
            print(f"\nCase {i} of {len(CASES)}")
            run_case(msg)
        print()


if __name__ == "__main__":
    main()
