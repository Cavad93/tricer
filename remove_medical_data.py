"""
Миграция для удаления медицинских данных из базы данных
"""
import asyncio
from sqlalchemy import text
from app.db.session import engine
from loguru import logger


async def remove_medical_data():
    """Удаляет медицинские поля из таблицы users"""

    logger.info("Starting medical data removal migration...")

    # SQL команды для удаления столбцов
    drop_commands = [
        "ALTER TABLE users DROP COLUMN IF EXISTS chronic_conditions",
        "ALTER TABLE users DROP COLUMN IF EXISTS removed_organs",
        "ALTER TABLE users DROP COLUMN IF EXISTS medical_restrictions",
        "ALTER TABLE users DROP COLUMN IF EXISTS medical_notes",
        "ALTER TABLE users DROP COLUMN IF EXISTS _chronic_conditions_encrypted",
        "ALTER TABLE users DROP COLUMN IF EXISTS _removed_organs_encrypted",
        "ALTER TABLE users DROP COLUMN IF EXISTS _medical_restrictions_encrypted",
    ]

    async with engine.begin() as conn:
        for command in drop_commands:
            try:
                logger.info(f"Executing: {command}")
                await conn.execute(text(command))
                logger.success(f"✓ Successfully executed: {command}")
            except Exception as e:
                logger.warning(f"Failed to execute '{command}': {repr(e)}")
                # Продолжаем выполнение даже если столбец не существует

    logger.success("Medical data removal migration completed!")


if __name__ == "__main__":
    asyncio.run(remove_medical_data())
