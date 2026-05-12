import bcrypt
import hashlib
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from api.server import app
from db.auth.factory import get_auth_repository
from db.auth.models import Invite, RefreshToken, User
from db.auth.sqlite import SQLiteAuthRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(test_db):
    return SQLiteAuthRepository(test_db["auth"])


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_auth_repository] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(repo):
    _make_user(repo, username="admin", tier="admin")
    return "admin", "password123"


@pytest.fixture
def standard_user(repo):
    _make_user(repo, username="standard", tier="standard")
    return "standard", "password123"


@pytest.fixture
def admin_token(client, admin_user):
    username, password = admin_user
    return _login(client, username, password)["access_token"]


@pytest.fixture
def standard_login(client, standard_user):
    username, password = standard_user
    return _login(client, username, password)


@pytest.fixture
def invite_token(client, admin_token):
    return client.post(
        "/auth/invite",
        json={"type": "invite", "username": "bob", "tier": "standard", "assistant_name": "Jarvis"},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["token"]


@pytest.fixture
def reset_token(client, admin_token, standard_user):
    username, _ = standard_user
    return client.post(
        "/auth/invite",
        json={"type": "password_reset", "username": username},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["token"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(repo, username="standard", password="password123", tier="standard", disabled=False):
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    repo.create_user(User(
        username=username,
        password_hash=password_hash,
        tier=tier,
        assistant_name="Jarvis",
        token_version=0,
        disabled=disabled,
    ))


def _login(client, username="standard", password="password123"):
    return client.post("/auth/login", json={
        "username": username,
        "password": password,
        "client_type": "tui",
    }).json()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_success(client, standard_user):
    response = client.post("/auth/login", json={
        "username": "standard",
        "password": "password123",
        "client_type": "tui",
    })

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert "access_expires_at" in body


def test_login_wrong_password(client, standard_user):
    response = client.post("/auth/login", json={
        "username": "standard",
        "password": "wrongpassword",
        "client_type": "tui",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


def test_login_disabled_account(client, repo):
    _make_user(repo, disabled=True)

    response = client.post("/auth/login", json={
        "username": "standard",
        "password": "password123",
        "client_type": "tui",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Account disabled. Contact admin to restore access."


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

def test_refresh_success(client, standard_login):
    response = client.post("/auth/refresh", json={
        "refresh_token": standard_login["refresh_token"],
        "client_type": "tui",
    })

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "access_expires_at" in body


def test_refresh_invalid_token(client):
    response = client.post("/auth/refresh", json={
        "refresh_token": "notarealtoken",
        "client_type": "tui",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_refresh_revoked_token(client, standard_login):
    client.post(
        "/auth/logout",
        json={"refresh_token": standard_login["refresh_token"]},
        headers={"Authorization": f"Bearer {standard_login['access_token']}"},
    )

    response = client.post("/auth/refresh", json={
        "refresh_token": standard_login["refresh_token"],
        "client_type": "tui",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid refresh token"


def test_refresh_disabled_account(client, repo, standard_login, standard_user):
    username, _ = standard_user
    repo.disable_user(username)

    response = client.post("/auth/refresh", json={
        "refresh_token": standard_login["refresh_token"],
        "client_type": "tui",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Account disabled. Contact admin to restore access."


def test_refresh_expired_token(client, repo, standard_user):
    username, _ = standard_user
    raw_token = "expiredrawtoken"
    repo.create_refresh_token(RefreshToken(
        id=None,
        user_id=username,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime(2020, 1, 1, 0, 0, 0),
        revoked=False,
    ))

    response = client.post("/auth/refresh", json={
        "refresh_token": raw_token,
        "client_type": "tui",
    })

    assert response.status_code == 401
    assert response.json()["detail"] == "Refresh token expired"


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_success(client, standard_login):
    response = client.post(
        "/auth/logout",
        json={"refresh_token": standard_login["refresh_token"]},
        headers={"Authorization": f"Bearer {standard_login['access_token']}"},
    )

    assert response.status_code == 200


def test_logout_unauthenticated(client):
    response = client.post(
        "/auth/logout",
        json={"refresh_token": "irrelevant"},
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Invite
# ---------------------------------------------------------------------------

def test_invite_success(client, admin_token):
    response = client.post(
        "/auth/invite",
        json={"type": "invite", "username": "bob", "tier": "standard", "assistant_name": "Jarvis"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert "token" in response.json()


def test_invite_non_admin_rejected(client, standard_login):
    response = client.post(
        "/auth/invite",
        json={"type": "invite", "username": "bob", "tier": "standard", "assistant_name": "Jarvis"},
        headers={"Authorization": f"Bearer {standard_login['access_token']}"},
    )

    assert response.status_code == 403


def test_invite_missing_fields(client, admin_token):
    response = client.post(
        "/auth/invite",
        json={"type": "invite", "username": "bob", "tier": None, "assistant_name": None},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "tier and assistant_name are required for invite tokens"


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def test_register_success(client, invite_token):
    response = client.post("/auth/register", json={
        "token": invite_token,
        "password": "bobpassword123",
    })

    assert response.status_code == 200
    assert _login(client, username="bob", password="bobpassword123")["access_token"] is not None


def test_register_invalid_token(client):
    response = client.post("/auth/register", json={
        "token": "notavalidtoken",
        "password": "somepassword123",
    })

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid invite token"


def test_register_expired_token(client, repo):
    raw_token = "expiredinvitetoken"
    repo.create_invite(Invite(
        id=None,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        type="invite",
        username="bob",
        tier="standard",
        assistant_name="Jarvis",
        expires_at=datetime(2020, 1, 1, 0, 0, 0),
        used=False,
    ))

    response = client.post("/auth/register", json={"token": raw_token, "password": "bobpassword123"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invite token expired"


def test_register_used_token(client, invite_token):
    client.post("/auth/register", json={"token": invite_token, "password": "bobpassword123"})

    response = client.post("/auth/register", json={"token": invite_token, "password": "bobpassword123"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid invite token"


# ---------------------------------------------------------------------------
# Reset password
# ---------------------------------------------------------------------------

def test_reset_success(client, reset_token, standard_user):
    username, _ = standard_user

    response = client.post("/auth/reset", json={"token": reset_token, "password": "newpassword456"})

    assert response.status_code == 200
    assert _login(client, username, "newpassword456")["access_token"] is not None


def test_reset_invalid_token(client):
    response = client.post("/auth/reset", json={
        "token": "notavalidtoken",
        "password": "newpassword456",
    })

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid reset token"


def test_reset_expired_token(client, repo, standard_user):
    username, _ = standard_user
    raw_token = "expiredresettoken"
    repo.create_invite(Invite(
        id=None,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        type="password_reset",
        username=username,
        tier=None,
        assistant_name=None,
        expires_at=datetime(2020, 1, 1, 0, 0, 0),
        used=False,
    ))

    response = client.post("/auth/reset", json={"token": raw_token, "password": "newpassword456"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Reset token expired"


def test_reset_used_token(client, reset_token):
    client.post("/auth/reset", json={"token": reset_token, "password": "newpassword456"})

    response = client.post("/auth/reset", json={"token": reset_token, "password": "differentpassword"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid reset token"


def test_reset_wrong_type(client, invite_token):
    # invite token used against the reset endpoint — type mismatch should be rejected
    response = client.post("/auth/reset", json={"token": invite_token, "password": "newpassword456"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid reset token"


def test_reset_same_password(client, reset_token, standard_user):
    _, password = standard_user

    response = client.post("/auth/reset", json={"token": reset_token, "password": password})

    assert response.status_code == 400
    assert response.json()["detail"] == "New password must differ from current password"


def test_reset_reenables_disabled_account(client, repo, admin_token, standard_user):
    username, _ = standard_user
    repo.disable_user(username)
    token = client.post(
        "/auth/invite",
        json={"type": "password_reset", "username": username},
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["token"]

    assert client.post("/auth/reset", json={"token": token, "password": "newpassword456"}).status_code == 200
    assert _login(client, username, "newpassword456")["access_token"] is not None


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------

def test_change_password_success(client, standard_user, standard_login):
    username, current_password = standard_user

    response = client.post(
        "/auth/password",
        json={"current_password": current_password, "new_password": "newpassword456"},
        headers={"Authorization": f"Bearer {standard_login['access_token']}"},
    )

    assert response.status_code == 200
    assert _login(client, username, "newpassword456")["access_token"] is not None


def test_change_password_wrong_current(client, standard_login):
    response = client.post(
        "/auth/password",
        json={"current_password": "wrongpassword", "new_password": "newpassword456"},
        headers={"Authorization": f"Bearer {standard_login['access_token']}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Current password incorrect"


def test_change_password_unauthenticated(client):
    response = client.post(
        "/auth/password",
        json={"current_password": "password123", "new_password": "newpassword456"},
    )

    assert response.status_code == 401
