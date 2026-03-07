from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationEventType(str, Enum):
    STATION_REACHED = "station_reached"
    FRIEND_REQUEST = "friend_request"
    FRIEND_REQUEST_RESPONSE = "friend_request_response"


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
    type: Literal["ping"]

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value != "ping":
            raise ValueError("Only ping messages are allowed over websocket")
        return value

