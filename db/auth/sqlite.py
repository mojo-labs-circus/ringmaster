import sqlite3
from datetime import datetime

from db.auth.models import Invite, RefreshToken, User
from db.auth.repository import AuthRepository


class SQLiteAuthRepository(AuthRepository):

    def __init__(self, db_path: str) -> None:
        # Path to auth.db — connection is opened per method, not held open,
        # to avoid SQLite's cross-thread connection issues with FastAPI
        self.db_path = db_path

    # --- Users ---

    def get_user(self, username: str) -> User | None:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT username, password_hash, tier, assistant_name, token_version "
            "FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()
        connection.close()
        if row is None:
            return None
        return User(
            username=row[0],
            password_hash=row[1],
            tier=row[2],
            assistant_name=row[3],
            token_version=row[4],
        )

    def create_user(self, user: User) -> None:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash, tier, assistant_name, token_version) "
            "VALUES (?, ?, ?, ?, ?)",
            (user.username, user.password_hash, user.tier, user.assistant_name, user.token_version),
        )
        connection.commit()
        connection.close()

    def increment_token_version(self, username: str) -> None:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE username = ?",
            (username,),
        )
        connection.commit()
        connection.close()

    # --- Refresh Tokens ---

    def create_refresh_token(self, token: RefreshToken) -> RefreshToken:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at, revoked) "
            "VALUES (?, ?, ?, ?)",
            (token.user_id, token.token_hash, token.expires_at.isoformat(), int(token.revoked)),
        )
        connection.commit()
        token.id = cursor.lastrowid  # stamp the database-assigned id back onto the dataclass
        connection.close()
        return token

    def get_refresh_token_by_hash(self, token_hash: str) -> RefreshToken | None:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, user_id, token_hash, expires_at, revoked "
            "FROM refresh_tokens WHERE token_hash = ?",
            (token_hash,),
        )
        row = cursor.fetchone()
        connection.close()
        if row is None:
            return None
        return RefreshToken(
            id=row[0],
            user_id=row[1],
            token_hash=row[2],
            expires_at=datetime.fromisoformat(row[3]),
            revoked=bool(row[4]),
        )

    def revoke_refresh_token(self, token_hash: str) -> None:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?",
            (token_hash,),
        )
        connection.commit()
        connection.close()

    # --- Invites ---

    def create_invite(self, invite: Invite) -> Invite:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO invites (token_hash, username, tier, assistant_name, expires_at, used) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                invite.token_hash,
                invite.username,
                invite.tier,
                invite.assistant_name,
                invite.expires_at.isoformat(),
                int(invite.used),
            ),
        )
        connection.commit()
        invite.id = cursor.lastrowid  # stamp the database-assigned id back onto the dataclass
        connection.close()
        return invite

    def get_invite_by_hash(self, token_hash: str) -> Invite | None:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, token_hash, username, tier, assistant_name, expires_at, used "
            "FROM invites WHERE token_hash = ?",
            (token_hash,),
        )
        row = cursor.fetchone()
        connection.close()
        if row is None:
            return None
        return Invite(
            id=row[0],
            token_hash=row[1],
            username=row[2],
            tier=row[3],
            assistant_name=row[4],
            expires_at=datetime.fromisoformat(row[5]),
            used=bool(row[6]),
        )

    def mark_invite_used(self, token_hash: str) -> None:
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE invites SET used = 1 WHERE token_hash = ?",
            (token_hash,),
        )
        connection.commit()
        connection.close()
