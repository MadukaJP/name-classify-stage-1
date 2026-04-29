from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    ENV : str
    SECRET_KEY : str
    ADMIN_GITHUB_USERNAMES : str | None = None
    GITHUB_CLIENT_ID : str
    GITHUB_CLIENT_ID_CLI : str
    GITHUB_CLIENT_SECRET : str
    GITHUB_CLIENT_SECRET_CLI : str
    FRONTEND_URL: str
    LOCAL_DATABASE_URL: str | None = None
    PROD_DATABASE_URL:  str | None = None
    REDIS_URL: str

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
