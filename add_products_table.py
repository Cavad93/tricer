#!/usr/bin/env python
"""
Добавление таблицы products для кэширования продуктов с микронутриентами.

Запуск:
    python add_products_table.py
"""
import asyncio
from sqlalchemy import text
from loguru import logger

from app.db.session import async_engine


async def add_products_table():
    """Создать таблицу products"""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name VARCHAR(500) NOT NULL,
        name_normalized VARCHAR(500) NOT NULL,
        name_hash VARCHAR(64) NOT NULL UNIQUE,

        calories FLOAT NOT NULL,
        proteins FLOAT NOT NULL,
        fats FLOAT NOT NULL,
        carbs FLOAT NOT NULL,

        micronutrients JSONB DEFAULT '{}',

        category VARCHAR(100),
        source VARCHAR(50) NOT NULL,
        confidence FLOAT,

        usage_count INTEGER DEFAULT 1,
        last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_product_name ON products(name);",
        "CREATE INDEX IF NOT EXISTS idx_product_name_normalized ON products(name_normalized);",
        "CREATE INDEX IF NOT EXISTS idx_product_name_hash ON products(name_hash);",
        "CREATE INDEX IF NOT EXISTS idx_product_source ON products(source);",
        "CREATE INDEX IF NOT EXISTS idx_product_usage_count ON products(usage_count DESC);",
    ]

    try:
        async with async_engine.begin() as conn:
            logger.info("Creating products table...")
            await conn.execute(text(create_table_sql))
            logger.info("✅ Table 'products' created successfully")

            logger.info("Creating indexes...")
            for index_sql in create_indexes_sql:
                await conn.execute(text(index_sql))
            logger.info("✅ All indexes created successfully")

        logger.info("🎉 Migration completed successfully!")

    except Exception as e:
        logger.error(f"❌ Error creating products table: {repr(e)}")
        raise


async def main():
    logger.info("=" * 80)
    logger.info("Adding products table for product caching")
    logger.info("=" * 80)

    await add_products_table()

    logger.info("=" * 80)
    logger.info("Migration completed!")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
