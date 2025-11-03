"""
Миграция для переименования поля allergies в food_exclusions
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
from loguru import logger


async def rename_allergies_column():
    """Переименовывает колонку allergies в food_exclusions"""

    logger.info("Starting allergies to food_exclusions migration...")

    async with engine.begin() as conn:
        try:
            # Переименовываем колонку
            logger.info("Renaming column allergies to food_exclusions...")
            await conn.execute(text(
                "ALTER TABLE users RENAME COLUMN allergies TO food_exclusions"
            ))
            logger.success("✓ Column renamed successfully!")

        except Exception as e:
            logger.error(f"Migration failed: {repr(e)}")
            raise

    logger.success("Allergies to food_exclusions migration completed!")


if __name__ == "__main__":
    asyncio.run(rename_allergies_column())
