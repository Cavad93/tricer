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

    # Claude API Rate Limiting
    # Anthropic tiers: Tier 1=50 req/min, Tier 2=1000, Tier 3=2000, Tier 4=4000
    CLAUDE_RATE_LIMIT: int = 50  # Requests per minute
    CLAUDE_MAX_RETRIES: int = 3  # Maximum retry attempts on failure
    CLAUDE_RETRY_MIN_WAIT: int = 1  # Minimum wait between retries (seconds)
    CLAUDE_RETRY_MAX_WAIT: int = 10  # Maximum wait between retries (seconds)

    # ===== ОБХОД ГЕОБЛОКИРОВКИ =====
    # ВНИМАНИЕ: Эти параметры нужны ТОЛЬКО если ваш сервер в России!
    # Если сервер за пределами России (США, Европа, Азия) - оставьте None

    # Вариант 1: Cloudflare Worker (для облачных сервисов)
    # Формат: https://your-worker.your-subdomain.workers.dev
    # Используйте если не можете установить VPN на сервере
    CLOUDFLARE_WORKER_URL: Optional[str] = None

    # Вариант 2: WARP/VPN Proxy (для VDS/VPS с возможностью установки VPN)
    # Формат: socks5://127.0.0.1:40000
    # Используйте если установили Cloudflare WARP или другой SOCKS5 прокси
    WARP_PROXY_URL: Optional[str] = None

    # Приоритет: CLOUDFLARE_WORKER_URL > WARP_PROXY_URL > Прямое подключение

    # Database (PostgreSQL)
    DATABASE_URL: str = "postgresql+asyncpg://nutriai:nutriai@localhost:5432/nutriai"

    # Redis (for Celery task queue)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Webhook Mode Settings
    USE_WEBHOOK: bool = False
    WEBHOOK_LISTEN: str = "0.0.0.0"
    WEBHOOK_PORT: int = 8443
    WEBHOOK_PATH: str = "webhook"
    WEBHOOK_URL: str = ""  # Example: "https://bot.example.com/webhook"
    WEBHOOK_SECRET: str = ""  # Generate with: openssl rand -hex 32
    WEBHOOK_SSL_CERT: str = ""  # Path to SSL certificate (optional if using nginx)
    WEBHOOK_SSL_KEY: str = ""  # Path to SSL private key (optional if using nginx)

    # PostgreSQL connection settings (optional, for advanced configuration)
    POSTGRES_USER: str = "nutriai"
    POSTGRES_PASSWORD: str = "nutriai"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "nutriai"

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

    # Monitoring (Prometheus + Grafana)
    METRICS_PORT: int = 8000  # Port for Prometheus metrics HTTP endpoint
    ENVIRONMENT: str = "production"  # Environment: development/staging/production

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )


# Создаем глобальный экземпляр настроек
settings = Settings()
