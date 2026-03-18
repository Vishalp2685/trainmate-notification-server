from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationEventType(str, Enum):
    STATION_REACHED = "station_reached"
    FRIEND_REQUEST = "friend_request"
    FRIEND_REQUEST_RESPONSE = "friend_request_response"
    CHAT = "chat"


class FriendRequestStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DeviceRegistrationRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=255)
    fcm_token: str = Field(min_length=20)
    device_name: Optional[str] = Field(default=None, max_length=255)
    device_type: Optional[str] = Field(default=None, max_length=50)

    model_config = ConfigDict(str_strip_whitespace=True)


class StationReachedEventRequest(BaseModel):
    type: Literal[NotificationEventType.STATION_REACHED] = NotificationEventType.STATION_REACHED
    reached: bool = True


class FriendRequestEventRequest(BaseModel):
    type: Literal[NotificationEventType.FRIEND_REQUEST] = NotificationEventType.FRIEND_REQUEST
    receiver_id: int = Field(gt=0)


class FriendRequestResponseEventRequest(BaseModel):
    type: Literal[NotificationEventType.FRIEND_REQUEST_RESPONSE] = NotificationEventType.FRIEND_REQUEST_RESPONSE
    sender_id: int = Field(gt=0)
    status: FriendRequestStatus


class SendMessageRequest(BaseModel):
    receiver_id: int = Field(gt=0)
    content: str = Field(min_length=1)


class GetChatHistoryRequest(BaseModel):
    friend_id: int = Field(gt=0)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class NotificationPayload(BaseModel):
    type: NotificationEventType
    title: str
    body: str
    actor_id: int = Field(gt=0)
    data: dict[str, str] = Field(default_factory=dict)


class WebSocketAck(BaseModel):
    type: Literal["connected", "pong", "error"]
    detail: str


class WebSocketClientMessage(BaseModel):
    type: Literal["ping", "chat"]
    receiver_id: Optional[int] = None
    content: Optional[str] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in ["ping", "chat"]:
            raise ValueError("Only ping and chat messages are allowed over websocket")
        return value

