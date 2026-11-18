from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "EduVision AI API"
    environment: str = "development"
    api_prefix: str = "/api"
    frontend_origins: str = "http://localhost:5173"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "eduvision"
    upload_dir: str = "uploads"
    max_upload_mb: int = 20
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"
    max_analysis_chars: int = 50_000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.frontend_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
