from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    username: str        # Primary key — used as user_id throughout the system
    password_hash: str   # bcrypt hash — raw password is never stored
    tier: str            # admin | power | standard
    assistant_name: str  # Per-user, included in JWT payload
    token_version: int   # Increment to immediately invalidate all active tokens


@dataclass
class RefreshToken:
    id: int | None   # None before insert — assigned by the database on first write
    user_id: str
    token_hash: str  # SHA-256 of the raw token — raw value is never stored
    expires_at: datetime
    revoked: bool    # True on logout or forced deauth — rows are never deleted


@dataclass
class Invite:
    id: int | None       # None before insert — assigned by the database on first write
    token_hash: str      # SHA-256 of the raw invite token
    username: str        # Pre-assigned by Admin
    tier: str            # Pre-assigned by Admin
    assistant_name: str  # Default name pre-assigned by Admin — user can change later
    expires_at: datetime  # 48 hours from issuance
    used: bool           # True once registration completes — cannot be reused
