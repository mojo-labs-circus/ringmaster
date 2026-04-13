from db.auth.models import Invite, RefreshToken, User
from db.auth.repository import AuthRepository


class PostgresAuthRepository(AuthRepository):
    # Full implementation deferred to Phase 5 — SQLite is the dev backend until then

    # --- Users ---

    def get_user(self, username: str) -> User | None:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    def create_user(self, user: User) -> None:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    def increment_token_version(self, username: str) -> None:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    def update_assistant_name(self, username: str, assistant_name: str) -> None:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    # --- Refresh Tokens ---

    def create_refresh_token(self, token: RefreshToken) -> RefreshToken:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    def revoke_refresh_token(self, token_hash: str) -> None:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    # --- Invites ---

    def create_invite(self, invite: Invite) -> Invite:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    def get_invite_by_hash(self, token_hash: str) -> Invite | None:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")

    def mark_invite_used(self, token_hash: str) -> None:
        raise NotImplementedError("PostgresAuthRepository is not implemented until Phase 5")
