from fastapi import HTTPException, status

from ConnectionManager import ConnectionManager
from database import NotificationRepository
from firebase import FirebaseClient
from schemas import (
    DeviceRegistrationRequest,
    FriendRequestEventRequest,
    FriendRequestResponseEventRequest,
    NotificationEventType,
    NotificationPayload,
    StationReachedEventRequest,
)


class NotificationService:
    def __init__(
        self,
        repository: NotificationRepository,
        manager: ConnectionManager,
        push_client: FirebaseClient,
    ) -> None:
        self.repository = repository
        self.manager = manager
        self.push_client = push_client

    def register_device(self, user_id: int, payload: DeviceRegistrationRequest) -> None:
        self.repository.upsert_device_token(
            user_id=user_id,
            device_id=payload.device_id,
            fcm_token=payload.fcm_token,
            device_name=payload.device_name,
            device_type=payload.device_type,
        )

    async def notify_station_reached(
        self,
        actor_id: int,
        payload: StationReachedEventRequest,
    ) -> dict[str, int]:
        self._ensure_user_exists(actor_id)

        actor_name = self.repository.get_user_name(actor_id)
        tokens_by_friend = self.repository.get_friend_device_tokens(actor_id)
        live_count = 0
        push_count = 0

        for friend_id, tokens in tokens_by_friend.items():
            if self._is_blocked_between(actor_id, friend_id):
                continue

            message = NotificationPayload(
                type=NotificationEventType.STATION_REACHED,
                title="Friend reached the station",
                body=f"{actor_name} has reached the station.",
                actor_id=actor_id,
                data={"friend_id": str(actor_id), "reached": str(payload.reached).lower()},
            )

            delivered = await self.manager.send_to_user(friend_id, message)
            if delivered:
                live_count += 1

            result = self.push_client.send_notification(
                tokens=tokens,
                title=message.title,
                body=message.body,
                data=message.data | {"event_type": message.type.value},
            )
            push_count += result["success_count"]
            self._delete_invalid_tokens(result["invalid_tokens"])

        return {"live_deliveries": live_count, "push_deliveries": push_count}

    async def send_friend_request(
        self,
        sender_id: int,
        payload: FriendRequestEventRequest,
    ) -> dict[str, int]:
        receiver_id = payload.receiver_id
        self._validate_user_interaction(sender_id, receiver_id)

        sender_name = self.repository.get_user_name(sender_id)
        message = NotificationPayload(
            type=NotificationEventType.FRIEND_REQUEST,
            title="New friend request",
            body=f"{sender_name} sent you a friend request.",
            actor_id=sender_id,
            data={"sender_id": str(sender_id)},
        )

        return await self._deliver_to_user(receiver_id, message)

    async def respond_to_friend_request(
        self,
        receiver_id: int,
        payload: FriendRequestResponseEventRequest,
    ) -> dict[str, int]:
        sender_id = payload.sender_id
        self._validate_user_interaction(receiver_id, sender_id)

        if not self.repository.friend_request_exists(sender_id=sender_id, receiver_id=receiver_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Friend request not found",
            )

        receiver_name = self.repository.get_user_name(receiver_id)
        message = NotificationPayload(
            type=NotificationEventType.FRIEND_REQUEST_RESPONSE,
            title="Friend request update",
            body=f"{receiver_name} {payload.status.value} your friend request.",
            actor_id=receiver_id,
            data={"receiver_id": str(receiver_id), "status": payload.status.value},
        )

        return await self._deliver_to_user(sender_id, message)

    async def send_chat_message(
        self,
        sender_id: int,
        receiver_id: int,
        content: str
    ) -> dict[str, int]:
        self._validate_user_interaction(sender_id, receiver_id)

        if not self.repository.are_friends(sender_id, receiver_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Users must be friends to chat",
            )
            
        self.repository.save_chat_message(sender_id, receiver_id, content)

        sender_name = self.repository.get_user_name(sender_id)
        message = NotificationPayload(
            type=NotificationEventType.CHAT,
            title=f"New message from {sender_name}",
            body=content,
            actor_id=sender_id,
            data={"sender_id": str(sender_id), "content": content},
        )

        return await self._deliver_to_user(receiver_id, message)

    async def _deliver_to_user(self, user_id: int, payload: NotificationPayload) -> dict[str, int]:
        delivered = await self.manager.send_to_user(user_id, payload)
        if delivered:
            return {"live_deliveries": 1, "push_deliveries": 0}

        result = self.push_client.send_notification(
            tokens=self.repository.get_user_tokens(user_id),
            title=payload.title,
            body=payload.body,
            data=payload.data | {"event_type": payload.type.value},
        )
        self._delete_invalid_tokens(result["invalid_tokens"])
        return {"live_deliveries": 0, "push_deliveries": result["success_count"]}

    def _validate_user_interaction(self, actor_id: int, target_id: int) -> None:
        if actor_id == target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Users cannot target themselves",
            )

        self._ensure_user_exists(actor_id)
        self._ensure_user_exists(target_id)

        if self._is_blocked_between(actor_id, target_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Notification blocked due to block settings",
            )

    def _ensure_user_exists(self, user_id: int) -> None:
        if not self.repository.user_exists(user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

    def _is_blocked_between(self, user_a: int, user_b: int) -> bool:
        return self.repository.is_user_blocked(user_a, user_b) or self.repository.is_user_blocked(
            user_b,
            user_a,
        )

    def _delete_invalid_tokens(self, tokens: list[str]) -> None:
        for token in tokens:
            self.repository.delete_token(token)

