import os
from collections import defaultdict
from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


load_dotenv()


def _build_database_url() -> str:
    direct_url = os.environ.get("DATABASE_URL")
    if direct_url:
        return direct_url

    password = os.environ.get("password")
    if not password:
        raise ValueError("DATABASE_URL or password environment variable must be set")

    return (
        "postgresql://postgres.dlbtacxmxlgsjvmtrlsl:"
        f"{password}@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"
    )


class NotificationRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @classmethod
    def from_env(cls) -> "NotificationRepository":
        engine = create_engine(_build_database_url(), pool_pre_ping=True)
        return cls(engine)

    @contextmanager
    def _connection(self) -> Iterator:
        with self.engine.begin() as connection:
            yield connection

    def user_exists(self, user_id: int) -> bool:
        query = text("SELECT 1 FROM users WHERE unique_id = :user_id LIMIT 1")
        with self._connection() as connection:
            return connection.execute(query, {"user_id": user_id}).scalar() is not None

    def get_user_name(self, user_id: int) -> str:
        query = text(
            """
            SELECT CONCAT(first_name, ' ', last_name)
            FROM users
            WHERE unique_id = :user_id
            """
        )
        with self._connection() as connection:
            result = connection.execute(query, {"user_id": user_id}).scalar()
        return result or f"User {user_id}"

    def is_user_blocked(self, blocker_id: int, blocked_id: int) -> bool:
        query = text(
            """
            SELECT 1
            FROM blocked_users
            WHERE blocker_id = :blocker_id
              AND blocked_id = :blocked_id
            LIMIT 1
            """
        )
        with self._connection() as connection:
            return (
                connection.execute(
                    query,
                    {"blocker_id": blocker_id, "blocked_id": blocked_id},
                ).scalar()
                is not None
            )

    def are_friends(self, user_id: int, target_id: int) -> bool:
        query = text(
            """
            SELECT 1
            FROM friends
            WHERE (user1_id = :user_id AND user2_id = :target_id)
               OR (user1_id = :target_id AND user2_id = :user_id)
            LIMIT 1
            """
        )
        params = {"user_id": user_id, "target_id": target_id}
        with self._connection() as connection:
            return connection.execute(query, params).scalar() is not None

    def friend_request_exists(self, sender_id: int, receiver_id: int) -> bool:
        query = text(
            """
            SELECT 1
            FROM friend_requests
            WHERE sender_id = :sender_id
              AND receiver_id = :receiver_id
            LIMIT 1
            """
        )
        params = {"sender_id": sender_id, "receiver_id": receiver_id}
        with self._connection() as connection:
            return connection.execute(query, params).scalar() is not None

    def get_user_tokens(self, user_id: int) -> list[str]:
        query = text(
            """
            SELECT fcm_token
            FROM device_tokens
            WHERE user_id = :user_id
            """
        )
        with self._connection() as connection:
            rows = connection.execute(query, {"user_id": user_id}).fetchall()
        return [row[0] for row in rows if row[0]]

    def get_friend_device_tokens(self, user_id: int) -> dict[int, list[str]]:
        query = text(
            """
            SELECT friend_id, fcm_token
            FROM (
                SELECT
                    CASE
                        WHEN f.user1_id = :user_id THEN f.user2_id
                        ELSE f.user1_id
                    END AS friend_id,
                    d.fcm_token
                FROM friends f
                LEFT JOIN device_tokens d
                    ON d.user_id = CASE
                        WHEN f.user1_id = :user_id THEN f.user2_id
                        ELSE f.user1_id
                    END
                WHERE f.user1_id = :user_id
                   OR f.user2_id = :user_id
            ) AS friend_tokens
            """
        )
        with self._connection() as connection:
            rows = connection.execute(query, {"user_id": user_id}).fetchall()

        grouped: dict[int, list[str]] = defaultdict(list)
        for friend_id, token in rows:
            if token:
                grouped[friend_id].append(token)
            else:
                grouped.setdefault(friend_id, [])
        return dict(grouped)

    def upsert_device_token(
        self,
        user_id: int,
        device_id: str,
        fcm_token: str,
        device_name: str | None,
        device_type: str | None,
    ) -> None:
        update_query = text(
            """
            UPDATE device_tokens
            SET
                user_id = :user_id,
                fcm_token = :fcm_token,
                device_name = :device_name,
                device_type = :device_type,
                last_used_at = CURRENT_TIMESTAMP
            WHERE device_id = :device_id
            """
        )
        insert_query = text(
            """
            INSERT INTO device_tokens (
                user_id,
                device_id,
                fcm_token,
                device_name,
                device_type,
                created_at,
                last_used_at
            )
            VALUES (
                :user_id,
                :device_id,
                :fcm_token,
                :device_name,
                :device_type,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """
        )
        params = {
            "user_id": user_id,
            "device_id": device_id,
            "fcm_token": fcm_token,
            "device_name": device_name,
            "device_type": device_type,
        }
        with self._connection() as connection:
            result = connection.execute(update_query, params)
            if result.rowcount == 0:
                connection.execute(insert_query, params)

    def delete_token(self, token: str) -> None:
        query = text("DELETE FROM device_tokens WHERE fcm_token = :token")
        with self._connection() as connection:
            connection.execute(query, {"token": token})


def get_user_friends(user_id: int):
    return NotificationRepository.from_env().get_friend_device_tokens(user_id)


def save_user_device(user_id, token, device_type, device_name, device_id="default"):
    NotificationRepository.from_env().upsert_device_token(
        user_id=user_id,
        device_id=device_id,
        fcm_token=token,
        device_name=device_name,
        device_type=device_type,
    )
    return True


def get_user_tokens(user_id):
    return NotificationRepository.from_env().get_user_tokens(user_id)


def delete_token(token):
    NotificationRepository.from_env().delete_token(token)
    return True


def is_user_blocked(user_id, target_id):
    return NotificationRepository.from_env().is_user_blocked(user_id, target_id)


def user_exists(user_id):
    return NotificationRepository.from_env().user_exists(user_id)
