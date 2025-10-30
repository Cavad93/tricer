"""
Скрипт для применения исправления типа колонки is_active
Изменяет meal_plans.is_active с INTEGER на BOOLEAN
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
from loguru import logger


async def fix_is_active_column():
    """Исправление типа колонки is_active в таблице meal_plans"""

    logger.info("Начинаем исправление типа колонки meal_plans.is_active...")

    async with engine.begin() as conn:
        try:
            # Проверяем текущий тип
            logger.info("Проверка текущего типа колонки...")
            check_query = text("""
                SELECT column_name, data_type, column_default
                FROM information_schema.columns
                WHERE table_name = 'meal_plans' AND column_name = 'is_active'
            """)
            result = await conn.execute(check_query)
            row = result.fetchone()

            if row:
                logger.info("Текущий тип: {} (default: {})", row[1], row[2] or "NULL")

                if row[1] == 'integer':
                    logger.info("Конвертируем INTEGER -> BOOLEAN...")

                    # Изменяем тип колонки
                    await conn.execute(text("""
                        ALTER TABLE meal_plans
                            ALTER COLUMN is_active TYPE BOOLEAN
                            USING CASE
                                WHEN is_active = 0 THEN FALSE
                                WHEN is_active = 1 THEN TRUE
                                ELSE TRUE
                            END
                    """))
                    logger.success("✅ Тип колонки изменен на BOOLEAN")

                    # Устанавливаем значение по умолчанию
                    await conn.execute(text("""
                        ALTER TABLE meal_plans
                            ALTER COLUMN is_active SET DEFAULT TRUE
                    """))
                    logger.success("✅ Установлено значение по умолчанию: TRUE")

                elif row[1] == 'boolean':
                    logger.success("✅ Колонка уже имеет тип BOOLEAN, исправление не требуется")
                else:
                    logger.warning("⚠️ Неожиданный тип колонки: {}", row[1])
            else:
                logger.error("❌ Колонка is_active не найдена в таблице meal_plans")
                return

            # Проверяем результат
            logger.info("Проверка результата...")
            result = await conn.execute(check_query)
            row = result.fetchone()

            if row:
                logger.info("Новый тип: {} (default: {})", row[1], row[2] or "NULL")

                if row[1] == 'boolean':
                    logger.success("✅ Исправление применено успешно!")
                else:
                    logger.error("❌ Тип колонки не изменился: {}", row[1])

        except Exception as e:
            logger.error("❌ Ошибка при исправлении: {}", repr(e))
            raise


async def main():
    """Главная функция"""
    try:
        await fix_is_active_column()
        logger.success("\n✅ Миграция завершена успешно!")
        logger.info("\nТеперь вы можете перезапустить бота: python -m app.bot.main")
    except Exception as e:
        logger.error("\n❌ Миграция не удалась: {}", repr(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
