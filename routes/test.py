from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from dependencies.database import get_db
from dependencies.limiter import limiter
from models.user import User
from utils.tokens import create_access_token, create_refresh_token

router = APIRouter()


def _get_or_create_test_user(db: Session, role: str) -> User:
    username = f"test_{role}_user"
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            github_id=f"test_{role}_github_id_{role}",
            username=username,
            email=f"{role}@test.local",
            avatar_url="",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/test-token")
@limiter.limit("10/minute")
def test_token(request: Request, db: Session = Depends(get_db)):
    analyst = _get_or_create_test_user(db, role="analyst")
    access = create_access_token(analyst.id)
    refresh = create_refresh_token(db, analyst.id)
    return JSONResponse(
        content={
            "status": "success",
            "access_token": access,
            "refresh_token": refresh,
            "user": {
                "id": str(analyst.id),
                "username": analyst.username,
                "role": analyst.role,
            },
        }
    )
