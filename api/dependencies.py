from dataclasses import dataclass, field
from datetime import datetime

from fastapi import Depends, HTTPException, Query, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import ALGORITHM, SECRET_KEY
from db.auth.factory import get_auth_repository
from db.auth.models import User
from db.auth.repository import AuthRepository


@dataclass
class ConnectedClient:
    user: User
    client_type: str
    websocket: WebSocket
    last_activity: datetime | None = field(default=None)


_bearer = HTTPBearer()


def _decode_token(token: str, http_status: int) -> dict:
    """Decode and signature-verify the JWT. Raises HTTPException on any failure."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=http_status, detail="Invalid token")


def _get_user_from_payload(payload: dict, repo: AuthRepository, http_status: int) -> User:
    """
    Validate an already-decoded JWT payload against the database and return the User.
    Checks that user_id and token_version are present, the user exists, and token_version
    matches the live DB record (mismatch means forced deauth has occurred).
    HTTP routes pass 401; WebSocket routes pass 403.
    """
    username: str | None = payload.get("user_id")
    token_version: int | None = payload.get("token_version")

    if username is None or token_version is None:
        raise HTTPException(status_code=http_status, detail="Invalid token")

    user = repo.get_user(username)

    if user is None:
        raise HTTPException(status_code=http_status, detail="User not found")

    if user.disabled:
        raise HTTPException(status_code=http_status, detail="Account disabled")

    # token_version mismatch means forced deauth has occurred since this token was issued
    if user.token_version != token_version:
        raise HTTPException(status_code=http_status, detail="Token invalidated")

    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    repo: AuthRepository = Depends(get_auth_repository),
) -> User:
    """FastAPI dependency for authenticated HTTP routes. Reads token from Authorization header."""
    payload = _decode_token(credentials.credentials, status.HTTP_401_UNAUTHORIZED)
    return _get_user_from_payload(payload, repo, status.HTTP_401_UNAUTHORIZED)


def get_current_user_ws(
    websocket: WebSocket,
    token: str = Query(...),
    repo: AuthRepository = Depends(get_auth_repository),
) -> User:
    """
    FastAPI dependency for authenticated WebSocket endpoints.
    Reads token from query param (?token=...) — WebSocket connections
    cannot set arbitrary headers.
    """
    payload = _decode_token(token, status.HTTP_403_FORBIDDEN)
    return _get_user_from_payload(payload, repo, status.HTTP_403_FORBIDDEN)


def get_connected_client_ws(
    websocket: WebSocket,
    token: str = Query(...),
    repo: AuthRepository = Depends(get_auth_repository),
) -> ConnectedClient:
    """
    WebSocket dependency that returns both the authenticated User and client_type.
    Used by chat_ws — client_type is needed at connect time for logging and the
    connection registry, before the graph ever runs.
    """
    payload = _decode_token(token, status.HTTP_403_FORBIDDEN)

    client_type: str | None = payload.get("client_type")
    if client_type not in ("tui", "web", "mobile"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid client_type")

    user = _get_user_from_payload(payload, repo, status.HTTP_403_FORBIDDEN)
    return ConnectedClient(user=user, client_type=client_type, websocket=websocket)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.tier != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_power_or_above(user: User = Depends(get_current_user)) -> User:
    if user.tier not in ("admin", "power"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Power tier or above required")
    return user
