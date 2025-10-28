"""
Конфигурация приложения NutriAI
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения"""

    # Application
    APP_NAME: str = "NutriAI"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Telegram
    TELEGRAM_BOT_TOKEN: str

    # Claude API
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # Database (SQLite)
    DATABASE_URL: str = "sqlite+aiosqlite:///./nutriai.db"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Server
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Rate Limiting
    FREE_PHOTO_LIMIT_PER_DAY: int = 5
    FREE_CHAT_LIMIT_PER_DAY: int = 10

    # Logging
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


# Создаем глобальный экземпляр настроек
settings = Settings()
