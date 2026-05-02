"""db/auth/models.py
Dataclasses representing the three auth database tables: users, refresh_tokens,
and invites. Plain data containers — no methods, no ORM coupling. The repository
layer is responsible for all reads and writes.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class User:
    """A registered JARVIS user account.

    username is the primary key and serves as user_id throughout the system.
    token_version is incremented on forced deauth to invalidate all active
    tokens without touching the token rows themselves.
    """

    username: str        # Primary key — used as user_id throughout the system
    password_hash: str   # bcrypt hash — raw password is never stored
    tier: str            # admin | power | standard
    assistant_name: str  # Per-user, included in JWT payload
    token_version: int   # Increment to immediately invalidate all active tokens
    disabled: bool       # True on forced deauth — blocks login and refresh regardless of credentials


@dataclass
class RefreshToken:
    """A refresh token row in the database.

    Rows are never deleted — revoked is set to True on logout or forced deauth.
    Expired rows are purged by the daily maintenance job.
    """

    id: int | None   # None before insert — assigned by the database on first write
    user_id: str
    token_hash: str  # SHA-256 of the raw token — raw value is never stored
    expires_at: datetime
    revoked: bool    # True on logout or forced deauth — rows are never deleted


@dataclass
class Invite:
    """A one-time token for registration or password reset.

    The same table holds both types — the type field disambiguates. Rows are
    marked used=True on consumption rather than deleted, so the audit trail
    is preserved. Expired rows are purged by the daily maintenance job.
    """

    id: int | None          # None before insert — assigned by the database on first write
    token_hash: str         # SHA-256 of the raw token
    type: str               # invite | password_reset
    username: str           # For invite: pre-assigned by Admin. For password_reset: existing account to unlock
    tier: str | None        # Pre-assigned by Admin — invite only, None for password_reset
    assistant_name: str | None  # Default name pre-assigned by Admin — invite only, None for password_reset
    expires_at: datetime    # 48 hours from issuance
    used: bool              # True once consumed — cannot be reused
