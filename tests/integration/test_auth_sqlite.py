from datetime import datetime, timezone

import pytest

from db.auth.models import Invite, RefreshToken, User
from db.auth.sqlite import SQLiteAuthRepository


def test_create_and_get_user(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    user = User(
        username="alice",
        password_hash="$2b$12$somehash",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    )

    repo.create_user(user)
    result = repo.get_user("alice")

    assert result is not None
    assert result.username == "alice"
    assert result.password_hash == "$2b$12$somehash"
    assert result.tier == "standard"
    assert result.assistant_name == "Jarvis"
    assert result.token_version == 0
    assert result.disabled is False


def test_get_user_missing(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])

    result = repo.get_user("nobody")

    assert result is None


def test_increment_token_version(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    repo.create_user(User(
        username="alice",
        password_hash="$2b$12$somehash",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    ))

    repo.increment_token_version("alice")
    result = repo.get_user("alice")

    assert result.token_version == 1


def test_update_assistant_name(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    repo.create_user(User(
        username="alice",
        password_hash="$2b$12$somehash",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    ))

    repo.update_assistant_name("alice", "Alfred")
    result = repo.get_user("alice")

    assert result.assistant_name == "Alfred"


def test_disable_user(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    repo.create_user(User(
        username="alice",
        password_hash="$2b$12$somehash",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    ))

    repo.disable_user("alice")
    result = repo.get_user("alice")

    assert result.disabled is True


def test_enable_user(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    repo.create_user(User(
        username="alice",
        password_hash="$2b$12$somehash",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=True,
    ))

    repo.enable_user("alice")
    result = repo.get_user("alice")

    assert result.disabled is False


def test_update_password(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    repo.create_user(User(
        username="alice",
        password_hash="$2b$12$oldhash",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    ))

    repo.update_password("alice", "$2b$12$newhash")
    result = repo.get_user("alice")

    assert result.password_hash == "$2b$12$newhash"


def test_create_and_get_refresh_token(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    repo.create_user(User(
        username="alice",
        password_hash="$2b$12$somehash",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    ))
    token = RefreshToken(
        id=None,
        user_id="alice",
        token_hash="abc123hash",
        expires_at=datetime(2026, 12, 31, 0, 0, 0),
        revoked=False,
    )

    returned = repo.create_refresh_token(token)
    result = repo.get_refresh_token_by_hash("abc123hash")

    assert returned.id is not None
    assert result is not None
    assert result.id == returned.id
    assert result.user_id == "alice"
    assert result.token_hash == "abc123hash"
    assert result.expires_at == datetime(2026, 12, 31, 0, 0, 0)
    assert result.revoked is False


def test_get_refresh_token_missing(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])

    result = repo.get_refresh_token_by_hash("doesnotexist")

    assert result is None


def test_revoke_refresh_token(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    repo.create_user(User(
        username="alice",
        password_hash="$2b$12$somehash",
        tier="standard",
        assistant_name="Jarvis",
        token_version=0,
        disabled=False,
    ))
    repo.create_refresh_token(RefreshToken(
        id=None,
        user_id="alice",
        token_hash="abc123hash",
        expires_at=datetime(2026, 12, 31, 0, 0, 0),
        revoked=False,
    ))

    repo.revoke_refresh_token("abc123hash")
    result = repo.get_refresh_token_by_hash("abc123hash")

    assert result.revoked is True


def test_create_and_get_invite(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    invite = Invite(
        id=None,
        token_hash="invitehash",
        type="invite",
        username="bob",
        tier="standard",
        assistant_name="Jarvis",
        expires_at=datetime(2026, 12, 31, 0, 0, 0),
        used=False,
    )

    returned = repo.create_invite(invite)
    result = repo.get_invite_by_hash("invitehash")

    assert returned.id is not None
    assert result is not None
    assert result.id == returned.id
    assert result.token_hash == "invitehash"
    assert result.type == "invite"
    assert result.username == "bob"
    assert result.tier == "standard"
    assert result.assistant_name == "Jarvis"
    assert result.expires_at == datetime(2026, 12, 31, 0, 0, 0)
    assert result.used is False


def test_get_invite_missing(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])

    result = repo.get_invite_by_hash("doesnotexist")

    assert result is None


def test_mark_invite_used(test_db):
    repo = SQLiteAuthRepository(test_db["auth"])
    repo.create_invite(Invite(
        id=None,
        token_hash="invitehash",
        type="invite",
        username="bob",
        tier="standard",
        assistant_name="Jarvis",
        expires_at=datetime(2026, 12, 31, 0, 0, 0),
        used=False,
    ))

    repo.mark_invite_used("invitehash")
    result = repo.get_invite_by_hash("invitehash")

    assert result.used is True
