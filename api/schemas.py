from pydantic import BaseModel


# --- Login ---

class LoginRequest(BaseModel):
    username: str
    password: str
    client_type: str  # tui | web | mobile — baked into the JWT


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_at: str  # ISO 8601 datetime string


# --- Refresh ---

class RefreshRequest(BaseModel):
    refresh_token: str
    client_type: str  # tui | web | mobile — client knows its own type, no need to store in refresh_tokens


class RefreshResponse(BaseModel):
    access_token: str
    access_expires_at: str  # ISO 8601 datetime string


# --- Logout ---

class LogoutRequest(BaseModel):
    refresh_token: str  # identifies which refresh_tokens row to revoke


# --- Invite ---

class InviteRequest(BaseModel):
    username: str
    tier: str           # admin | power | standard
    assistant_name: str


class InviteResponse(BaseModel):
    token: str  # raw invite token — only time it exists in plaintext, share immediately


# --- Register ---

class RegisterRequest(BaseModel):
    token: str      # raw invite token
    password: str
