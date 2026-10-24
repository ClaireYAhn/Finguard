"""Environment-driven settings. API keys live here (server side) and are never sent to the frontend."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore", populate_by_name=True)

    admin_password: str = Field("change-me-admin", validation_alias="FINGUARD_ADMIN_PASSWORD")
    session_secret: str = Field("", validation_alias="FINGUARD_SESSION_SECRET")
    db_path: str = Field(str(BACKEND_DIR / "data" / "runtime" / "finguard.db"), validation_alias="FINGUARD_DB_PATH")
    provider: str = Field("mock", validation_alias="FINGUARD_PROVIDER")  # mock | anthropic | openai
    anthropic_api_key: str = Field("", validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    default_model: str = Field("", validation_alias="FINGUARD_DEFAULT_MODEL")
    engine: str = Field("nemo", validation_alias="FINGUARD_ENGINE")  # nemo | native
    store_raw: bool = Field(False, validation_alias="FINGUARD_STORE_RAW")
    model_judge: bool = Field(False, validation_alias="FINGUARD_MODEL_JUDGE")
    use_presidio: bool = Field(False, validation_alias="FINGUARD_USE_PRESIDIO")
    public_url: str = Field("", validation_alias="FINGUARD_PUBLIC_URL")
    cors_origins: str = Field("http://localhost:5173,http://localhost:3000", validation_alias="FINGUARD_CORS_ORIGINS")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    global _settings
    _settings = Settings()
    return _settings
