import secrets

from arq.connections import RedisSettings
from pydantic import PostgresDsn, computed_field
from pydantic_core import MultiHostUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Use the top level .env file (one level above ./deep_ice/).
        env_file=".env",
        env_ignore_empty=False,
        extra="ignore",
    )

    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False
    PROJECT_NAME: str = "Deep Ice"
    API_V1_STR: str = "/v1"

    # Helps JWT signing and checking.
    SECRET_KEY: str = secrets.token_urlsafe(32)
    # 60 minutes * 24 hours * 8 days = 8 days
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    POSTGRES_SERVER: str
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDLOCK_TTL: int = 30  # seconds for the lock to persists in Redis

    TASK_MAX_TRIES: int = 3
    TASK_RETRY_DELAY: int = 1  # seconds between retries
    TASK_BACKOFF_FACTOR: int = 5  # seconds to wait based on the job try counter

    SENTRY_DSN: str = ""  # without a value we won't initialize Sentry capturing
    SENTRY_SAMPLE_RATE: float = 0.2  # percentage of traces to capture

    @computed_field  # type: ignore[prop-decorator]
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> PostgresDsn:
        return MultiHostUrl.build(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_SERVER,
            port=self.POSTGRES_PORT,
            path=self.POSTGRES_DB,
        )


settings = Settings()  # type: ignore
redis_settings = RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
