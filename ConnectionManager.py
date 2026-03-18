import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import WebSocket

from schemas import NotificationPayload


@dataclass
class ConnectionContext:
    websocket: WebSocket
    device_id: str
    connected_at: datetime


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, dict[str, ConnectionContext]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: int, device_id: str) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id][device_id] = ConnectionContext(
                websocket=websocket,
                device_id=device_id,
                connected_at=datetime.now(timezone.utc),
            )

    async def disconnect(self, user_id: int, device_id: str) -> None:
        async with self._lock:
            user_connections = self._connections.get(user_id)
            if not user_connections:
                return
            user_connections.pop(device_id, None)
            if not user_connections:
                self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: NotificationPayload) -> bool:
        async with self._lock:
            user_connections = list(self._connections.get(user_id, {}).items())

        delivered = False
        for device_id, context in user_connections:
            try:
                await context.websocket.send_json(payload.model_dump())
                delivered = True
            except Exception:
                await self.disconnect(user_id, device_id)
        return delivered

    async def send_json_to_user(self, user_id: int, payload: dict) -> bool:
        async with self._lock:
            user_connections = list(self._connections.get(user_id, {}).items())

        delivered = False
        for device_id, context in user_connections:
            try:
                await context.websocket.send_json(payload)
                delivered = True
            except Exception:
                await self.disconnect(user_id, device_id)
        return delivered

    async def send_ack(self, user_id: int, device_id: str, detail: str) -> None:
        async with self._lock:
            context = self._connections.get(user_id, {}).get(device_id)
        if context:
            await context.websocket.send_json({"type": "connected", "detail": detail})

    def is_user_online(self, user_id: int) -> bool:
        return bool(self._connections.get(user_id))

