"""api/schemas.py
Pydantic request and response models for all JARVIS API endpoints.
Imported by route modules — never by graph nodes or repository implementations.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from db.tasks.models import Task


# --- Login ---

class LoginRequest(BaseModel):
    """Credentials and client identity sent at login."""

    username: str
    password: str
    client_type: str  # tui | web | mobile — baked into the JWT


class TokenResponse(BaseModel):
    """Access and refresh tokens returned on successful login."""

    access_token: str
    refresh_token: str
    access_expires_at: str  # ISO 8601 datetime string


# --- Refresh ---

class RefreshRequest(BaseModel):
    """Refresh token and client type sent to obtain a new access token."""

    refresh_token: str
    client_type: str  # tui | web | mobile — client knows its own type, no need to store in refresh_tokens


class RefreshResponse(BaseModel):
    """New access token issued in exchange for a valid refresh token."""

    access_token: str
    access_expires_at: str  # ISO 8601 datetime string


# --- Logout ---

class LogoutRequest(BaseModel):
    """Refresh token identifying the device session to terminate."""

    refresh_token: str  # identifies which refresh_tokens row to revoke


# --- Invite ---

class InviteRequest(BaseModel):
    """Admin request to generate an invite or password reset token.

    tier and assistant_name are required for invite type and ignored for password_reset.
    """

    type: str = "invite"        # invite | password_reset
    username: str
    tier: str | None = None     # required for invite, omitted for password_reset
    assistant_name: str | None = None  # required for invite, omitted for password_reset


class InviteResponse(BaseModel):
    """Raw one-time token — the only time it exists in plaintext outside a hash."""

    token: str  # raw token — only time it exists in plaintext, share immediately


# --- Register ---

class RegisterRequest(BaseModel):
    """Registration credentials. token is the raw invite token issued by the admin."""

    token: str      # raw invite token
    password: str


# --- Password Reset ---

class ResetRequest(BaseModel):
    """Password reset credentials. token is the raw reset token issued by the admin."""

    token: str      # raw password reset token
    password: str   # new password — rejected if it matches the current password_hash


# --- Password Change (self-service) ---

class PasswordChangeRequest(BaseModel):
    """Self-service password change. current_password is verified before the update is applied."""

    current_password: str
    new_password: str


# --- Profile ---

class ProfileResponse(BaseModel):
    """Public user profile data returned by GET /profile."""

    username: str
    tier: str
    assistant_name: str


class ProfileUpdateRequest(BaseModel):
    """Fields the user can update on their own profile."""

    assistant_name: str


# --- Tasks ---

class TaskResponse(BaseModel):
    """Task data returned by GET /tasks. Use from_task() to convert from the Task dataclass."""

    id: int
    user_id: str
    title: str
    status: str
    priority: str
    due_date: datetime | None
    created_at: datetime

    @classmethod
    def from_task(cls, task: Task) -> TaskResponse:
        return cls(
            id=task.id,
            user_id=task.user_id,
            title=task.title,
            status=task.status,
            priority=task.priority,
            due_date=task.due_date,
            created_at=task.created_at,
        )
