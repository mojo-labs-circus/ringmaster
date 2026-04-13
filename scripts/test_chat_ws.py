"""scripts/test_chat_ws.py
Throwaway end-to-end verification script — not a permanent test.
Logs in, opens the chat WebSocket, sends one message, prints all frames received.

Usage:
    python scripts/test_chat_ws.py
"""

import asyncio
import getpass
import json
import secrets

import httpx
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


async def main() -> None:
    username = input("Username [clarkehines]: ").strip() or "clarkehines"
    password = getpass.getpass("Password: ")

    # Step 1 — login
    print("\n→ POST /auth/login")
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE_URL}/auth/login", json={
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
    print(f"\n→ WS {WS_URL}/chat/ws")
    async with websockets.connect(f"{WS_URL}/chat/ws?token={token}") as ws:
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
