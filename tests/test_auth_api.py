import importlib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPLICATIONS_DB", str(tmp_path / "app.db"))
    monkeypatch.setenv("OWNER_EMAIL", "owner@example.com")
    monkeypatch.setenv("ALLOWED_EMAILS", "friend@example.com, Second@Example.com")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://localhost:3000")
    import a2a.db as db
    importlib.reload(db)
    import a2a.auth as auth
    importlib.reload(auth)
    return db, auth


@pytest.fixture
def client(env, monkeypatch):
    db, auth = env
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth.router)
    return TestClient(app, follow_redirects=False), db, auth


def google_returns(monkeypatch, auth, email, verified=True, name="Friend"):
    async def fake(request):
        return {"userinfo": {"email": email, "email_verified": verified, "name": name, "picture": ""}}
    monkeypatch.setattr(auth.oauth.google, "authorize_access_token", fake)


def test_callback_creates_user_and_session_for_allowed_email(client, monkeypatch):
    c, db, auth = client
    google_returns(monkeypatch, auth, "friend@example.com")
    resp = c.get("/api/auth/callback")
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "http://localhost:3000/"
    me = c.get("/api/auth/me").json()
    assert me["email"] == "friend@example.com"
    assert me["is_owner"] is False


def test_callback_rejects_uninvited_email(client, monkeypatch):
    c, db, auth = client
    google_returns(monkeypatch, auth, "stranger@example.com")
    resp = c.get("/api/auth/callback")
    assert "auth_error=not_invited" in resp.headers["location"]
    assert "stranger%40example.com" in resp.headers["location"]
    assert db.list_users() == []
    assert c.get("/api/auth/me").status_code == 401


def test_callback_rejects_unverified_email(client, monkeypatch):
    c, db, auth = client
    google_returns(monkeypatch, auth, "friend@example.com", verified=False)
    resp = c.get("/api/auth/callback")
    assert "auth_error=not_invited" in resp.headers["location"]
    assert db.list_users() == []


def test_me_401_without_session(client):
    c, *_ = client
    assert c.get("/api/auth/me").status_code == 401


def test_removed_from_allowlist_gets_403_on_next_request(client, monkeypatch):
    c, db, auth = client
    google_returns(monkeypatch, auth, "friend@example.com")
    c.get("/api/auth/callback")
    monkeypatch.setenv("ALLOWED_EMAILS", "second@example.com")
    resp = c.get("/api/auth/me")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "not_invited"


def test_logout_clears_session(client, monkeypatch):
    c, db, auth = client
    google_returns(monkeypatch, auth, "friend@example.com")
    c.get("/api/auth/callback")
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401


def test_owner_flag_from_owner_email(client, monkeypatch):
    c, db, auth = client
    google_returns(monkeypatch, auth, "Owner@Example.com", name="Rohit")
    c.get("/api/auth/callback")
    me = c.get("/api/auth/me").json()
    assert me["is_owner"] is True
    assert me["email"] == "owner@example.com"
