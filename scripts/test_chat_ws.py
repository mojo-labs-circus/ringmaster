"""scripts/test_chat_ws.py
Throwaway end-to-end verification script — not a permanent test.
Logs in, opens the chat WebSocket, sends one message, prints all frames received.

Usage:
    python scripts/test_chat_ws.py                        # localhost
    python scripts/test_chat_ws.py --host 192.168.1.50    # remote server
"""

import argparse
import asyncio
import getpass
import json
import secrets

import httpx
import websockets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost", help="Server host (default: localhost)")
    parser.add_argument("--port", default=8000, type=int, help="Server port (default: 8000)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    base_url = f"http://{args.host}:{args.port}"
    ws_url = f"ws://{args.host}:{args.port}"

    username = input("Username [clarkehines]: ").strip() or "clarkehines"
    password = getpass.getpass("Password: ")

    # Step 1 — login
    print(f"\n→ POST {base_url}/auth/login")
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{base_url}/auth/login", json={
            "username": username,
            "password": password,
            "client_type": "tui",
        })

    if resp.status_code != 200:
        print(f"✗ Login failed: {resp.status_code} {resp.text}")
        return

    token = resp.json()["access_token"]
    print(f"✓ Login OK — token: {token[:20]}...")

    # Step 2 — open WebSocket
    print(f"\n→ WS {ws_url}/chat/ws")
    async with websockets.connect(f"{ws_url}/chat/ws?token={token}") as ws:
        print("✓ Connected")

        # Step 3 — send a chat frame
        message_id = secrets.token_hex(4)
        frame = {"message_id": message_id, "content": "hello from the test script"}
        await ws.send(json.dumps(frame))
        print(f"\n→ Sent: {frame}")

        # Step 4 — receive frames until done or error
        print("\n← Received frames:")
        while True:
            raw = await asyncio.wait_for(ws.recv(), timeout=30)
            received = json.loads(raw)
            print(f"   {received}")
            if received.get("type") in ("done", "error"):
                break

    print("\n✓ Done")


if __name__ == "__main__":
    asyncio.run(main())
