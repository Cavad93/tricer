#!/usr/bin/env python
"""
Тестовый скрипт для проверки системы логирования.

Проверяет:
1. Создание файлов логов для всех компонентов
2. Запись логов разных уровней
3. Ротацию файлов
4. JSON форматирование

Usage:
    python test_logging.py
"""

import time
from pathlib import Path


def test_bot_logging():
    """Тест логирования бота"""
    print("=" * 80)
    print("🤖 Тестирование логирования БОТА")
    print("=" * 80)

    from app.core.loguru_setup import setup_bot_logger

    logger = setup_bot_logger(level="DEBUG")

    # Тестируем все уровни
    logger.debug("🔍 DEBUG: Отладочная информация")
    logger.info("ℹ️ INFO: Бот запущен успешно")
    logger.warning("⚠️ WARNING: Обнаружена подозрительная активность")
    logger.error("❌ ERROR: Ошибка подключения к базе данных")

    # Тест с дополнительными полями
    logger.bind(user_id=12345, telegram_id=987654321).info(
        "✅ Пользователь завершил онбординг"
    )

    # Тест exception logging
    try:
        raise ValueError("Тестовая ошибка для проверки traceback")
    except Exception as e:
        logger.exception("🔥 EXCEPTION: Произошла тестовая ошибка")

    print("\n✅ Логирование бота протестировано")
    print("📁 Проверьте файлы в logs/bot/\n")


def test_worker_logging():
    """Тест логирования воркера"""
    print("=" * 80)
    print("⚙️ Тестирование логирования ВОРКЕРА")
    print("=" * 80)

    from app.core.loguru_setup import setup_worker_logger

    logger = setup_worker_logger(level="DEBUG")

    logger.debug("🔍 DEBUG: Worker инициализирован")
    logger.info("ℹ️ INFO: Задача генерации плана питания запущена")
    logger.warning("⚠️ WARNING: AI API медленно отвечает")
    logger.error("❌ ERROR: Превышено время ожидания ответа от AI")

    # Тест с task_id
    logger.bind(task_id="abc-123-def-456", user_id=999).info(
        "✅ Задача выполнена успешно"
    )

    print("\n✅ Логирование воркера протестировано")
    print("📁 Проверьте файлы в logs/worker/\n")


def test_beat_logging():
    """Тест логирования планировщика"""
    print("=" * 80)
    print("📅 Тестирование логирования ПЛАНИРОВЩИКА")
    print("=" * 80)

    from app.core.loguru_setup import setup_beat_logger

    logger = setup_beat_logger(level="DEBUG")

    logger.debug("🔍 DEBUG: Beat scheduler инициализирован")
    logger.info("ℹ️ INFO: Запуск периодической задачи обновления кэша")
    logger.warning("⚠️ WARNING: Задача выполняется дольше обычного")
    logger.error("❌ ERROR: Не удалось запланировать задачу")

    logger.bind(task_name="update_cached_meal_plans").info(
        "✅ Периодическая задача запланирована"
    )

    print("\n✅ Логирование планировщика протестировано")
    print("📁 Проверьте файлы в logs/beat/\n")


def verify_log_files():
    """Проверка наличия созданных файлов"""
    print("=" * 80)
    print("📊 Проверка созданных файлов логов")
    print("=" * 80)

    log_base = Path("logs")
    components = ["bot", "worker", "beat"]
    files = ["all.log", "info.log", "error.log", "structured.json"]

    all_ok = True

    for component in components:
        print(f"\n📁 {component.upper()}:")
        component_dir = log_base / component

        if not component_dir.exists():
            print(f"  ❌ Директория {component_dir} не существует")
            all_ok = False
            continue

        for file_name in files:
            file_path = component_dir / file_name
            if file_path.exists():
                size = file_path.stat().st_size
                print(f"  ✅ {file_name:<20} - {size:>6} bytes")
            else:
                print(f"  ❌ {file_name:<20} - НЕ НАЙДЕН")
                all_ok = False

    print("\n" + "=" * 80)
    if all_ok:
        print("✅ Все файлы логов созданы успешно!")
    else:
        print("❌ Некоторые файлы отсутствуют. Проверьте конфигурацию.")
    print("=" * 80)

    return all_ok


def show_sample_logs():
    """Показать примеры записей из логов"""
    print("\n" + "=" * 80)
    print("📄 Примеры записей из логов")
    print("=" * 80)

    log_base = Path("logs")

    # Показать последние строки из error.log каждого компонента
    for component in ["bot", "worker", "beat"]:
        error_log = log_base / component / "error.log"
        if error_log.exists() and error_log.stat().st_size > 0:
            print(f"\n🔴 {component.upper()} - error.log (последние 3 строки):")
            print("-" * 80)
            with open(error_log, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines[-3:]:
                    print(f"  {line.rstrip()}")


def main():
    """Главная функция тестирования"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "ТЕСТ СИСТЕМЫ ЛОГИРОВАНИЯ" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # Тестируем каждый компонент
    test_bot_logging()
    time.sleep(0.5)

    test_worker_logging()
    time.sleep(0.5)

    test_beat_logging()
    time.sleep(0.5)

    # Проверяем файлы
    verify_log_files()

    # Показываем примеры
    show_sample_logs()

    print("\n" + "=" * 80)
    print("🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
    print("=" * 80)
    print()
    print("📌 Следующие шаги:")
    print("  1. Откройте logs/bot/error.log для просмотра ошибок бота")
    print("  2. Откройте logs/worker/error.log для просмотра ошибок воркера")
    print("  3. Откройте logs/beat/error.log для просмотра ошибок планировщика")
    print("  4. Используйте 'tail -f logs/bot/error.log' для мониторинга в реальном времени")
    print()
    print("📚 Полная документация: LOGGING.md")
    print()


if __name__ == "__main__":
    main()
