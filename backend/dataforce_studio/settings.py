from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    AUTH_SECRET_KEY: str

    POSTGRESQL_DSN: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    CONFIRM_EMAIL_REDIRECT_URL: str
    CONFIRM_EMAIL_URL: str
    CHANGE_PASSWORD_URL: str

    SENDGRID_API_KEY: str

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache
def get_config() -> Settings:
    return Settings()


config = get_config()
