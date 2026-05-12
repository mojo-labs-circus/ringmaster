"""scripts/test_node_router.py
Manual output test for the ROUTER node.
Runs against real Ollama — no mocks. Hits the real history DB (returns [] if empty).

Usage:
    python scripts/test_node_router.py             # run predefined cases
    python scripts/test_node_router.py -m "msg"    # run a single custom message
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

from config import ROUTER_MODEL
from graph.nodes.router import router

CASES = [
    "What is the capital of France?",
    "Add buy groceries to my task list",
    "Search the web for the best pizza places nearby and add the top result to my list",
    "What do you remember about my preferences?",
]

SEP = "─" * 60

DEFAULT_USER_ID = "clarkehines"
DEFAULT_TIER = "admin"


def run_case(message: str) -> None:
    state = {
        "engineered_message": message,
        "user_id": DEFAULT_USER_ID,
        "tier": DEFAULT_TIER,
    }
    result = router(state)
    print(f"  Input:  {message}")
    if "error" in result:
        print(f"  Error:  {result['error']}")
    else:
        print(f"  Intent: {result['intent']}")
        print(f"  Skills: {result['detected_skills']}")
        print(f"  Gated:  {result['tier_gate']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--message", help="Run a single custom message")
    args = parser.parse_args()

    print(f"ROUTER — model: {ROUTER_MODEL}  (user: {DEFAULT_USER_ID}, tier: {DEFAULT_TIER})")
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
