"""
Скрипт для добавления колонок pdf_filename и pdf_path в таблицу meal_plans

ИСПОЛЬЗОВАНИЕ:
    python migrate_add_pdf_columns.py
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
    """Добавляет колонки для хранения информации о PDF файлах"""
    try:
        async with engine.begin() as conn:
            # Добавляем колонки
            await conn.execute(text("""
                ALTER TABLE meal_plans
                ADD COLUMN IF NOT EXISTS pdf_filename VARCHAR(255),
                ADD COLUMN IF NOT EXISTS pdf_path VARCHAR(500);
            """))

            logger.info("✅ Колонки pdf_filename и pdf_path успешно добавлены в таблицу meal_plans")
            print("\n✅ УСПЕШНО! Колонки добавлены в базу данных.")
            print("Теперь можно перезапустить бота.\n")

    except Exception as e:
        logger.error(f"❌ Ошибка при добавлении колонок: {e}")
        print(f"\n❌ ОШИБКА: {e}\n")
        raise


if __name__ == "__main__":
    print("=" * 60)
    print("МИГРАЦИЯ: Добавление PDF колонок в таблицу meal_plans")
    print("=" * 60)
    asyncio.run(migrate())
    print("=" * 60)
