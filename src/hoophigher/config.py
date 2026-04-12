from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings shared across layers."""

    app_name: str = "Hoop Higher"
    database_url: str = f"sqlite:///{Path('hoophigher.db').resolve()}"
    sqlite_journal_mode: str | None = "WAL"
    sqlite_synchronous: str | None = "NORMAL"
    sqlite_busy_timeout_ms: int | None = 5000

    model_config = SettingsConfigDict(
        env_prefix="HOOPHIGHER_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
