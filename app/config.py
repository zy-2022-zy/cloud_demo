from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    cdp_url: str = "http://127.0.0.1:19222"
    api_key: str = "local-dev-only-change-me"
    host: str = "127.0.0.1"
    port: int = 8000
    max_snapshot_chars: int = 20_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
