import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

ENV = os.getenv("ENV", "development")

# Pick database URL based on environment
DATABASE_URL = (
    os.getenv("LOCAL_DATABASE_URL")
    if ENV == "development"
    else os.getenv("PROD_DATABASE_URL")
)

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in environment variables")

engine = create_engine(DATABASE_URL, connect_args={"options": "-c timezone=utc"})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()  
