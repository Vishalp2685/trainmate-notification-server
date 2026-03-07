"""
Custom exceptions for the notification server.
"""


class NotificationError(Exception):
    """Base exception for notification server."""
    pass


class AuthenticationError(NotificationError):
    """Raised when authentication fails."""
    pass


class ValidationError(NotificationError):
    """Raised when message validation fails."""
    pass


class UserNotFoundError(NotificationError):
    """Raised when user is not found in database."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(f"User {user_id} not found")


class UserBlockedError(NotificationError):
    """Raised when user is blocked by target."""
    def __init__(self, blocker_id: int, blocked_id: int):
        self.blocker_id = blocker_id
        self.blocked_id = blocked_id
        super().__init__(f"User {blocker_id} has blocked user {blocked_id}")


class InvalidRequestError(NotificationError):
    """Raised when request is invalid."""
    pass
