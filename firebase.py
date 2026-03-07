import logging
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging


logger = logging.getLogger(__name__)


class FirebaseClient:
    def __init__(self, credentials_path: str | None = None) -> None:
        self.credentials_path = credentials_path or os.environ.get(
            "FIREBASE_CREDENTIALS_PATH",
            "firebase-keys.json",
        )
        self.enabled = False
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        if firebase_admin._apps:
            self.enabled = True
            return

        credential_file = Path(self.credentials_path)
        if not credential_file.exists():
            logger.warning("Firebase credentials file not found at %s", credential_file)
            return

        try:
            firebase_admin.initialize_app(credentials.Certificate(str(credential_file)))
            self.enabled = True
        except Exception as exc:
            logger.exception("Firebase initialization failed: %s", exc)
            self.enabled = False

    def send_notification(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> dict[str, list[str] | int]:
        if not tokens or not self.enabled:
            return {"success_count": 0, "invalid_tokens": [], "failure_count": 0}

        success_count = 0
        invalid_tokens: list[str] = []

        for token in tokens:
            try:
                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    token=token,
                )
                messaging.send(message)
                success_count += 1
            except Exception:
                invalid_tokens.append(token)

        return {
            "success_count": success_count,
            "invalid_tokens": invalid_tokens,
            "failure_count": len(invalid_tokens),
        }


def send_station_push_notification(friend_name: str, device_token: str):
    client = FirebaseClient()
    result = client.send_notification(
        [device_token],
        "Friend status update",
        f"{friend_name} has reached the station.",
        {"event_type": "station_reached"},
    )
    return result["success_count"] == 1


def send_friend_request_status_notification(friend_name: str, status: str, device_token: str):
    client = FirebaseClient()
    body = (
        f"{friend_name} accepted your friend request."
        if status == "accepted"
        else f"{friend_name} responded to your friend request: {status}."
    )
    result = client.send_notification(
        [device_token],
        "Friend request update",
        body,
        {"event_type": "friend_request_response", "status": status},
    )
    return result["success_count"] == 1

