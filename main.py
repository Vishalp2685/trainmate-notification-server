import os
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from ConnectionManager import ConnectionManager
from database import NotificationRepository
from firebase import FirebaseClient
from notification_service import NotificationService
from schemas import (
    DeviceRegistrationRequest,
    FriendRequestEventRequest,
    FriendRequestResponseEventRequest,
    StationReachedEventRequest,
    WebSocketClientMessage,
)


load_dotenv()

ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")


def get_secret_key() -> str:
    secret_key = os.environ.get("JWT_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("JWT_SECRET_KEY environment variable not set")
    return secret_key


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        ) from exc

    user_id = payload.get("user_id") or payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token missing user identifier",
        )

    try:
        payload["user_id"] = int(user_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token contains invalid user identifier",
        ) from exc

    return payload


security = HTTPBearer()


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    return decode_access_token(credentials.credentials)["user_id"]


def create_app(
    repository: NotificationRepository | None = None,
    push_client: FirebaseClient | None = None,
    manager: ConnectionManager | None = None,
) -> FastAPI:
    app = FastAPI(title="Notification Server", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.manager = manager or ConnectionManager()
    app.state.repository = repository or NotificationRepository.from_env()
    app.state.push_client = push_client or FirebaseClient()
    app.state.notification_service = NotificationService(
        repository=app.state.repository,
        manager=app.state.manager,
        push_client=app.state.push_client,
    )

    def get_service() -> NotificationService:
        return app.state.notification_service

    @app.get("/health")
    async def healthcheck():
        return {"status": "ok"}

    @app.post("/devices/register", status_code=status.HTTP_204_NO_CONTENT)
    async def register_device(
        payload: DeviceRegistrationRequest,
        user_id: int = Depends(get_current_user_id),
        service: NotificationService = Depends(get_service),
    ):
        service.register_device(user_id, payload)

    @app.post("/notifications/friend-request")
    async def create_friend_request_notification(
        payload: FriendRequestEventRequest,
        user_id: int = Depends(get_current_user_id),
        service: NotificationService = Depends(get_service),
    ):
        return await service.send_friend_request(sender_id=user_id, payload=payload)

    @app.post("/notifications/friend-request-response")
    async def create_friend_request_response_notification(
        payload: FriendRequestResponseEventRequest,
        user_id: int = Depends(get_current_user_id),
        service: NotificationService = Depends(get_service),
    ):
        return await service.respond_to_friend_request(receiver_id=user_id, payload=payload)

    @app.post("/notifications/station-reached")
    async def create_station_reached_notification(
        payload: StationReachedEventRequest,
        user_id: int = Depends(get_current_user_id),
        service: NotificationService = Depends(get_service),
    ):
        return await service.notify_station_reached(actor_id=user_id, payload=payload)

    @app.websocket("/ws")
    async def websocket_endpoint(
        websocket: WebSocket,
        token: str = Query(..., min_length=1),
        device_id: str = Query(..., min_length=1, max_length=255),
    ):
        try:
            user_id = decode_access_token(token)["user_id"]
        except HTTPException:
            await websocket.close(code=1008)
            return

        manager_instance: ConnectionManager = app.state.manager
        await manager_instance.connect(websocket, user_id, device_id)
        await manager_instance.send_ack(user_id, device_id, "WebSocket connection established")

        try:
            while True:
                raw_message = await websocket.receive_json()
                message = WebSocketClientMessage.model_validate(raw_message)
                if message.type == "ping":
                    await websocket.send_json({"type": "pong", "detail": "alive"})
        except WebSocketDisconnect:
            await manager_instance.disconnect(user_id, device_id)
        except Exception:
            await websocket.send_json({"type": "error", "detail": "Invalid websocket payload"})
            await manager_instance.disconnect(user_id, device_id)
            await websocket.close(code=1003)

    return app


app = create_app()

