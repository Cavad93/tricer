"""
Скрипт для применения миграции системы кэширования планов питания
"""
import asyncio
import sys
from pathlib import Path
from loguru import logger
from sqlalchemy import text

# Добавляем корневую директорию в path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import engine as async_engine


async def apply_migration():
    """Применяет миграцию для системы кэширования планов питания"""

    migration_file = Path(__file__).parent / "migrations" / "cached_meal_plans_migration.sql"

    if not migration_file.exists():
        logger.error(f"Файл миграции не найден: {migration_file}")
        return False

    logger.info(f"Читаю миграцию из {migration_file}")

    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    logger.info("Применяю миграцию...")

    try:
        async with async_engine.begin() as conn:
            # Разбиваем SQL на отдельные команды (по точке с запятой)
            # Но учитываем, что внутри функций тоже есть точки с запятой
            commands = []
            current_command = []
            in_function = False

            for line in migration_sql.split('\n'):
                # Пропускаем комментарии
                if line.strip().startswith('--'):
                    continue

                # Отслеживаем начало/конец функций
                if 'CREATE OR REPLACE FUNCTION' in line or 'CREATE FUNCTION' in line:
                    in_function = True
                elif in_function and line.strip().startswith('$$') and '$$;' in line:
                    in_function = False
                    current_command.append(line)
                    commands.append('\n'.join(current_command))
                    current_command = []
                    continue

                current_command.append(line)

                # Если не в функции и строка заканчивается на ;, это конец команды
                if not in_function and line.strip().endswith(';'):
                    command_text = '\n'.join(current_command)
                    if command_text.strip():
                        commands.append(command_text)
                    current_command = []

            # Выполняем команды
            for i, command in enumerate(commands, 1):
                command = command.strip()
                if not command or command.startswith('--'):
                    continue

                try:
                    logger.info(f"Выполняю команду {i}/{len(commands)}")
                    await conn.execute(text(command))
                    logger.success(f"✅ Команда {i} выполнена успешно")
                except Exception as e:
                    # Игнорируем ошибки "уже существует"
                    if 'already exists' in str(e) or 'уже существует' in str(e):
                        logger.warning(f"⚠️ Команда {i}: объект уже существует, пропускаю")
                    else:
                        logger.error(f"❌ Ошибка при выполнении команды {i}: {e}")
                        logger.error(f"Команда: {command[:200]}...")
                        raise

        logger.success("✅ Миграция успешно применена!")
        return True

    except Exception as e:
        logger.error(f"❌ Ошибка при применении миграции: {e}")
        return False


async def verify_migration():
    """Проверяет что таблицы созданы"""
    logger.info("Проверяю созданные таблицы...")

    try:
        async with async_engine.begin() as conn:
            # Проверяем наличие таблиц
            result = await conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('user_categories', 'cached_meal_plans')
                ORDER BY table_name
            """))

            tables = [row[0] for row in result]

            if len(tables) == 2:
                logger.success(f"✅ Таблицы созданы: {', '.join(tables)}")

                # Проверяем количество столбцов
                for table in tables:
                    result = await conn.execute(text(f"""
                        SELECT COUNT(*)
                        FROM information_schema.columns
                        WHERE table_name = '{table}'
                    """))
                    count = result.scalar()
                    logger.info(f"  - {table}: {count} столбцов")

                return True
            else:
                logger.error(f"❌ Не все таблицы созданы. Найдено: {tables}")
                return False

    except Exception as e:
        logger.error(f"❌ Ошибка при проверке миграции: {e}")
        return False


async def main():
    """Главная функция"""
    logger.info("=" * 80)
    logger.info("Применение миграции системы кэширования планов питания")
    logger.info("=" * 80)

    # Применяем миграцию
    success = await apply_migration()

    if not success:
        logger.error("Миграция не применена из-за ошибок")
        sys.exit(1)

    # Проверяем результат
    verified = await verify_migration()

    if verified:
        logger.success("=" * 80)
        logger.success("✅ Миграция успешно применена и проверена!")
        logger.success("=" * 80)
        logger.info("Следующие шаги:")
        logger.info("1. Настроить Celery Beat (см. инструкцию)")
        logger.info("2. Перезапустить приложение")
        logger.info("3. Протестировать генерацию планов питания")
    else:
        logger.error("Проверка миграции не прошла")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
