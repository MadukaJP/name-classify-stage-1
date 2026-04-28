
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
import jwt, hashlib, secrets
from core.config import settings
from models.refresh_token import RefreshToken

SECRET_KEY = settings.SECRET_KEY

def create_access_token(user_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=3),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def create_refresh_token(db: Session, user_id: str) -> str:
    raw_token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Store hash in DB (never the raw token)
    db_token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db.add(db_token)
    db.commit()
    return raw_token  # send this to the client

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

    