"""scripts/test_node_planner.py
Manual output test for the PLANNER node.
Runs against real Ollama — no mocks.

Usage:
    python scripts/test_node_planner.py             # run predefined cases
    python scripts/test_node_planner.py -m "msg"    # run a single custom message (defaults to conversation intent)
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

from config import PLANNER_MODEL
from graph.nodes.planner import planner

# Each case: (intents, detected_skills, message)
CASES = [
    (["conversation"], [], "What is the capital of France?"),
    (["web", "tasks"], [], "Search for the best pizza places nearby and add the top result to my list"),
    (["tasks"], [], "Add milk, eggs, and bread to my shopping list"),
]

SEP = "─" * 60


def run_case(message: str, intents: list, skills: list) -> None:
    state = {
        "engineered_message": message,
        "intent": intents,
        "detected_skills": skills,
    }
    result = planner(state)
    print(f"  Message: {message}")
    print(f"  Intents: {intents}")
    if "error" in result:
        print(f"  Error:   {result['error']}")
    else:
        steps = result["step_plan"]
        print(f"  Steps ({len(steps)}):")
        for step in steps:
            deps = step["depends_on"] if step["depends_on"] else ["none"]
            print(f"    [{step['id']}] ({step['intent']}) {step['description']}")
            print(f"          depends_on: {deps}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--message", help="Run a single custom message (uses intent=[conversation])")
    args = parser.parse_args()

    print(f"PLANNER — model: {PLANNER_MODEL}")
    print(SEP)

    if args.message:
        print()
        print("  Note: using intent=[conversation] — run test_graph_flow.py to get real intents from ROUTER")
        run_case(args.message, ["conversation"], [])
        print()
    else:
        for i, (intents, skills, msg) in enumerate(CASES, 1):
            print(f"\nCase {i} of {len(CASES)}")
            run_case(msg, intents, skills)
        print()


if __name__ == "__main__":
    main()
