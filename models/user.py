from models.base import Base
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from utils.generate_id import generate_id


class User(Base):
    __tablename__ = "users"

    id         = Column(UUID(as_uuid=True),  primary_key=True, default=generate_id)
    github_id  = Column(String(50), unique=True, nullable=False)
    username   = Column(String(100), nullable=False)
    email      = Column(String(200))
    avatar_url = Column(String(500))
    role       = Column(String(20), nullable=False, default="analyst")  # admin | analyst
    is_active  = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())