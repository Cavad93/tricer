"""
Скрипт для проверки типов данных в БД PostgreSQL
Находит INTEGER колонки которые должны быть BOOLEAN
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
from loguru import logger


async def check_boolean_columns():
    """Проверка типов boolean-подобных колонок в БД"""

    query = text("""
        SELECT
            table_name,
            column_name,
            data_type,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND (
              column_name LIKE '%_active%'
              OR column_name LIKE '%_enabled%'
              OR column_name LIKE '%_blocked%'
              OR column_name LIKE '%_completed%'
              OR (column_name LIKE '%_used%' AND column_name NOT LIKE 'times_%' AND column_name NOT LIKE 'tokens_%')
          )
        ORDER BY table_name, column_name
    """)

    async with engine.connect() as conn:
        result = await conn.execute(query)
        rows = result.fetchall()

        if not rows:
            logger.success("✅ Не найдено boolean-подобных колонок")
            return

        logger.info("Найдено {} boolean-подобных колонок:", len(rows))
        print("\n{:<30} {:<30} {:<15} {:<20}".format("Таблица", "Колонка", "Тип", "По умолчанию"))
        print("-" * 100)

        issues = []
        for row in rows:
            table, column, dtype, default = row
            print("{:<30} {:<30} {:<15} {:<20}".format(
                table, column, dtype, str(default)[:20] if default else "NULL"
            ))

            # Проверяем проблемные случаи
            if dtype == 'integer' and any(x in column for x in ['active', 'enabled', 'blocked', 'completed', 'trial_used', 'onboarding_completed']):
                issues.append((table, column, dtype))

        print("\n")

        if issues:
            logger.error("❌ Найдено {} проблемных INTEGER колонок, которые должны быть BOOLEAN:", len(issues))
            for table, column, dtype in issues:
                logger.error("  - {}.{} ({}) - должно быть BOOLEAN", table, column, dtype)
            logger.info("\nДля исправления выполните: psql -U nutriai -d nutriai -f fix_is_active_column.sql")
        else:
            logger.success("✅ Все boolean-подобные колонки имеют правильный тип данных!")


if __name__ == "__main__":
    asyncio.run(check_boolean_columns())
