"""
Скрипт миграции данных из SQLite в PostgreSQL
Мигрирует все данные из nutriai.db (SQLite) в PostgreSQL
"""
import asyncio
import sqlite3
import json
from datetime import datetime
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


# Конфигурация
SQLITE_DB_PATH = "./nutriai.db"
POSTGRES_URL = "postgresql+asyncpg://nutriai:nutriai@localhost:5432/nutriai"


# Список таблиц для миграции (в правильном порядке, учитывая внешние ключи)
TABLES_TO_MIGRATE = [
    "users",
    "user_consent",
    "chat_messages",
    "daily_usage",
    "meals",
    "meal_foods",
    "meal_plans",
    "meal_plan_days",
    "planned_meals",
    "shopping_lists",
    "shopping_items",
    "product_prices",
    "daily_micronutrients",
    "food_recognition_corrections",
    "medical_analyses",
    "wellness_logs",
    "weight_history",
    "user_steps",
    "temporary_meal_plans",
]


def get_sqlite_connection():
    """Создает подключение к SQLite"""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        logger.info(f"✅ Подключение к SQLite БД: {SQLITE_DB_PATH}")
        return conn
    except Exception as e:
        logger.error("❌ Ошибка подключения к SQLite: {}", repr(e))
        raise


async def get_postgres_engine():
    """Создает async engine для PostgreSQL"""
    try:
        engine = create_async_engine(POSTGRES_URL, echo=False)
        logger.info("✅ Подключение к PostgreSQL БД")
        return engine
    except Exception as e:
        logger.error("❌ Ошибка подключения к PostgreSQL: {}", repr(e))
        raise


def convert_value(value):
    """Конвертирует значения из SQLite в формат PostgreSQL"""
    if value is None:
        return None

    # Конвертируем JSON строки в dict/list для JSONB полей
    if isinstance(value, str):
        # Проверяем, является ли строка JSON
        if value.startswith('{') or value.startswith('['):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value

    # Конвертируем булевы значения (SQLite хранит как 0/1)
    if isinstance(value, int) and value in (0, 1):
        # Это может быть boolean, но может быть и обычный int
        # Оставим как есть, PostgreSQL справится
        return value

    return value


async def migrate_table(sqlite_conn, pg_session, table_name):
    """Мигрирует одну таблицу из SQLite в PostgreSQL"""
    try:
        # Проверяем, существует ли таблица в SQLite
        cursor = sqlite_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )

        if not cursor.fetchone():
            logger.warning(f"⚠️  Таблица {table_name} не найдена в SQLite, пропускаем")
            return 0

        # Получаем все строки из таблицы SQLite
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        if not rows:
            logger.info(f"ℹ️  Таблица {table_name} пуста, пропускаем")
            return 0

        # Получаем имена колонок
        column_names = [description[0] for description in cursor.description]

        migrated_count = 0

        # Вставляем данные в PostgreSQL
        for row in rows:
            # Конвертируем row в dict
            row_dict = {}
            for i, col_name in enumerate(column_names):
                value = row[i]
                row_dict[col_name] = convert_value(value)

            # Формируем SQL запрос для INSERT
            columns = ", ".join(row_dict.keys())
            placeholders = ", ".join([f":{key}" for key in row_dict.keys()])

            insert_query = text(
                f"INSERT INTO {table_name} ({columns}) "
                f"VALUES ({placeholders}) "
                f"ON CONFLICT DO NOTHING"
            )

            try:
                await pg_session.execute(insert_query, row_dict)
                migrated_count += 1
            except Exception as e:
                logger.error("❌ Ошибка при вставке строки в {}: {}", table_name, repr(e))
                logger.debug(f"Данные строки: {row_dict}")
                # Продолжаем миграцию остальных строк
                continue

        await pg_session.commit()
        logger.success(f"✅ Таблица {table_name}: мигрировано {migrated_count} строк")
        return migrated_count

    except Exception as e:
        logger.error("❌ Ошибка при миграции таблицы {}: {}", table_name, repr(e))
        await pg_session.rollback()
        return 0


async def reset_sequences(pg_session):
    """Сбрасывает последовательности (sequences) для SERIAL полей"""
    logger.info("🔄 Обновление последовательностей для SERIAL полей...")

    # Список таблиц с SERIAL полями
    tables_with_serial = [
        "users", "user_consent", "chat_messages", "daily_usage",
        "meals", "meal_foods", "meal_plans", "meal_plan_days", "planned_meals",
        "shopping_lists", "shopping_items", "product_prices",
        "daily_micronutrients", "food_recognition_corrections",
        "medical_analyses", "wellness_logs", "weight_history",
        "user_steps", "temporary_meal_plans"
    ]

    for table in tables_with_serial:
        try:
            # Получаем максимальный ID из таблицы
            result = await pg_session.execute(
                text(f"SELECT MAX(id) FROM {table}")
            )
            max_id = result.scalar()

            if max_id:
                # Устанавливаем sequence на max_id + 1
                await pg_session.execute(
                    text(f"SELECT setval('{table}_id_seq', {max_id}, true)")
                )
                logger.info(f"  ✅ {table}: sequence установлена на {max_id}")
        except Exception as e:
            logger.warning("  ⚠️  Не удалось обновить sequence для {}: {}", table, repr(e))

    await pg_session.commit()
    logger.success("✅ Последовательности обновлены")


async def main():
    """Основная функция миграции"""
    logger.info("🚀 Начало миграции из SQLite в PostgreSQL")
    logger.info(f"   SQLite: {SQLITE_DB_PATH}")
    logger.info(f"   PostgreSQL: {POSTGRES_URL}")
    logger.info("")

    # Подключаемся к базам данных
    sqlite_conn = get_sqlite_connection()
    pg_engine = await get_postgres_engine()

    # Создаем фабрику сессий для PostgreSQL
    async_session_maker = async_sessionmaker(
        pg_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    total_migrated = 0

    try:
        async with async_session_maker() as pg_session:
            # Мигрируем каждую таблицу
            for table_name in TABLES_TO_MIGRATE:
                logger.info(f"📊 Миграция таблицы: {table_name}")
                count = await migrate_table(sqlite_conn, pg_session, table_name)
                total_migrated += count
                logger.info("")

            # Обновляем sequences
            await reset_sequences(pg_session)

        logger.info("")
        logger.success(f"✅ Миграция завершена успешно!")
        logger.success(f"   Всего мигрировано записей: {total_migrated}")

    except Exception as e:
        logger.error("❌ Критическая ошибка при миграции: {}", repr(e))
        raise

    finally:
        # Закрываем соединения
        sqlite_conn.close()
        await pg_engine.dispose()
        logger.info("🔒 Соединения закрыты")


if __name__ == "__main__":
    asyncio.run(main())
