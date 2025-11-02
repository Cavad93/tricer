"""
Скрипт миграции медицинских данных с шифрованием (152-ФЗ)

Переносит существующие медицинские данные из незашифрованных полей
в зашифрованные для соответствия 152-ФЗ.

Использование:
    python migrate_encrypt_medical_data.py

ВАЖНО: Перед запуском убедитесь, что:
1. Применена SQL миграция: migrations/add_encrypted_medical_fields.sql
2. В .env добавлен ENCRYPTION_KEY
3. Создана резервная копия БД!
"""

import asyncio
import sys
from sqlalchemy import select
from app.db.session import async_session_maker
from app.models.user import User
from app.services.encryption_service import get_encryption_service
from loguru import logger

# Настройка логирования
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


async def migrate_medical_data():
    """Основная функция миграции"""

    logger.info("=" * 60)
    logger.info("Миграция медицинских данных с шифрованием (152-ФЗ)")
    logger.info("=" * 60)

    # Инициализируем сервис шифрования
    try:
        encryption = get_encryption_service()
        logger.info("✓ Сервис шифрования инициализирован")
    except Exception as e:
        logger.error(f"✗ Ошибка инициализации шифрования: {e}")
        logger.error("Убедитесь, что ENCRYPTION_KEY добавлен в .env")
        return False

    # Подключаемся к БД
    async with async_session_maker() as session:
        try:
            # Получаем всех пользователей
            result = await session.execute(select(User))
            users = result.scalars().all()

            total_users = len(users)
            logger.info(f"Найдено пользователей: {total_users}")

            if total_users == 0:
                logger.warning("Нет пользователей для миграции")
                return True

            migrated_count = 0
            skipped_count = 0
            error_count = 0

            # Мигрируем данные для каждого пользователя
            for i, user in enumerate(users, 1):
                try:
                    logger.info(f"\n[{i}/{total_users}] Обработка пользователя ID={user.id}, telegram_id={user.telegram_id}")

                    has_data = False

                    # Мигрируем chronic_conditions
                    if user.chronic_conditions and not user._chronic_conditions_encrypted:
                        logger.debug(f"  Шифрование chronic_conditions: {user.chronic_conditions}")
                        user._chronic_conditions_encrypted = encryption.encrypt_list(user.chronic_conditions)
                        has_data = True

                    # Мигрируем removed_organs
                    if user.removed_organs and not user._removed_organs_encrypted:
                        logger.debug(f"  Шифрование removed_organs: {user.removed_organs}")
                        user._removed_organs_encrypted = encryption.encrypt_list(user.removed_organs)
                        has_data = True

                    # Мигрируем medical_restrictions
                    if user.medical_restrictions and not user._medical_restrictions_encrypted:
                        logger.debug(f"  Шифрование medical_restrictions")
                        user._medical_restrictions_encrypted = encryption.encrypt_dict(user.medical_restrictions)
                        has_data = True

                    if has_data:
                        await session.commit()
                        logger.info(f"  ✓ Данные зашифрованы и сохранены")
                        migrated_count += 1
                    else:
                        logger.info(f"  → Нет данных для миграции или уже мигрировано")
                        skipped_count += 1

                except Exception as e:
                    logger.error(f"  ✗ Ошибка миграции пользователя {user.id}: {e}")
                    error_count += 1
                    await session.rollback()

            # Итоговая статистика
            logger.info("\n" + "=" * 60)
            logger.info("ИТОГОВАЯ СТАТИСТИКА")
            logger.info("=" * 60)
            logger.info(f"Всего пользователей: {total_users}")
            logger.info(f"✓ Успешно мигрировано: {migrated_count}")
            logger.info(f"→ Пропущено (нет данных): {skipped_count}")
            logger.info(f"✗ Ошибок: {error_count}")

            if error_count > 0:
                logger.warning("\n⚠️ Миграция завершена с ошибками!")
                return False

            logger.success("\n✓ Миграция успешно завершена!")

            # Предупреждение о старых полях
            logger.info("\n" + "=" * 60)
            logger.warning("ВАЖНО: Старые незашифрованные поля сохранены для обратной совместимости.")
            logger.warning("После проверки корректности миграции можно удалить их командой:")
            logger.warning("ALTER TABLE users DROP COLUMN chronic_conditions;")
            logger.warning("ALTER TABLE users DROP COLUMN removed_organs;")
            logger.warning("ALTER TABLE users DROP COLUMN medical_restrictions;")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"\n✗ Критическая ошибка миграции: {e}")
            await session.rollback()
            return False


async def verify_migration():
    """Проверка корректности миграции"""

    logger.info("\n" + "=" * 60)
    logger.info("ПРОВЕРКА МИГРАЦИИ")
    logger.info("=" * 60)

    encryption = get_encryption_service()

    async with async_session_maker() as session:
        result = await session.execute(select(User).limit(5))
        users = result.scalars().all()

        for user in users:
            if user._chronic_conditions_encrypted:
                decrypted = encryption.decrypt_list(user._chronic_conditions_encrypted)
                original = user.chronic_conditions

                if decrypted == original:
                    logger.success(f"✓ User {user.id}: chronic_conditions совпадают")
                else:
                    logger.error(f"✗ User {user.id}: НЕСООТВЕТСТВИЕ chronic_conditions!")
                    logger.error(f"  Оригинал: {original}")
                    logger.error(f"  Расшифровано: {decrypted}")


def main():
    """Точка входа"""

    # Предупреждение
    logger.warning("\n" + "⚠️" * 30)
    logger.warning("ВНИМАНИЕ! Вы запускаете миграцию медицинских данных.")
    logger.warning("Убедитесь, что создана резервная копия БД!")
    logger.warning("⚠️" * 30 + "\n")

    response = input("Продолжить миграцию? (yes/no): ")
    if response.lower() != 'yes':
        logger.info("Миграция отменена пользователем")
        return

    # Запускаем миграцию
    success = asyncio.run(migrate_medical_data())

    if success:
        # Проверяем результат
        verify = input("\nВыполнить проверку миграции? (yes/no): ")
        if verify.lower() == 'yes':
            asyncio.run(verify_migration())

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
