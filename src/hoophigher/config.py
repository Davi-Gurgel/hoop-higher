from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from hoophigher.paths import default_sqlite_url


class Settings(BaseSettings):
    """Application settings shared across layers."""

    app_name: str = "Hoop Higher"
    database_url: str = Field(default_factory=default_sqlite_url)
    sqlite_journal_mode: str | None = "WAL"
    sqlite_synchronous: str | None = "NORMAL"
    sqlite_busy_timeout_ms: int | None = Field(default=5000, ge=0)
    stats_provider: Literal["mock", "nba_api"] = "nba_api"
    historical_start_year: int = 2010
    historical_end_year: int = 2020
    historical_rounds: int = Field(default=5, ge=1)
    nba_api_timeout_seconds: int = Field(default=20, ge=1)
    nba_api_max_retries: int = Field(default=1, ge=0)
    nba_api_retry_delay_seconds: float = Field(default=1.0, ge=0)
    nba_api_fetch_concurrency: int = Field(default=8, ge=1)
    nba_api_startup_games: int = Field(default=5, ge=1)
    game_start_timeout_seconds: float = Field(default=45.0, ge=1)
    historical_max_date_probes: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def validate_historical_settings(self) -> "Settings":
        if self.historical_start_year > self.historical_end_year:
            raise ValueError(
                "historical_start_year must be less than or equal to historical_end_year"
            )
        return self

    model_config = SettingsConfigDict(
        env_prefix="HOOPHIGHER_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
