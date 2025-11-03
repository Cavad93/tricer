"""
Скрипт для добавления полей chronic_conditions и removed_organs в таблицу users

ИСПОЛЬЗОВАНИЕ:
    python migrate_add_wellness_fields.py
"""
import asyncio
import sys
import os

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine
from loguru import logger


async def migrate():
    """Добавляет колонки для хранения wellness данных (хронические заболевания и удаленные органы)"""
    try:
        async with engine.begin() as conn:
            # Добавляем колонки
            await conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN IF NOT EXISTS chronic_conditions JSONB DEFAULT '[]'::jsonb,
                ADD COLUMN IF NOT EXISTS removed_organs JSONB DEFAULT '[]'::jsonb;
            """))

            logger.info("✅ Колонки chronic_conditions и removed_organs успешно добавлены в таблицу users")
            print("\n✅ УСПЕШНО! Wellness поля добавлены в базу данных.")
            print("Теперь можно перезапустить бота.\n")

    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении колонок: {e}")
        print(f"\n❌ ОШИБКА: {e}\n")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("МИГРАЦИЯ: Добавление wellness полей в таблицу users")
    print("=" * 60)
    asyncio.run(migrate())
    print("=" * 60)
