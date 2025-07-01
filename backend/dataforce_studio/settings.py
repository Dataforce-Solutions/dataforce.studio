import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    AUTH_SECRET_KEY: str
    BUCKET_SECRET_KEY: str

    POSTGRESQL_DSN: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str

    CONFIRM_EMAIL_REDIRECT_URL: str
    CONFIRM_EMAIL_URL: str
    CHANGE_PASSWORD_URL: str
    APP_EMAIL_URL: str

    SENDGRID_API_KEY: str
    SENDER_EMAIL: str

    TEMPLATE_ID_ACTIVATION_EMAIL: str
    TEMPLATE_ID_RESET_PASSWORD_EMAIL: str
    TEMPLATE_ID_ORGANIZATION_INVITE_EMAIL: str
    TEMPLATE_ID_ADDED_TO_ORBIT_EMAIL: str

    SUBJECT_ACTIVATION_EMAIL: str
    SUBJECT_RESET_PASSWORD_EMAIL: str

    # quickfix, to be refactored later
    model_config = SettingsConfigDict(
        env_file=".env.test" if "PYTEST_VERSION" in os.environ else ".env",
        extra="ignore",
    )


@lru_cache
def get_config() -> Settings:
    return Settings()  # type: ignore[call-arg]


config = get_config()
