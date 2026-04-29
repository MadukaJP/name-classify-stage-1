from datetime import datetime, timezone
import hashlib
import secrets
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
import httpx
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from core.config import settings
from dependencies.auth import get_current_user
from dependencies.database import get_db
from dependencies.limiter import limiter
from models.refresh_token import RefreshToken
from models.user import User
from pydantic_schemas.register_state_payload import RegisterStatePayload
from services.user_service import upsert_user
from utils.custom_content import custom_content
from utils.state_store import consume_state, generate_pkce, save_state
from utils.tokens import create_access_token, create_refresh_token

router = APIRouter()


def github_client(mode: str) -> dict:
    if mode == "cli":
        return {
            "client_id": settings.GITHUB_CLIENT_ID_CLI,
            "client_secret": settings.GITHUB_CLIENT_SECRET_CLI,
        }
    return {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
    }


GITHUB_CLIENT_SECRET = settings.GITHUB_CLIENT_SECRET
FRONTEND_URL = settings.FRONTEND_URL.rstrip("/")
IS_PRODUCTION = settings.ENV == "production"
COOKIE_SAMESITE = "none" if IS_PRODUCTION else "lax"
COOKIE_SECURE = IS_PRODUCTION
ACCESS_TOKEN_SECONDS = 180
REFRESH_TOKEN_SECONDS = 300
CSRF_COOKIE_NAME = "csrf_token"


class CLIAuthPayload(BaseModel):
    code: str
    code_verifier: str
    redirect_uri: str
    state: str | None = None

    @field_validator("redirect_uri")
    @classmethod
    def validate_local_redirect_uri(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("CLI redirect_uri must use localhost")
        if not parsed.port:
            raise ValueError("CLI redirect_uri must include a port")
        return value


def set_session_cookies(
    response: JSONResponse | RedirectResponse, access_token: str, refresh_token: str
) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=ACCESS_TOKEN_SECONDS,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=REFRESH_TOKEN_SECONDS,
        path="/",
    )
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=secrets.token_urlsafe(32),
        httponly=False,
        samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=REFRESH_TOKEN_SECONDS,
        path="/",
    )


def clear_session_cookies(response: JSONResponse) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


async def exchange_github_code(
    code: str, code_verifier: str, redirect_uri: str, mode: str
) -> str:
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": github_client(mode).get("client_id"),
                "client_secret": github_client(mode).get("client_secret"),
                "code": code,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )

    try:
        token_body = token_res.json()
    except ValueError:
        token_body = {}

    github_token = token_body.get("access_token")
    if token_res.status_code >= 400 or not github_token:
        raise HTTPException(status_code=502, detail="Failed to obtain GitHub token")

    return github_token


async def fetch_github_user(github_token: str) -> dict:
    headers = {"Authorization": f"Bearer {github_token}", "Accept": "application/json"}
    async with httpx.AsyncClient() as client:
        user_res = await client.get("https://api.github.com/user", headers=headers)
        if user_res.status_code >= 400:
            raise HTTPException(
                status_code=502, detail="Failed to fetch GitHub user info"
            )

        github_user = user_res.json()
        if "id" not in github_user:
            raise HTTPException(
                status_code=502, detail="Failed to fetch GitHub user info"
            )

        if not github_user.get("email"):
            email_res = await client.get(
                "https://api.github.com/user/emails", headers=headers
            )
            if email_res.status_code == 200:
                emails = email_res.json()
                primary = next(
                    (
                        email
                        for email in emails
                        if email.get("primary") and email.get("verified")
                    ),
                    None,
                )
                fallback = next(
                    (email for email in emails if email.get("verified")), None
                )
                selected = primary or fallback
                if selected:
                    github_user["email"] = selected.get("email")

    return github_user


async def authenticate_with_github(
    db: Session,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    mode: str,
) -> User:
    github_token = await exchange_github_code(code, code_verifier, redirect_uri, mode)
    github_user = await fetch_github_user(github_token)
    user = upsert_user(db, github_user)

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    return user


def issue_token_pair(db: Session, user: User) -> tuple[str, str]:
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(db, user.id)
    return access_token, refresh_token


@router.get("/github")
@limiter.limit("10/minute")
def github_login(request: Request):
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce()
    redirect_uri = str(request.url_for("github_callback"))

    save_state(state=state, code_verifier=code_verifier, mode="web")

    params = urlencode(
        {
            "client_id": github_client("web").get("client_id"),
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@router.post("/register-state")
@limiter.limit("10/minute")
def register_state(request: Request, payload: RegisterStatePayload):
    save_state(
        state=payload.state,
        code_verifier=payload.code_verifier,
        mode=payload.mode,
    )
    return JSONResponse(
        status_code=200,
        content=custom_content("success", message="state registered successfully"),
    )


@router.get("/github/callback")
@limiter.limit("10/minute")
async def github_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    state_data = consume_state(state)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    if state_data.get("mode") != "web":
        raise HTTPException(status_code=400, detail="Invalid OAuth flow")

    user = await authenticate_with_github(
        db=db,
        code=code,
        code_verifier=state_data["code_verifier"],
        redirect_uri=str(request.url_for("github_callback")),
        mode="web",
    )
    access_token, refresh_token = issue_token_pair(db, user)

    response = RedirectResponse(url=f"{FRONTEND_URL}/dashboard")
    set_session_cookies(response, access_token, refresh_token)
    return response


@router.post("/github/cli/callback")
@limiter.limit("10/minute")
async def github_cli_callback(
    request: Request,
    payload: CLIAuthPayload,
    db: Session = Depends(get_db),
):
    user = await authenticate_with_github(
        db=db,
        code=payload.code,
        code_verifier=payload.code_verifier,
        redirect_uri=payload.redirect_uri,
        mode="cli",
    )
    access_token, refresh_token = issue_token_pair(db, user)

    return JSONResponse(
        content={
            "status": "success",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "role": user.role,
            },
        }
    )


@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh_tokens(
    request: Request,
    db: Session = Depends(get_db),
):
    cookie_refresh_token = request.cookies.get("refresh_token")
    body_refresh_token = None
    try:
        body = await request.json()
        body_refresh_token = body.get("refresh_token")
    except Exception:
        pass

    raw_token = cookie_refresh_token or body_refresh_token
    if not raw_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    db_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    db_token.revoked = True
    db.commit()

    new_access = create_access_token(db_token.user_id)
    new_refresh = create_refresh_token(db, db_token.user_id)

    if body_refresh_token and not cookie_refresh_token:
        return JSONResponse(
            content={
                "status": "success",
                "access_token": new_access,
                "refresh_token": new_refresh,
            }
        )

    response = JSONResponse(content={"status": "success"})
    set_session_cookies(response, new_access, new_refresh)
    return response


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, db: Session = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    try:
        body = await request.json()
        raw_token = raw_token or body.get("refresh_token")
    except Exception:
        pass

    if raw_token:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        db_token = (
            db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
        )
        if db_token:
            db_token.revoked = True
            db.commit()

    response = JSONResponse(content={"status": "success"})
    clear_session_cookies(response)
    return response


@router.get("/me")
@limiter.limit("10/minute")
def me(request: Request, current_user: User = Depends(get_current_user)):
    return JSONResponse(
        content={
            "status": "success",
            "data": {
                "id": str(current_user.id),
                "username": current_user.username,
                "email": current_user.email,
                "avatar_url": current_user.avatar_url,
                "role": current_user.role,
            },
        }
    )
