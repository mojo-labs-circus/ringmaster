"""db/auth/repository.py
Abstract base class defining the AuthRepository interface. Both SQLiteAuthRepository
and PostgresAuthRepository implement this contract. Route handlers never touch
SQL directly — they call through this interface.
"""

from abc import ABC, abstractmethod

from db.auth.models import Invite, RefreshToken, User


class AuthRepository(ABC):
    """Interface for all auth data operations.

    The factory in db/auth/factory.py returns the correct implementation based
    on JARVIS_DB_BACKEND. SQLite is the dev backend; Postgres is production.
    """

    # --- Users ---

    @abstractmethod
    def get_user(self, username: str) -> User | None:
        # Used for login, token_version validation, and register
        ...

    @abstractmethod
    def create_user(self, user: User) -> None:
        # Called on registration after invite is validated
        ...

    @abstractmethod
    def increment_token_version(self, username: str) -> None:
        # Called on logout and forced deauth — immediately invalidates all active tokens
        ...

    @abstractmethod
    def update_assistant_name(self, username: str, assistant_name: str) -> None:
        # Called on PATCH /profile — updates the display name without touching token_version
        ...

    @abstractmethod
    def disable_user(self, username: str) -> None:
        # Called on forced deauth — blocks login and refresh regardless of credentials
        ...

    @abstractmethod
    def enable_user(self, username: str) -> None:
        # Called on password reset token consumption — re-enables the account
        ...

    @abstractmethod
    def update_password(self, username: str, password_hash: str) -> None:
        # Called on password reset and self-service password change
        ...

    # --- Refresh Tokens ---

    @abstractmethod
    def create_refresh_token(self, token: RefreshToken) -> RefreshToken:
        # Called on login — returns the same object with id set from the database
        ...

    @abstractmethod
    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        # Called on /auth/refresh — validates the token exists, is not revoked, has not expired
        ...

    @abstractmethod
    def revoke_refresh_token(self, token_hash: str) -> None:
        # Called on logout — marks the row revoked, rows are never deleted
        ...

    # --- Invites ---

    @abstractmethod
    def create_invite(self, invite: Invite) -> Invite:
        # Called on POST /auth/invite — returns the same object with id set from the database
        ...

    @abstractmethod
    def get_invite_by_hash(self, token_hash: str) -> Invite | None:
        # Called on register — validates the token exists, is not used, has not expired
        ...

    @abstractmethod
    def mark_invite_used(self, token_hash: str) -> None:
        # Called on register after user is created — prevents the token being reused
        ...
