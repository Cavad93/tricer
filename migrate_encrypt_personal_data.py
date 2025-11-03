"""
Миграция для шифрования персональных данных (152-ФЗ)

Добавляет зашифрованные поля и переносит существующие данные
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine, async_session_maker
from app.services.encryption_service import EncryptionService
from loguru import logger


async def migrate():
    """Миграция для добавления зашифрованных полей"""
    try:
        async with engine.begin() as conn:
            logger.info("Adding encrypted columns to users table...")

            # Добавляем новые зашифрованные поля
            await conn.execute(text("""
                -- Telegram данные (зашифрованные)
                ALTER TABLE users ADD COLUMN IF NOT EXISTS username_encrypted TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name_encrypted TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name_encrypted TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_name_encrypted TEXT;

                -- Локация (зашифрованная)
                ALTER TABLE users ADD COLUMN IF NOT EXISTS country_encrypted TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS city_encrypted TEXT;

                -- Профиль (зашифрованный)
                ALTER TABLE users ADD COLUMN IF NOT EXISTS birth_year_encrypted TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS height_encrypted TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS current_weight_encrypted TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS target_weight_encrypted TEXT;

                -- Предпочтения (зашифрованные)
                ALTER TABLE users ADD COLUMN IF NOT EXISTS food_exclusions_encrypted TEXT;

                -- Wellness данные (зашифрованные)
                ALTER TABLE users ADD COLUMN IF NOT EXISTS chronic_conditions_encrypted TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS removed_organs_encrypted TEXT;
            """))

            logger.info("✅ Encrypted columns added successfully")

        # Теперь мигрируем существующие данные
        logger.info("Migrating existing data...")

        async with async_session_maker() as session:
            # Получаем всех пользователей с незашифрованными данными
            result = await session.execute(text("""
                SELECT id, username, first_name, last_name, preferred_name,
                       country, city, birth_year, height, current_weight, target_weight,
                       food_exclusions, chronic_conditions, removed_organs
                FROM users
                WHERE username_encrypted IS NULL OR preferred_name_encrypted IS NULL
            """))

            users = result.fetchall()
            logger.info(f"Found {len(users)} users with unencrypted data")

            # Шифруем данные каждого пользователя
            for user in users:
                user_id, username, first_name, last_name, preferred_name, country, city, \
                    birth_year, height, current_weight, target_weight, \
                    food_exclusions, chronic_conditions, removed_organs = user

                # Шифруем строковые поля
                username_enc = EncryptionService.encrypt_string(username) if username else None
                first_name_enc = EncryptionService.encrypt_string(first_name) if first_name else None
                last_name_enc = EncryptionService.encrypt_string(last_name) if last_name else None
                preferred_name_enc = EncryptionService.encrypt_string(preferred_name) if preferred_name else None
                country_enc = EncryptionService.encrypt_string(country) if country else None
                city_enc = EncryptionService.encrypt_string(city) if city else None

                # Шифруем численные поля
                birth_year_enc = EncryptionService.encrypt_int(birth_year) if birth_year else None
                height_enc = EncryptionService.encrypt_int(height) if height else None
                current_weight_enc = EncryptionService.encrypt_float(current_weight) if current_weight else None
                target_weight_enc = EncryptionService.encrypt_float(target_weight) if target_weight else None

                # Шифруем списки (JSONB)
                food_exclusions_enc = EncryptionService.encrypt_list(food_exclusions) if food_exclusions else None
                chronic_conditions_enc = EncryptionService.encrypt_list(chronic_conditions) if chronic_conditions else None
                removed_organs_enc = EncryptionService.encrypt_list(removed_organs) if removed_organs else None

                # Обновляем запись
                await session.execute(
                    text("""
                        UPDATE users SET
                            username_encrypted = :username_enc,
                            first_name_encrypted = :first_name_enc,
                            last_name_encrypted = :last_name_enc,
                            preferred_name_encrypted = :preferred_name_enc,
                            country_encrypted = :country_enc,
                            city_encrypted = :city_enc,
                            birth_year_encrypted = :birth_year_enc,
                            height_encrypted = :height_enc,
                            current_weight_encrypted = :current_weight_enc,
                            target_weight_encrypted = :target_weight_enc,
                            food_exclusions_encrypted = :food_exclusions_enc,
                            chronic_conditions_encrypted = :chronic_conditions_enc,
                            removed_organs_encrypted = :removed_organs_enc
                        WHERE id = :user_id
                    """),
                    {
                        "user_id": user_id,
                        "username_enc": username_enc,
                        "first_name_enc": first_name_enc,
                        "last_name_enc": last_name_enc,
                        "preferred_name_enc": preferred_name_enc,
                        "country_enc": country_enc,
                        "city_enc": city_enc,
                        "birth_year_enc": birth_year_enc,
                        "height_enc": height_enc,
                        "current_weight_enc": current_weight_enc,
                        "target_weight_enc": target_weight_enc,
                        "food_exclusions_enc": food_exclusions_enc,
                        "chronic_conditions_enc": chronic_conditions_enc,
                        "removed_organs_enc": removed_organs_enc,
                    }
                )

            await session.commit()
            logger.info(f"✅ Migrated {len(users)} users successfully")

        # Удаляем старые незашифрованные колонки (опционально)
        print("\n⚠️  ВНИМАНИЕ: Хотите удалить старые незашифрованные колонки? (y/N): ", end="")
        response = input().strip().lower()

        if response == 'y':
            async with engine.begin() as conn:
                logger.info("Dropping old unencrypted columns...")
                await conn.execute(text("""
                    ALTER TABLE users
                    DROP COLUMN IF EXISTS username,
                    DROP COLUMN IF EXISTS first_name,
                    DROP COLUMN IF EXISTS last_name,
                    DROP COLUMN IF EXISTS preferred_name,
                    DROP COLUMN IF EXISTS country,
                    DROP COLUMN IF EXISTS city,
                    DROP COLUMN IF EXISTS birth_year,
                    DROP COLUMN IF EXISTS height,
                    DROP COLUMN IF EXISTS current_weight,
                    DROP COLUMN IF EXISTS target_weight,
                    DROP COLUMN IF EXISTS food_exclusions,
                    DROP COLUMN IF EXISTS chronic_conditions,
                    DROP COLUMN IF EXISTS removed_organs;
                """))

                logger.info("✅ Old columns dropped successfully")
        else:
            logger.info("Keeping old columns for backward compatibility")

        print("\n✅ MIGRATION COMPLETED!")
        print("All personal data is now encrypted.")
        print("The app will now transparently encrypt/decrypt data on the fly.\n")

    except Exception as e:
        logger.error(f"❌ Migration error: {repr(e)}")
        print(f"\n❌ ОШИБКА: {e}\n")
        raise


if __name__ == "__main__":
    print("=" * 70)
    print("МИГРАЦИЯ: Шифрование персональных данных (152-ФЗ)")
    print("=" * 70)
    print("\nЭта миграция:")
    print("1. Добавит новые зашифрованные поля в таблицу users")
    print("2. Зашифрует все существующие персональные данные")
    print("3. (Опционально) Удалит старые незашифрованные поля\n")

    asyncio.run(migrate())

    print("=" * 70)
