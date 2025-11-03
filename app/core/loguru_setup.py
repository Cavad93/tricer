"""
Интеграция Loguru с профессиональной системой логирования.

Настраивает loguru для записи в структурированные файлы логов
с ротацией, автоочисткой и разделением по уровням.
"""

import sys
from pathlib import Path
from loguru import logger


LOG_BASE_DIR = Path("logs")
MAX_SIZE = "50 MB"
RETENTION = "30 days"
COMPRESSION = "zip"


def setup_bot_logger(level: str = "INFO"):
    """
    Настраивает loguru для Telegram бота.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Настроенный logger
    """
    # Удаляем стандартный обработчик
    logger.remove()

    # Создаем директорию для логов бота
    bot_dir = LOG_BASE_DIR / "bot"
    bot_dir.mkdir(parents=True, exist_ok=True)

    # 1. Console handler - для разработки
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # 2. ALL.LOG - Все уровни (DEBUG и выше)
    logger.add(
        bot_dir / "all.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation=MAX_SIZE,
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
    )

    # 3. INFO.LOG - INFO и выше (без DEBUG)
    logger.add(
        bot_dir / "info.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="INFO",
        rotation="00:00",  # Ротация в полночь
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
    )

    # 4. ERROR.LOG - Только ERROR и CRITICAL
    logger.add(
        bot_dir / "error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message} | {extra}",
        level="ERROR",
        rotation=MAX_SIZE,
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # 5. STRUCTURED.JSON - JSON формат
    logger.add(
        bot_dir / "structured.json",
        format=_json_serialize,
        level="DEBUG",
        rotation="00:00",
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
        serialize=True,
    )

    logger.info(f"Bot logging configured. Level: {level}, Directory: {bot_dir}")
    return logger


def setup_worker_logger(level: str = "INFO"):
    """
    Настраивает loguru для Celery Worker.

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Настроенный logger
    """
    # Удаляем стандартный обработчик
    logger.remove()

    # Создаем директорию для логов воркера
    worker_dir = LOG_BASE_DIR / "worker"
    worker_dir.mkdir(parents=True, exist_ok=True)

    # 1. Console handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # 2. ALL.LOG
    logger.add(
        worker_dir / "all.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation=MAX_SIZE,
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
    )

    # 3. INFO.LOG
    logger.add(
        worker_dir / "info.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="INFO",
        rotation="00:00",
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
    )

    # 4. ERROR.LOG
    logger.add(
        worker_dir / "error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message} | {extra}",
        level="ERROR",
        rotation=MAX_SIZE,
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # 5. STRUCTURED.JSON
    logger.add(
        worker_dir / "structured.json",
        format=_json_serialize,
        level="DEBUG",
        rotation="00:00",
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
        serialize=True,
    )

    logger.info(f"Worker logging configured. Level: {level}, Directory: {worker_dir}")
    return logger


def setup_beat_logger(level: str = "INFO"):
    """
    Настраивает loguru для Celery Beat (планировщик).

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Настроенный logger
    """
    # Удаляем стандартный обработчик
    logger.remove()

    # Создаем директорию для логов планировщика
    beat_dir = LOG_BASE_DIR / "beat"
    beat_dir.mkdir(parents=True, exist_ok=True)

    # 1. Console handler
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True,
    )

    # 2. ALL.LOG
    logger.add(
        beat_dir / "all.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="DEBUG",
        rotation=MAX_SIZE,
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
    )

    # 3. INFO.LOG
    logger.add(
        beat_dir / "info.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level="INFO",
        rotation="00:00",
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
    )

    # 4. ERROR.LOG
    logger.add(
        beat_dir / "error.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message} | {extra}",
        level="ERROR",
        rotation=MAX_SIZE,
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # 5. STRUCTURED.JSON
    logger.add(
        beat_dir / "structured.json",
        format=_json_serialize,
        level="DEBUG",
        rotation="00:00",
        retention=RETENTION,
        compression=COMPRESSION,
        encoding="utf-8",
        serialize=True,
    )

    logger.info(f"Beat logging configured. Level: {level}, Directory: {beat_dir}")
    return logger


def _json_serialize(record):
    """
    Сериализация записи лога в JSON формат.

    Функция для loguru serialize=True режима.
    """
    # loguru уже предоставляет serialize=True, но мы можем кастомизировать
    return record


# Удобные функции
def get_logger():
    """Получить настроенный логгер"""
    return logger
