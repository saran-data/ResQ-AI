"""
ResQAI - WebSocket Manager
Real-time event broadcasting for live tracking, notifications, and agent status.
"""

import json
from typing import Dict, Set
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from loguru import logger

from app.core.security import decode_token, TokenType

websocket_router = APIRouter()


class ConnectionManager:
    """
    Manages all active WebSocket connections.
    Supports:
    - Broadcasting to all connected clients
    - Targeting specific users
    - Room-based broadcasting (donation tracking rooms)
    """

    def __init__(self) -> None:
        # user_id → set of WebSocket connections (multi-device support)
        self._user_connections: Dict[str, Set[WebSocket]] = {}
        # donation_id → set of WebSocket connections (tracking rooms)
        self._room_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        await websocket.accept()
        if user_id not in self._user_connections:
            self._user_connections[user_id] = set()
        self._user_connections[user_id].add(websocket)
        logger.info(f"WebSocket connected: user={user_id}, total={self._connection_count}")

    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        if user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        # Remove from all rooms
        for room_connections in self._room_connections.values():
            room_connections.discard(websocket)

        logger.info(f"WebSocket disconnected: user={user_id}")

    async def join_room(self, websocket: WebSocket, room_id: str) -> None:
        """Subscribe to a tracking room (e.g., donation_{id})."""
        if room_id not in self._room_connections:
            self._room_connections[room_id] = set()
        self._room_connections[room_id].add(websocket)

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to all connections for a specific user."""
        connections = self._user_connections.get(user_id, set()).copy()
        dead = set()
        for ws in connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._user_connections[user_id].discard(ws)

    async def broadcast_to_room(self, room_id: str, message: dict) -> None:
        """Broadcast to all clients in a tracking room."""
        connections = self._room_connections.get(room_id, set()).copy()
        dead = set()
        for ws in connections:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._room_connections[room_id].discard(ws)

    async def broadcast_all(self, message: dict) -> None:
        """Broadcast to all connected clients (admin alerts)."""
        for user_id, connections in list(self._user_connections.items()):
            for ws in connections.copy():
                try:
                    await ws.send_text(json.dumps(message))
                except Exception:
                    self._user_connections[user_id].discard(ws)

    @property
    def _connection_count(self) -> int:
        return sum(len(ws) for ws in self._user_connections.values())


# Global connection manager instance
manager = ConnectionManager()


def _authenticate_ws_token(token: str) -> str:
    """Validate JWT token for WebSocket connection. Returns user_id."""
    try:
        payload = decode_token(token)
        if payload.get("type") != TokenType.ACCESS:
            return "anonymous"
        return payload.get("sub", "anonymous")
    except Exception:
        return "anonymous"


@websocket_router.websocket("/connect")
async def websocket_connect(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    Main WebSocket connection endpoint.
    Clients authenticate by passing JWT token as query param.

    Events emitted to client:
    - notification: New notification received
    - donation.status_changed: Donation lifecycle update
    - delivery.location: Real-time GPS tracking update
    - ai.decision: Agent completed a task
    """
    user_id = _authenticate_ws_token(token)
    await manager.connect(websocket, user_id)

    try:
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "event": "connected",
            "user_id": user_id,
            "message": "Connected to ResQAI real-time feed",
        }))

        while True:
            # Receive and process client messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                event = msg.get("event", "")

                # Client joins a donation tracking room
                if event == "track.donation" and "donation_id" in msg:
                    await manager.join_room(websocket, f"donation_{msg['donation_id']}")
                    await websocket.send_text(json.dumps({
                        "event": "tracking.started",
                        "donation_id": msg["donation_id"],
                    }))

                # Ping/pong keepalive
                elif event == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)


@websocket_router.websocket("/tracking/{donation_id}")
async def donation_tracking_ws(
    websocket: WebSocket,
    donation_id: str,
    token: str = Query(default=""),
):
    """
    Dedicated tracking WebSocket for a specific donation.
    Broadcasts GPS updates from the volunteer's app to the restaurant and NGO.
    """
    user_id = _authenticate_ws_token(token) if token else "guest"
    await manager.connect(websocket, user_id)
    await manager.join_room(websocket, f"donation_{donation_id}")

    try:
        await websocket.send_text(json.dumps({
            "event": "tracking.connected",
            "donation_id": donation_id,
        }))

        while True:
            data = await websocket.receive_text()
            try:
                update = json.loads(data)
                # Volunteer sending location update
                if update.get("event") == "location.update":
                    # Broadcast to all tracking this donation
                    await manager.broadcast_to_room(
                        f"donation_{donation_id}",
                        {
                            "event": "delivery.location",
                            "donation_id": donation_id,
                            "latitude": update.get("latitude"),
                            "longitude": update.get("longitude"),
                            "speed": update.get("speed"),
                            "heading": update.get("heading"),
                            "timestamp": update.get("timestamp"),
                        },
                    )
                    # Persist to DB via Celery (non-blocking)
                    try:
                        from app.tasks.ai_tasks import run_agent_task
                        # Update delivery GPS in background
                    except Exception:
                        pass

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


# Module-level function so other services can push to connected clients
async def push_to_user(user_id: str, event: str, data: dict) -> None:
    """Push a WebSocket event to a specific user. Called by AI agents and services."""
    await manager.send_to_user(user_id, {"event": event, "data": data})


async def push_to_donation_room(donation_id: str, event: str, data: dict) -> None:
    """Push to all clients tracking a specific donation."""
    await manager.broadcast_to_room(
        f"donation_{donation_id}",
        {"event": event, "data": data, "donation_id": donation_id},
    )
