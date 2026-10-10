from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT / ".dev.vars", ROOT / ".env"),
        env_file_encoding="utf-8", extra="ignore",
    )
    database_url: str = "postgresql+asyncpg://lab:knowledge_lab_local@127.0.0.1:55432/knowledge_lab"
    openai_api_key: SecretStr = SecretStr("")
    editor_token: SecretStr = SecretStr("")
    ai_mode: str = "saved"
    daily_global_limit: int = 100
    daily_visitor_limit: int = 20
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 256
    chat_model: str = "gpt-4.1-mini"


settings = Settings()
