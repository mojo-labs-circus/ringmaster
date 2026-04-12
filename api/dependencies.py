from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from config import ALGORITHM, SECRET_KEY
from db.auth.factory import get_auth_repository
from db.auth.models import User
from db.auth.repository import AuthRepository

_bearer = HTTPBearer()


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.tier != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_power_or_above(user: User = Depends(get_current_user)) -> User:
    if user.tier not in ("admin", "power"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Power tier or above required")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    repo: AuthRepository = Depends(get_auth_repository),
) -> User:
    """
    FastAPI dependency for authenticated routes.
    Decodes the JWT, validates token_version against the database,
    and returns the User. Raises 401 on any failure.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    username: str | None = payload.get("user_id")
    token_version: int | None = payload.get("token_version")

    if username is None or token_version is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = repo.get_user(username)

    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # token_version mismatch means logout or forced deauth has occurred since this token was issued
    if user.token_version != token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalidated")

    return user
