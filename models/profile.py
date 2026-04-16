from models.base import Base
from sqlalchemy import Column, Enum, String, Float, Integer, DateTime
from sqlalchemy.sql import func
from utils.generate_id import generate_id



class Profile(Base):
    __tablename__ = "profile"

    id = Column(String(36), primary_key=True, default=generate_id)

    name = Column(String(100), nullable=False)
    gender = Column(String(20), nullable=False)

    gender_probability = Column(Float, nullable=False)
    sample_size = Column(Integer, nullable=False)

    age = Column(Integer, nullable=False)
    age_group = Column(
        Enum("child", "teenager", "adult", "senior", name="age_group_enum"),
        nullable=False,
    )

    country_id = Column(String(10), nullable=False)
    country_probability = Column(Float, nullable=False)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

