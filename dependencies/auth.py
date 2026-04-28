# dependencies/auth.py
import uuid
from fastapi import Depends, HTTPException, Request, Cookie
from typing import Annotated
import jwt
from sqlalchemy.orm import Session

from dependencies.database import get_db
from models.user import User
from utils.tokens import decode_access_token

def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    # reads from either Bearer header (CLI) or cookie (web)
) -> User:
    token = None

    # Try Authorization header first (CLI)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    # Fall back to cookie (web portal)
    if not token:
        token = request.cookies.get("access_token")

    print(f"[AUTH] token found: {bool(token)}")
    print(f"[AUTH] token value: {token[:20] if token else None}")
    print(f"[AUTH] cookies: {dict(request.cookies)}")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
   
    user_id = uuid.UUID(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Access denied")

    return user


# Role enforcement — compose on top of get_current_user
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user