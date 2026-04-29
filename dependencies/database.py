from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"options": "-c timezone=utc"},
    pool_pre_ping=True,  # tests connection before using it
    pool_recycle=300,  # recycle connections every 5 minutes
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
