"""
Тестовый скрипт для инициализации базы данных
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import init_db
from loguru import logger


async def main():
    """Инициализация БД"""
    try:
        logger.info("Starting database initialization...")
        await init_db()
        logger.success("✓ Database initialized successfully!")

        # Проверяем что таблицы созданы
        from sqlalchemy import inspect
        from app.db.session import engine

        async with engine.connect() as conn:
            def get_tables(connection):
                inspector = inspect(connection)
                return inspector.get_table_names()

            tables = await conn.run_sync(get_tables)

            logger.info(f"Created {len(tables)} tables:")
            for table in sorted(tables):
                logger.info(f"  - {table}")

            # Проверяем наличие таблицы микронутриентов
            if "daily_micronutrients" in tables:
                logger.success("✓ Micronutrients table created successfully!")
            else:
                logger.error("✗ Micronutrients table NOT found!")

            if "food_recognition_corrections" in tables:
                logger.success("✓ Food corrections table created successfully!")
            else:
                logger.error("✗ Food corrections table NOT found!")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
