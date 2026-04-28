from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENV : str
    SECRET_KEY : str
    ADMIN_GITHUB_USERNAMES : str | None = None
    GITHUB_CLIENT_ID : str
    GITHUB_CLIENT_SECRET : str
    FRONTEND_URL: str
    LOCAL_DATABASE_URL: str | None = None
    PROD_DATABASE_URL:  str | None = None
    REDIS_URL: str

    class Config:
        env_file = ".env"

settings = Settings()

def get_database_url(settings: Settings) -> str:
    env = settings.ENV or "development"

    db_url = (
        settings.LOCAL_DATABASE_URL
        if env == "development"
        else settings.PROD_DATABASE_URL
    )

    if not db_url:
        raise ValueError("DATABASE_URL is not set in environment variables")

    return db_url

DATABASE_URL = get_database_url(settings)