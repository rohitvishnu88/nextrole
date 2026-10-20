"""Google sign-in for invited users, kept in a signed session cookie."""
import os
from dataclasses import dataclass
from urllib.parse import quote

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from a2a import db

router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    picture: str
    is_owner: bool


def owner_email() -> str:
    return os.environ.get("OWNER_EMAIL", "").strip().lower()


def allowed_emails() -> set:
    emails = {e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()}
    if owner_email():
        emails.add(owner_email())
    return emails


def is_allowed(email: str) -> bool:
    return email.strip().lower() in allowed_emails()


def _base_url() -> str:
    return os.environ.get("PUBLIC_BASE_URL", "http://localhost:3000").rstrip("/")


def current_user(request: Request) -> User:
    user_id = request.session.get("user_id")
    row = db.get_user(user_id) if user_id else None
    if row is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    # Checked on every request so removing someone from the invite list takes effect at once.
    if not is_allowed(row["email"]):
        raise HTTPException(status_code=403, detail={"code": "not_invited", "email": row["email"]})
    return User(row["id"], row["email"], row["name"] or "", row["picture"] or "", row["email"] == owner_email())


@router.get("/login")
async def login(request: Request):
    return await oauth.google.authorize_redirect(request, f"{_base_url()}/api/auth/callback")


@router.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        return RedirectResponse(f"{_base_url()}/?auth_error=failed")
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("email_verified") or not is_allowed(email):
        return RedirectResponse(f"{_base_url()}/?auth_error=not_invited&email={quote(email)}")
    user = db.upsert_user(email, info.get("name") or "", info.get("picture") or "", email == owner_email())
    request.session["user_id"] = user["id"]
    return RedirectResponse(f"{_base_url()}/")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.get("/me")
def me(request: Request):
    user = current_user(request)
    return {"email": user.email, "name": user.name, "picture": user.picture, "is_owner": user.is_owner}
