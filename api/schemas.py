from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from db.tasks.models import Task


# --- Login ---

class LoginRequest(BaseModel):
    username: str
    password: str
    client_type: str  # tui | web | mobile — baked into the JWT


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_at: str  # ISO 8601 datetime string


# --- Refresh ---

class RefreshRequest(BaseModel):
    refresh_token: str
    client_type: str  # tui | web | mobile — client knows its own type, no need to store in refresh_tokens


class RefreshResponse(BaseModel):
    access_token: str
    access_expires_at: str  # ISO 8601 datetime string


# --- Logout ---

class LogoutRequest(BaseModel):
    refresh_token: str  # identifies which refresh_tokens row to revoke


# --- Invite ---

class InviteRequest(BaseModel):
    type: str = "invite"        # invite | password_reset
    username: str
    tier: str | None = None     # required for invite, omitted for password_reset
    assistant_name: str | None = None  # required for invite, omitted for password_reset


class InviteResponse(BaseModel):
    token: str  # raw token — only time it exists in plaintext, share immediately


# --- Register ---

class RegisterRequest(BaseModel):
    token: str      # raw invite token
    password: str


# --- Password Reset ---

class ResetRequest(BaseModel):
    token: str      # raw password reset token
    password: str   # new password — rejected if it matches the current password_hash


# --- Password Change (self-service) ---

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


# --- Profile ---

class ProfileResponse(BaseModel):
    username: str
    tier: str
    assistant_name: str


class ProfileUpdateRequest(BaseModel):
    assistant_name: str


# --- Tasks ---

class TaskResponse(BaseModel):
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
