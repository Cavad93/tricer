#!/usr/bin/env python3
"""
Скрипт для применения SQL миграций к базе данных
"""
import sqlite3
import os
from pathlib import Path
from loguru import logger


def apply_migrations(db_path: str = "./nutriai.db", migrations_dir: str = "./migrations"):
    """
    Применяет все SQL миграции из указанной директории

    Args:
        db_path: Путь к файлу базы данных SQLite
        migrations_dir: Путь к директории с миграциями
    """
    db_path = Path(db_path)
    migrations_dir = Path(migrations_dir)

    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        logger.info("Please start the bot first to create the database")
        return False

    if not migrations_dir.exists():
        logger.error(f"Migrations directory not found: {migrations_dir}")
        return False

    # Получаем список SQL файлов
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        logger.warning("No migration files found")
        return True

    logger.info(f"Found {len(migration_files)} migration files")

    # Подключаемся к БД
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Создаём таблицу для отслеживания применённых миграций
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applied_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Получаем список уже примененных миграций
        cursor.execute("SELECT filename FROM applied_migrations")
        applied = {row[0] for row in cursor.fetchall()}

        # Применяем миграции
        for migration_file in migration_files:
            filename = migration_file.name

            if filename in applied:
                logger.info(f"✓ {filename} - already applied")
                continue

            logger.info(f"Applying migration: {filename}")

            try:
                # Читаем SQL из файла
                with open(migration_file, 'r', encoding='utf-8') as f:
                    sql = f.read()

                # Разделяем на отдельные команды и выполняем
                statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

                for statement in statements:
                    if statement:
                        cursor.execute(statement)

                # Записываем, что миграция применена
                cursor.execute(
                    "INSERT INTO applied_migrations (filename) VALUES (?)",
                    (filename,)
                )

                conn.commit()
                logger.info(f"✓ {filename} - applied successfully")

            except sqlite3.Error as e:
                logger.error(f"✗ {filename} - failed: {e}")
                conn.rollback()
                continue

        cursor.close()
        conn.close()

        logger.info("All migrations applied successfully!")
        return True

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        return False


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    logger.info("=" * 60)
    logger.info("NutriAI Database Migration Tool")
    logger.info("=" * 60)

    success = apply_migrations()

    if success:
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("=" * 60)
        logger.error("Migration failed!")
        logger.error("=" * 60)
        sys.exit(1)
