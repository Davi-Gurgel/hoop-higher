from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from hoophigher.data.db import DEFAULT_SQLITE_URL


class Settings(BaseSettings):
    """Application settings shared across layers."""

    app_name: str = "Hoop Higher"
    database_url: str = DEFAULT_SQLITE_URL
    sqlite_journal_mode: str | None = "WAL"
    sqlite_synchronous: str | None = "NORMAL"
    sqlite_busy_timeout_ms: int | None = 5000
    stats_provider: Literal["mock", "nba_api"] = "nba_api"
    historical_start_year: int = 2010
    historical_end_year: int = 2020
    historical_rounds: int = 5
    nba_api_timeout_seconds: int = 20
    nba_api_max_retries: int = 1
    nba_api_retry_delay_seconds: float = 1.0
    nba_api_fetch_concurrency: int = 5
    nba_api_startup_games: int = 5
    game_start_timeout_seconds: float = 45.0
    historical_max_date_probes: int = 10

    @model_validator(mode="after")
    def validate_historical_settings(self) -> "Settings":
        if self.historical_start_year > self.historical_end_year:
            raise ValueError("historical_start_year must be less than or equal to historical_end_year")
        if self.historical_rounds < 1:
            raise ValueError("historical_rounds must be greater than or equal to 1")
        if self.nba_api_timeout_seconds < 1:
            raise ValueError("nba_api_timeout_seconds must be greater than or equal to 1")
        if self.nba_api_max_retries < 0:
            raise ValueError("nba_api_max_retries must be greater than or equal to 0")
        if self.nba_api_retry_delay_seconds < 0:
            raise ValueError("nba_api_retry_delay_seconds must be greater than or equal to 0")
        if self.nba_api_fetch_concurrency < 1:
            raise ValueError("nba_api_fetch_concurrency must be greater than or equal to 1")
        if self.nba_api_startup_games < 1:
            raise ValueError("nba_api_startup_games must be greater than or equal to 1")
        if self.game_start_timeout_seconds < 1:
            raise ValueError("game_start_timeout_seconds must be greater than or equal to 1")
        if self.historical_max_date_probes < 1:
            raise ValueError("historical_max_date_probes must be greater than or equal to 1")
        return self

    model_config = SettingsConfigDict(
        env_prefix="HOOPHIGHER_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
