from sqlalchemy.orm import validates
from models.base import Base
from sqlalchemy import VARCHAR, Column, String, Float, Integer, DateTime
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from utils.country_utils import get_country_name_from_id
from utils.generate_id import generate_id


class Profile(Base):
    __tablename__ = "profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=generate_id)
    # Database Requirements
    name = Column(String(100), nullable=False, unique=True)
    gender = Column(String(20), nullable=False, index=True)
    gender_probability = Column(Float, nullable=False, index=True)

    age = Column(Integer, nullable=False, index=True)
    age_group = Column(String(20), nullable=False, index=True)

    country_id = Column(VARCHAR(2), nullable=False, index=True)
    country_name = Column(String(100), nullable=False)
    country_probability = Column(Float, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    @validates("gender")
    def validate_gender(self, key, value):
        if value.lower() not in ["male", "female"]:
            raise ValueError("Gender must be 'male' or 'female'")
        return value.lower()

    @validates("age_group")
    def validate_age_group(self, key, value):
        allowed = ["child", "teenager", "adult", "senior"]
        if value.lower() not in allowed:
            raise ValueError(f"Age group must be one of {allowed}")
        return value.lower()

    @validates("country_id")
    def update_country_name(self, key, value):
        if not getattr(self, "country_name", None) and value:
            country_name = get_country_name_from_id(value)
            if not country_name:
                raise ValueError("country_id must map to a valid country name")
            self.country_name = country_name
        return value.upper()
