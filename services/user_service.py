
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from core.config import settings
from models.user import User


admin_usernames_raw = settings.ADMIN_GITHUB_USERNAMES or ""
if not isinstance(admin_usernames_raw, str):
    admin_usernames_raw = str(admin_usernames_raw)
    
ADMIN_USERNAMES = {
    u.strip().lower()
    for u in admin_usernames_raw.split(",")
    if u.strip()
}

def upsert_user(db: Session, github_user: dict) -> User:
    username = github_user["login"]
    user     = db.query(User).filter(
        User.github_id == str(github_user["id"])
    ).first()

    if user:
        # DO NOT downgrade existing users unintentionally
        if username.lower() in ADMIN_USERNAMES:
            user.role = "admin"

        user.username      = username
        user.email         = github_user.get("email")
        user.avatar_url    = github_user.get("avatar_url")
        user.last_login_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(user)
        return user
    # Determine role — whitelist takes priority
    if username.lower() in ADMIN_USERNAMES:
        role = "admin"
    else:
        user_count = db.query(User).count()
        role       = "admin" if user_count == 0 else "analyst"

    if user:
        user.username      = username
        user.email         = github_user.get("email")
        user.avatar_url    = github_user.get("avatar_url")
        user.role          = role   # re-evaluate on every login
        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
        return user

    user = User(
        github_id     = str(github_user["id"]),
        username      = username,
        email         = github_user.get("email"),
        avatar_url    = github_user.get("avatar_url"),
        role          = role,
        is_active     = True,
        last_login_at = datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user