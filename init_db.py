"""
Скрипт для инициализации базы данных
Создает все необходимые таблицы
"""
import asyncio
from loguru import logger

from app.db.session import init_db


async def main():
    """Инициализация БД"""
    logger.info("Initializing database...")

    try:
        await init_db()
        logger.success("✅ Database initialized successfully!")
        logger.info("Tables created:")
        logger.info("  - users")
        logger.info("  - chat_messages")
        logger.info("  - daily_usage")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
