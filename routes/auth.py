
from datetime import datetime, timezone
import hashlib
import secrets
from fastapi.exceptions import HTTPException
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse
from urllib.parse import urlencode
from pydantic.main import BaseModel
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

GITHUB_CLIENT_ID = settings.GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET = settings.GITHUB_CLIENT_SECRET
FRONTEND_URL = settings.FRONTEND_URL
IS_PRODUCTION = settings.ENV == "production"
COOKIE_SAMESITE = "none" if IS_PRODUCTION else "lax"
COOKIE_SECURE = IS_PRODUCTION


@router.get("/github")
@limiter.limit("10/minute")
def github_login(request: Request):
    state                      = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce()   # ✅ backend generates for web

    # Store both so callback can retrieve code_verifier
    save_state(state=state, code_verifier=code_verifier, mode="web")

    params = urlencode({
        "client_id":             GITHUB_CLIENT_ID,
        "redirect_uri":          str(request.base_url) + "auth/github/callback",
        "scope":                 "read:user user:email",
        "state":                 state,
        "code_challenge":        code_challenge,        # ✅ sent to GitHub
        "code_challenge_method": "S256",
    })
    print(f"[LOGIN] base_url: {request.base_url}") 
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{params}")


@router.post("/register-state")
def register_state(payload: RegisterStatePayload):
    """
    CLI generates state + code_verifier locally.
    It registers them here before opening the browser so the
    callback endpoint can retrieve code_verifier when GitHub redirects back.
    """
    save_state(
        state=payload.state,
        code_verifier=payload.code_verifier,
        mode=payload.mode,
    )
    return JSONResponse( status_code=200, content=custom_content("success", message="state registered successfully"))


# ─── Shared callback — same endpoint, both flows ─────────────────────────────

@router.get("/github/callback")
@limiter.limit("10/minute")
async def github_callback(
    request: Request,
    code:  str,
    state: str,
    db:    Session = Depends(get_db),
):
    print(f"[CALLBACK] HIT — code={code[:10]} state={state[:10]}")
    # Validate state — gets back mode + code_verifier for whichever flow
    state_data = consume_state(state)
    print(f"[CALLBACK] state_data: {state_data}") 
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    mode          = state_data["mode"]
    code_verifier = state_data["code_verifier"]  # always present — both flows use PKCE
    print(f"[CALLBACK] mode={mode}")  

    # Exchange code + code_verifier with GitHub (PKCE)
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id":     GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code":          code,
                "code_verifier": code_verifier,   # ✅ always sent now
            },
            headers={"Accept": "application/json"},
        )

    github_token = token_res.json().get("access_token")
    if not github_token:
        raise HTTPException(status_code=502, detail="Failed to obtain GitHub token")
 
    async with httpx.AsyncClient() as client:
        user_res = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {github_token}"},
        )
    print(f"[CALLBACK] github_user: {user_res.json()}")

    github_user = user_res.json()
    if "id" not in github_user:
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub user info")

    user = upsert_user(db, github_user)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    access_token  = create_access_token(user.id)
    refresh_token = create_refresh_token(db, user.id)

    print(f"[CALLBACK] mode check — is cli: {mode == 'cli'}")
    # ── CLI → JSON response 
    
    if mode == "cli":
        from urllib.parse import urlencode
        params = urlencode({
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "username":      user.username,
        })
        # Redirect to CLI local server with tokens
        return RedirectResponse(url=f"http://localhost:9999/callback?{params}")
    

    # ── Web → cookies + redirect 
    response = RedirectResponse(url=f"{FRONTEND_URL}/dashboard")
    response.set_cookie(
        key="access_token",  value=access_token,
        httponly=True, samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=180,
        path="/",
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE,
        max_age=300,
        path="/",
    )
    return response


# Refresh

class RefreshPayload(BaseModel):
    refresh_token: str | None = None

@router.post("/refresh")
@limiter.limit("10/minute")
async def refresh_tokens(
    request: Request,
    db:      Session = Depends(get_db),
):
    # CLI sends in body, web sends via cookie
    raw_token = request.cookies.get("refresh_token")
    try:
        body      = await request.json()
        raw_token = raw_token or body.get("refresh_token")
    except Exception:
        pass

    if not raw_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    db_token   = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked    == False,
        RefreshToken.expires_at >  datetime.now(timezone.utc),
    ).first()

    if not db_token:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Invalidate immediately — one time use
    db_token.revoked = True
    db.commit()

    new_access  = create_access_token(db_token.user_id)
    new_refresh = create_refresh_token(db, db_token.user_id)

    # CLI — return JSON
    if raw_token not in (request.cookies.get("refresh_token"), None):
        return JSONResponse(content={
            "status":        "success",
            "access_token":  new_access,
            "refresh_token": new_refresh,
        })

    # Web — set new cookies
    response = JSONResponse(content={"status": "success"})
    response.set_cookie(
        key="access_token",  value=new_access,
        httponly=True, samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE, max_age=180,
        path="/",
    )
    response.set_cookie(
        key="refresh_token", value=new_refresh,
        httponly=True, samesite=COOKIE_SAMESITE,
        secure=COOKIE_SECURE, max_age=300,
        path="/",
    )
    return response


#Logout 

@router.post("/logout")
@limiter.limit("10/minute")
async def logout(request: Request, db: Session = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    try:
        body      = await request.json()
        raw_token = raw_token or body.get("refresh_token")
    except Exception:
        pass

    if raw_token:
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        db_token   = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        if db_token:
            db_token.revoked = True
            db.commit()

    response = JSONResponse(content={"status": "success"})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return response


#Me

@router.get("/me")
@limiter.limit("10/minute")
def me(request: Request, current_user: User = Depends(get_current_user)):
    return JSONResponse(content={
        "status": "success",
        "data": {
            "id":         str(current_user.id),
            "username":   current_user.username,
            "email":      current_user.email,
            "avatar_url": current_user.avatar_url,
            "role":       current_user.role,
        }
    })