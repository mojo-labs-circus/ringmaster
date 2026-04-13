"""api/auth.py
Auth endpoints — login, refresh, logout, invite, register.
Gets its repository via Depends(get_auth_repository) — never constructs it directly.
"""

import hashlib
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import jwt

from api.dependencies import get_current_user, require_admin
from api.schemas import (
    InviteRequest,
    InviteResponse,
    LoginRequest,
    LogoutRequest,
    PasswordChangeRequest,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ResetRequest,
    TokenResponse,
)
from config import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    ALGORITHM,
    BRUTE_FORCE_LIMIT,
    BRUTE_FORCE_WINDOW_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY,
)
from db.auth.factory import get_auth_repository
from db.auth.models import Invite, RefreshToken, User
from db.auth.repository import AuthRepository

router = APIRouter(prefix="/auth", tags=["auth"])

# Brute-force tracking — in-memory, resets on server restart (acceptable per spec)
# Maps IP address -> list of failed attempt timestamps
_failed_attempts: dict[str, list[datetime]] = defaultdict(list)
_BRUTE_FORCE_WINDOW = timedelta(minutes=BRUTE_FORCE_WINDOW_MINUTES)


def _hash_token(raw: str) -> str:
    # SHA-256 — raw token is never stored, only this hash
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_access_token(user: User, client_type: str) -> tuple[str, str]:
    """Issue a signed access token. Returns (token, access_expires_at ISO string)."""
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "user_id": user.username,
        "client_type": client_type,
        "token_version": user.token_version,
        "exp": expires_at,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), expires_at.isoformat()


def _record_failed_attempt(ip: str) -> None:
    now = datetime.now(timezone.utc)
    # Drop attempts outside the rolling window before counting
    _failed_attempts[ip] = [t for t in _failed_attempts[ip] if now - t < _BRUTE_FORCE_WINDOW]
    _failed_attempts[ip].append(now)
    if len(_failed_attempts[ip]) >= BRUTE_FORCE_LIMIT:
        # TODO: wire up when monitoring/notify.py is built —
        # notify_admin("BruteForce", f"{ip} hit {BRUTE_FORCE_LIMIT} failed logins in {BRUTE_FORCE_WINDOW_MINUTES} minutes")
        pass


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    repo: AuthRepository = Depends(get_auth_repository),
) -> TokenResponse:
    ip = request.client.host
    user = repo.get_user(body.username)

    # Same error for wrong username and wrong password — don't reveal which one failed
    if user is None or not bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        _record_failed_attempt(ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if user.disabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled. Contact admin to restore access.")

    raw_refresh = secrets.token_urlsafe(32)
    repo.create_refresh_token(RefreshToken(
        id=None,
        user_id=user.username,
        token_hash=_hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        revoked=False,
    ))

    access_token, access_expires_at = _build_access_token(user, body.client_type)
    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,  # only time the raw token exists in plaintext
        access_expires_at=access_expires_at,
    )


@router.post("/refresh", response_model=RefreshResponse)
def refresh(
    body: RefreshRequest,
    repo: AuthRepository = Depends(get_auth_repository),
) -> RefreshResponse:
    stored = repo.get_refresh_token_by_hash(_hash_token(body.refresh_token))

    if stored is None or stored.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # SQLite stores datetimes without timezone — attach UTC before comparing
    if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = repo.get_user(stored.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.disabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account disabled. Contact admin to restore access.")

    # Re-read tier, assistant_name, token_version from the live record —
    # picks up any changes made since original login
    access_token, access_expires_at = _build_access_token(user, body.client_type)
    return RefreshResponse(access_token=access_token, access_expires_at=access_expires_at)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    body: LogoutRequest,
    repo: AuthRepository = Depends(get_auth_repository),
    user: User = Depends(get_current_user),
) -> None:
    # Revoke this device's refresh token only — other devices stay active
    repo.revoke_refresh_token(_hash_token(body.refresh_token))


@router.post("/invite", response_model=InviteResponse)
def invite(
    body: InviteRequest,
    repo: AuthRepository = Depends(get_auth_repository),
    _: User = Depends(require_admin),
) -> InviteResponse:
    if body.type not in ("invite", "password_reset"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")

    if body.type == "invite" and (body.tier is None or body.assistant_name is None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tier and assistant_name are required for invite tokens")

    if body.type == "password_reset":
        if repo.get_user(body.username) is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    raw_token = secrets.token_urlsafe(32)
    repo.create_invite(Invite(
        id=None,
        token_hash=_hash_token(raw_token),
        type=body.type,
        username=body.username,
        tier=body.tier,
        assistant_name=body.assistant_name,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
        used=False,
    ))
    return InviteResponse(token=raw_token)  # only time the raw token exists in plaintext


@router.post("/register", status_code=status.HTTP_200_OK)
def register(
    body: RegisterRequest,
    repo: AuthRepository = Depends(get_auth_repository),
) -> None:
    stored_invite = repo.get_invite_by_hash(_hash_token(body.token))

    if stored_invite is None or stored_invite.used or stored_invite.type != "invite":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invite token")

    # SQLite stores datetimes without timezone — attach UTC before comparing
    if stored_invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite token expired")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    repo.create_user(User(
        username=stored_invite.username,
        password_hash=password_hash,
        tier=stored_invite.tier,
        assistant_name=stored_invite.assistant_name,
        token_version=0,
        disabled=False,
    ))
    # Mark invite used after user creation — if create_user fails, invite stays valid
    repo.mark_invite_used(_hash_token(body.token))


@router.post("/reset", status_code=status.HTTP_200_OK)
def reset_password(
    body: ResetRequest,
    repo: AuthRepository = Depends(get_auth_repository),
) -> None:
    stored = repo.get_invite_by_hash(_hash_token(body.token))

    if stored is None or stored.used or stored.type != "password_reset":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")

    if stored.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token expired")

    user = repo.get_user(stored.username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")

    # Reject the new password if it matches the compromised one
    if bcrypt.checkpw(body.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password must differ from current password")

    new_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    repo.update_password(stored.username, new_hash)
    repo.enable_user(stored.username)
    # Mark token used after updates — if either update fails, token stays valid for retry
    repo.mark_invite_used(_hash_token(body.token))


@router.post("/password", status_code=status.HTTP_200_OK)
def change_password(
    body: PasswordChangeRequest,
    repo: AuthRepository = Depends(get_auth_repository),
    user: User = Depends(get_current_user),
) -> None:
    if not bcrypt.checkpw(body.current_password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password incorrect")

    new_hash = bcrypt.hashpw(body.new_password.encode(), bcrypt.gensalt()).decode()
    repo.update_password(user.username, new_hash)
