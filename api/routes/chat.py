"""api/routes/chat.py
WebSocket endpoint for chat. Owns all frame sending.
Uses astream_events to stream tokens and status frames as the graph executes."""

import asyncio
import json
import logging
import secrets
import socket
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from api import connections
from api.dependencies import ConnectedClient, get_connected_client_ws
from config import STATUS_MESSAGES
from db.auth.factory import get_auth_repository
from db.auth.repository import AuthRepository
from db.history.factory import get_history_repository
from db.history.models import HistoryEntry
from db.history.repository import HistoryRepository
from graph.graph import jarvis_graph
from graph.state import JarvisState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat")


@router.websocket("/ws")
async def chat_ws(
    websocket: WebSocket,
    client: ConnectedClient = Depends(get_connected_client_ws),
    auth_repo: AuthRepository = Depends(get_auth_repository),
    history_repo: HistoryRepository = Depends(get_history_repository),
) -> None:
    await websocket.accept()

    user = client.user
    token_version_at_connect = user.token_version
    client_ip = websocket.client.host if websocket.client else "unknown"
    try:
        client_hostname = socket.gethostbyaddr(client_ip)[0].split(".")[0]
    except OSError:
        client_hostname = client_ip
    logger.info("Client connected: %s via %s from %s (%s)", user.username, client.client_type, client_hostname, client_ip)

    connections.register(user.username, client)

    # Depth-1 buffer — last message wins while the processor is busy.
    # pending: the envelope (the raw message string).
    # message_ready: the doorbell (signals the processor to wake up).
    # The reader owns all WebSocket reads. The processor owns all processing and sending.
    pending: str | None = None
    message_ready = asyncio.Event()
    is_busy = False

    async def _reader() -> None:
        """Reads frames from the WebSocket continuously.

        Idle: saves to pending, rings the doorbell for the processor.
        Busy: saves to pending (last wins), sends "One moment..." immediately.
        Disconnect: clears pending, rings doorbell so the processor exits cleanly.
        """
        nonlocal pending
        try:
            while True:
                raw = await websocket.receive_text()
                pending = raw
                if is_busy:
                    try:
                        frame = json.loads(raw)
                        message_id = frame.get("message_id", secrets.token_hex(4))
                    except json.JSONDecodeError:
                        message_id = secrets.token_hex(4)
                    await websocket.send_json({
                        "type": "status",
                        "message_id": message_id,
                        "message": "One moment...",
                    })
                else:
                    message_ready.set()
        except WebSocketDisconnect:
            logger.info(
                "Client disconnected: %s via %s from %s (%s)",
                user.username, client.client_type, client_hostname, client_ip,
            )
            pending = None       # discard any buffered message
            message_ready.set()  # wake the processor so it exits cleanly

    reader_task = asyncio.create_task(_reader())

    try:
        while True:
            await message_ready.wait()
            message_ready.clear()

            raw = pending
            pending = None

            if raw is None:
                break  # disconnect signalled by reader

            # Re-check token_version on every message — catches forced deauth mid-session
            current_user = auth_repo.get_user(user.username)
            if current_user is None or current_user.token_version != token_version_at_connect:
                await websocket.send_json({
                    "type": "error",
                    "message_id": secrets.token_hex(4),
                    "message": "Session invalidated. Please log in again.",
                })
                break

            # Parse frame
            try:
                frame = json.loads(raw)
                message_id = frame["message_id"]
                content = frame["content"]
                active_project = frame.get("active_project")
            except (json.JSONDecodeError, KeyError) as exc:
                await websocket.send_json({
                    "type": "error",
                    "message_id": secrets.token_hex(4),
                    "message": f"Invalid frame: {exc}",
                })
                continue

            client.last_activity = datetime.now(timezone.utc)

            is_busy = True
            try:
                state: JarvisState = {
                    "user_id": user.username,
                    "message_id": message_id,
                    "tier": user.tier,
                    "client_type": client.client_type,
                    "assistant_name": user.assistant_name,
                    "current_input": content,
                    "engineered_message": "",
                    "active_project": active_project,
                    "intent": [],
                    "tier_gate": [],
                    "detected_skills": [],
                    "active_step_prompt": None,
                    "step_response": "",
                    "assembled_response": "",
                    "status_message": None,
                    "error": None,
                    "interrupt_payload": None,
                    "correction": None,
                    "step_plan": None,
                    "step_results": [],
                    "refresh": [],
                }

                final_state = None
                async for event in jarvis_graph.astream_events(state, version="v2"):
                    event_type = event["event"]
                    event_name = event["name"]

                    if event_type == "on_chain_start":
                        # Node entry — send status frame if configured in STATUS_MESSAGES
                        node_name = event.get("metadata", {}).get("langgraph_node")
                        if node_name and STATUS_MESSAGES.get(node_name):
                            await websocket.send_json({
                                "type": "status",
                                "message_id": message_id,
                                "message": STATUS_MESSAGES[node_name],
                            })

                    elif event_type == "on_chat_model_stream":
                        # Streaming token from an LLM call inside a node
                        chunk_content = event["data"]["chunk"].content
                        if chunk_content:
                            await websocket.send_json({
                                "type": "token",
                                "message_id": message_id,
                                "content": chunk_content,
                            })

                    elif event_type == "on_custom_event" and event_name == "status_message":
                        # Mid-node status written by a node during execution
                        await websocket.send_json({
                            "type": "status",
                            "message_id": message_id,
                            "message": event["data"]["message"],
                        })

                    elif event_type == "on_chain_end" and event_name == "LangGraph":
                        final_state = event["data"]["output"]

                if final_state is None:
                    raise RuntimeError("Graph completed without final state")

                # Write history before done frame — guarantees continuity if the process
                # crashes after this point. A single SQL INSERT, negligible latency.
                # Store assembled_response: RESPONDER always produces clean markdown, which
                # is safe to feed back into Ollama context on the next request.
                now = datetime.now(timezone.utc)
                history_repo.save(HistoryEntry(
                    id=None,
                    user_id=user.username,
                    role="user",
                    content=content,
                    created_at=now,
                ))
                history_repo.save(HistoryEntry(
                    id=None,
                    user_id=user.username,
                    role="assistant",
                    content=final_state["assembled_response"],
                    created_at=now,
                ))

                await websocket.send_json({
                    "type": "done",
                    "message_id": message_id,
                    "refresh": final_state["refresh"],
                })

                # TODO: fire memory/persist.py as asyncio background task — module not yet built

            except Exception:
                logger.exception("Error during graph invocation for %s", user.username)
                await websocket.send_json({
                    "type": "error",
                    "message_id": message_id,
                    "message": "An unexpected error occurred.",
                })

            finally:
                is_busy = False
                # If the reader buffered a message during processing, ring the doorbell
                # so the processor picks it up on the next iteration.
                if pending is not None:
                    message_ready.set()

    finally:
        reader_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        connections.deregister(user.username, client)
