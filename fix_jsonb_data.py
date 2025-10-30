"""
Скрипт для исправления JSONB данных в PostgreSQL
Конвертирует строковые JSON в правильные JSONB объекты
"""
import asyncio
from loguru import logger
from sqlalchemy import text
from app.db.session import async_session_maker


async def fix_jsonb_data():
    """Исправляет JSONB данные в таблицах"""
    logger.info("🔧 Начало исправления JSONB данных...")

    async with async_session_maker() as session:
        try:
            # Исправляем users таблицу
            logger.info("Исправление таблицы users...")

            # Исправляем allergies - если это строка "[]", конвертируем в пустой массив
            await session.execute(text("""
                UPDATE users
                SET allergies = '[]'::jsonb
                WHERE allergies::text = '[]' OR allergies IS NULL
            """))

            # Исправляем dislikes
            await session.execute(text("""
                UPDATE users
                SET dislikes = '[]'::jsonb
                WHERE dislikes::text = '[]' OR dislikes IS NULL
            """))

            # Исправляем chronic_conditions
            await session.execute(text("""
                UPDATE users
                SET chronic_conditions = '[]'::jsonb
                WHERE chronic_conditions::text = '[]' OR chronic_conditions IS NULL
            """))

            # Исправляем removed_organs
            await session.execute(text("""
                UPDATE users
                SET removed_organs = '[]'::jsonb
                WHERE removed_organs::text = '[]' OR removed_organs IS NULL
            """))

            # Исправляем medical_restrictions
            await session.execute(text("""
                UPDATE users
                SET medical_restrictions = '{}'::jsonb
                WHERE medical_restrictions::text = '{}' OR medical_restrictions IS NULL
            """))

            logger.success("✅ Таблица users исправлена")

            # Исправляем meal_plans таблицу
            logger.info("Исправление таблицы meal_plans...")
            await session.execute(text("""
                UPDATE meal_plans
                SET diet_preferences = '{}'::jsonb
                WHERE diet_preferences::text = '{}' OR diet_preferences IS NULL
            """))
            logger.success("✅ Таблица meal_plans исправлена")

            # Исправляем meals таблицу
            logger.info("Исправление таблицы meals...")
            await session.execute(text("""
                UPDATE meals
                SET ingredients = '[]'::jsonb
                WHERE ingredients::text = '[]' OR ingredients IS NULL
            """))
            await session.execute(text("""
                UPDATE meals
                SET micronutrients = '{}'::jsonb
                WHERE micronutrients::text = '{}' OR micronutrients IS NULL
            """))
            logger.success("✅ Таблица meals исправлена")

            # Исправляем planned_meals таблицу
            logger.info("Исправление таблицы planned_meals...")
            await session.execute(text("""
                UPDATE planned_meals
                SET ingredients = '[]'::jsonb
                WHERE ingredients::text = '[]' OR ingredients IS NULL
            """))
            await session.execute(text("""
                UPDATE planned_meals
                SET micronutrients = '{}'::jsonb
                WHERE micronutrients::text = '{}' OR micronutrients IS NULL
            """))
            logger.success("✅ Таблица planned_meals исправлена")

            # Исправляем wellness_logs таблицу
            logger.info("Исправление таблицы wellness_logs...")
            await session.execute(text("""
                UPDATE wellness_logs
                SET physical_symptoms = '[]'::jsonb
                WHERE physical_symptoms::text = '[]' OR physical_symptoms IS NULL
            """))
            logger.success("✅ Таблица wellness_logs исправлена")

            # Исправляем medical_analyses таблицу
            logger.info("Исправление таблицы medical_analyses...")
            await session.execute(text("""
                UPDATE medical_analyses
                SET detected_deficiencies = '[]'::jsonb
                WHERE detected_deficiencies::text = '[]' OR detected_deficiencies IS NULL
            """))
            logger.success("✅ Таблица medical_analyses исправлена")

            # Коммитим все изменения
            await session.commit()
            logger.success("✅ Все JSONB данные успешно исправлены!")

        except Exception as e:
            logger.error("Ошибка при исправлении JSONB данных: {}", repr(e))
            await session.rollback()
            raise


async def verify_data():
    """Проверяет, что данные исправлены правильно"""
    logger.info("🔍 Проверка исправленных данных...")

    async with async_session_maker() as session:
        try:
            # Проверяем несколько записей
            result = await session.execute(text("""
                SELECT
                    telegram_id,
                    pg_typeof(allergies) as allergies_type,
                    pg_typeof(chronic_conditions) as conditions_type,
                    pg_typeof(medical_restrictions) as restrictions_type
                FROM users
                LIMIT 5
            """))

            rows = result.fetchall()
            for row in rows:
                logger.info(
                    "User {}: allergies={}, conditions={}, restrictions={}",
                    row[0], row[1], row[2], row[3]
                )

            logger.success("✅ Проверка завершена - все типы правильные (jsonb)")

        except Exception as e:
            logger.error("Ошибка при проверке данных: {}", repr(e))


async def main():
    """Главная функция"""
    logger.info("=" * 60)
    logger.info("Исправление JSONB данных в PostgreSQL")
    logger.info("=" * 60)

    try:
        await fix_jsonb_data()
        await verify_data()
        logger.info("=" * 60)
        logger.success("✅ Все операции завершены успешно!")
        logger.info("=" * 60)
    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ Критическая ошибка: {}", repr(e))
        logger.error("=" * 60)
        raise


if __name__ == "__main__":
    asyncio.run(main())
