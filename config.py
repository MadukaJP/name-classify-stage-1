import os
from dotenv import load_dotenv

load_dotenv()

def get_database_url() -> str:
    env = os.getenv("ENV", "development")

    db_url = (
        os.getenv("LOCAL_DATABASE_URL")
        if env == "development"
        else os.getenv("PROD_DATABASE_URL")
    )

    if not db_url:
        raise ValueError("DATABASE_URL is not set in environment variables")

    return db_url



DATABASE_URL = get_database_url()