
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # CDP 浏览器连接地址
    cdp_url: str = "http://127.0.0.1:19222"

    # API 访问密钥：必须在 .env 中配置
    api_key: str = Field(
        min_length=32,
        description="API authentication key",
    )

    # FastAPI 服务配置
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    # 页面快照最大字符数
    max_snapshot_chars: int = Field(
        default=20_000,
        ge=1_000,
        le=100_000,
    )

    # 运行环境
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
