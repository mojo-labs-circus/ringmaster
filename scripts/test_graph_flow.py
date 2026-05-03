"""scripts/test_graph_flow.py
Manual end-to-end flow test — threads a message through PROMPT_ENGINEER → ROUTER → PLANNER
and prints the output at each stage. Runs against real Ollama — no mocks.

Usage:
    python scripts/test_graph_flow.py             # run predefined cases
    python scripts/test_graph_flow.py -m "msg"    # run a single custom message
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

from config import PLANNER_MODEL, PROMPT_ENGINEER_MODEL, ROUTER_MODEL
from graph.nodes.planner import planner
from graph.nodes.prompt_engineer import prompt_engineer
from graph.nodes.router import router

CASES = [
    "add buy milk to my tasks pls",
    "wats the capital of france",
    "search the web for best python tutorials and add the top one to my list",
]

WIDE = "═" * 65

DEFAULT_USER_ID = "clarkehines"
DEFAULT_TIER = "admin"


def run_flow(message: str) -> None:
    print(WIDE)
    print(f"  Message: {message!r}")
    print(WIDE)

    state: dict = {
        "current_input": message,
        "user_id": DEFAULT_USER_ID,
        "tier": DEFAULT_TIER,
    }

    # PROMPT_ENGINEER
    pe_result = prompt_engineer(state)
    state.update(pe_result)
    print(f"\n[PROMPT_ENGINEER]  {PROMPT_ENGINEER_MODEL}")
    print(f"  {state['engineered_message']}")

    # ROUTER
    router_result = router(state)
    state.update(router_result)
    print(f"\n[ROUTER]  {ROUTER_MODEL}")
    if "error" in router_result:
        print(f"  Error: {router_result['error']}")
        print()
        return
    print(f"  intent:  {state['intent']}")
    print(f"  skills:  {state['detected_skills']}")
    print(f"  gated:   {state['tier_gate']}")

    # PLANNER
    planner_result = planner(state)
    state.update(planner_result)
    print(f"\n[PLANNER]  {PLANNER_MODEL}")
    if "error" in planner_result:
        print(f"  Error: {planner_result['error']}")
    else:
        for step in state["step_plan"]:
            deps = step["depends_on"] if step["depends_on"] else ["none"]
            print(f"  [{step['id']}] ({step['intent']}) {step['description']}")
            print(f"        depends_on: {deps}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--message", help="Run a single custom message through the full flow")
    args = parser.parse_args()

    if args.message:
        run_flow(args.message)
    else:
        for msg in CASES:
            run_flow(msg)


if __name__ == "__main__":
    main()
