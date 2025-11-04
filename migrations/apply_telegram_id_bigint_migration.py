#!/usr/bin/env python3
"""
Скрипт для применения миграции telegram_id в таблице users с INTEGER на BIGINT
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.session import engine
from app.core.config import settings


async def apply_migration():
    """Применить миграцию"""
    print("🔄 Начинаем миграцию telegram_id с INTEGER на BIGINT...")

    try:
        async with engine.begin() as conn:
            # Проверяем текущий тип telegram_id
            result = await conn.execute(text("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name = 'telegram_id'
            """))
            current_type = result.scalar_one_or_none()
            print(f"📊 Текущий тип telegram_id: {current_type}")

            if current_type == 'bigint':
                print("✅ Поле telegram_id уже имеет тип BIGINT. Миграция не требуется.")
                return

            # Применяем миграцию
            print("⚙️  Изменяем тип telegram_id на BIGINT...")
            await conn.execute(text("""
                ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT
            """))

            # Проверяем результат
            result = await conn.execute(text("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name = 'users'
                AND column_name = 'telegram_id'
            """))
            new_type = result.scalar_one_or_none()
            print(f"✅ Новый тип telegram_id: {new_type}")

            print("✅ Миграция успешно завершена!")

    except Exception as e:
        print(f"❌ Ошибка при применении миграции: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(apply_migration())
