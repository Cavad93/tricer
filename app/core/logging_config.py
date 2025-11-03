"""
Профессиональная система логирования для NutriAI бота.

Функции:
✅ Отдельные файлы для бота, воркера и планировщика
✅ Ротация логов по размеру (50MB) и времени (ежедневно)
✅ Автоочистка старых логов (30 дней)
✅ Разделение по уровням (all, info, error)
✅ Структурированное логирование (JSON формат)
"""

import logging
import os
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from app.core.json_formatter import JSONFormatter


# Конфигурация логирования
LOG_BASE_DIR = Path("logs")
MAX_BYTES = 50 * 1024 * 1024  # 50MB
BACKUP_COUNT = 30  # Хранить 30 резервных копий (30 дней для daily ротации)
ENCODING = "utf-8"

# Форматы логов
DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"
SIMPLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class LoggingConfig:
    """
    Конфигуратор системы логирования.

    Создает отдельные логгеры для бота, воркера и планировщика
    с ротацией по размеру и времени, автоочисткой старых файлов.
    """

    @staticmethod
    def setup_logger(
        name: str,
        component: str,
        level: int = logging.INFO,
        use_console: bool = True
    ) -> logging.Logger:
        """
        Настраивает логгер для компонента (bot, worker, beat).

        Args:
            name: Имя логгера (например, 'nutriai.bot')
            component: Тип компонента ('bot', 'worker', 'beat')
            level: Уровень логирования (по умолчанию INFO)
            use_console: Выводить ли логи в консоль

        Returns:
            Настроенный логгер
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)  # Установим DEBUG, фильтрация на уровне handlers
        logger.propagate = False  # Не передавать родительским логгерам

        # Очистить существующие handlers
        logger.handlers.clear()

        # Создать директорию для компонента
        component_dir = LOG_BASE_DIR / component
        component_dir.mkdir(parents=True, exist_ok=True)

        # 1. ALL.LOG - Все уровни логирования (DEBUG и выше)
        all_handler = RotatingFileHandler(
            filename=component_dir / "all.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding=ENCODING
        )
        all_handler.setLevel(logging.DEBUG)
        all_handler.setFormatter(logging.Formatter(DETAILED_FORMAT, DATE_FORMAT))
        logger.addHandler(all_handler)

        # 2. INFO.LOG - INFO и выше (без DEBUG)
        info_handler = TimedRotatingFileHandler(
            filename=component_dir / "info.log",
            when="midnight",
            interval=1,
            backupCount=BACKUP_COUNT,
            encoding=ENCODING
        )
        info_handler.setLevel(logging.INFO)
        info_handler.setFormatter(logging.Formatter(DETAILED_FORMAT, DATE_FORMAT))
        logger.addHandler(info_handler)

        # 3. ERROR.LOG - Только ERROR и CRITICAL
        error_handler = RotatingFileHandler(
            filename=component_dir / "error.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding=ENCODING
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(DETAILED_FORMAT, DATE_FORMAT))
        logger.addHandler(error_handler)

        # 4. STRUCTURED.JSON - JSON формат для всех уровней
        json_handler = TimedRotatingFileHandler(
            filename=component_dir / "structured.json",
            when="midnight",
            interval=1,
            backupCount=BACKUP_COUNT,
            encoding=ENCODING
        )
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(JSONFormatter())
        logger.addHandler(json_handler)

        # 5. Console handler (опционально)
        if use_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(logging.Formatter(SIMPLE_FORMAT, DATE_FORMAT))
            logger.addHandler(console_handler)

        return logger

    @staticmethod
    def setup_bot_logging(level: int = logging.INFO) -> logging.Logger:
        """
        Настраивает логирование для Telegram бота.

        Args:
            level: Уровень логирования для консоли

        Returns:
            Логгер для бота
        """
        return LoggingConfig.setup_logger("nutriai.bot", "bot", level)

    @staticmethod
    def setup_worker_logging(level: int = logging.INFO) -> logging.Logger:
        """
        Настраивает логирование для Celery Worker.

        Args:
            level: Уровень логирования для консоли

        Returns:
            Логгер для воркера
        """
        return LoggingConfig.setup_logger("nutriai.worker", "worker", level)

    @staticmethod
    def setup_beat_logging(level: int = logging.INFO) -> logging.Logger:
        """
        Настраивает логирование для Celery Beat (планировщик).

        Args:
            level: Уровень логирования для консоли

        Returns:
            Логгер для планировщика
        """
        return LoggingConfig.setup_logger("nutriai.beat", "beat", level)

    @staticmethod
    def cleanup_old_logs(days: int = 30):
        """
        Удаляет логи старше указанного количества дней.

        Args:
            days: Количество дней (по умолчанию 30)
        """
        import time
        from datetime import datetime, timedelta

        cutoff_time = time.time() - (days * 24 * 60 * 60)
        deleted_count = 0

        for component_dir in LOG_BASE_DIR.iterdir():
            if component_dir.is_dir():
                for log_file in component_dir.glob("*.log*"):
                    if log_file.stat().st_mtime < cutoff_time:
                        try:
                            log_file.unlink()
                            deleted_count += 1
                            print(f"Удален старый лог: {log_file}")
                        except Exception as e:
                            print(f"Ошибка удаления {log_file}: {e}")

        print(f"Очистка завершена. Удалено файлов: {deleted_count}")

    @staticmethod
    def get_logger(component: str) -> logging.Logger:
        """
        Получает существующий логгер для компонента.

        Args:
            component: Тип компонента ('bot', 'worker', 'beat')

        Returns:
            Логгер для компонента
        """
        name_mapping = {
            "bot": "nutriai.bot",
            "worker": "nutriai.worker",
            "beat": "nutriai.beat"
        }

        logger_name = name_mapping.get(component, f"nutriai.{component}")
        logger = logging.getLogger(logger_name)

        # Если логгер еще не настроен, настроить его
        if not logger.handlers:
            setup_method = getattr(
                LoggingConfig,
                f"setup_{component}_logging",
                lambda: LoggingConfig.setup_logger(logger_name, component)
            )
            return setup_method()

        return logger


# Удобные функции для быстрого доступа
def setup_bot_logging(level: int = logging.INFO) -> logging.Logger:
    """Настройка логирования для бота"""
    return LoggingConfig.setup_bot_logging(level)


def setup_worker_logging(level: int = logging.INFO) -> logging.Logger:
    """Настройка логирования для воркера"""
    return LoggingConfig.setup_worker_logging(level)


def setup_beat_logging(level: int = logging.INFO) -> logging.Logger:
    """Настройка логирования для планировщика"""
    return LoggingConfig.setup_beat_logging(level)


def get_logger(component: str) -> logging.Logger:
    """Получение логгера для компонента"""
    return LoggingConfig.get_logger(component)


# Пример использования с дополнительными полями
class LoggerAdapter(logging.LoggerAdapter):
    """
    Адаптер для добавления контекстной информации в логи.

    Использование:
        logger = get_logger("bot")
        adapted_logger = LoggerAdapter(logger, {"user_id": 123, "telegram_id": 456})
        adapted_logger.info("User action", extra={"action": "meal_plan_generated"})
    """

    def process(self, msg, kwargs):
        """Добавляет дополнительные поля к логу"""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs
