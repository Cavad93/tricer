"""
JSON Formatter для структурированного логирования.

Преобразует LogRecord в JSON формат для удобного парсинга и анализа.
"""

import json
import logging
import traceback
from datetime import datetime
from typing import Any, Dict


class JSONFormatter(logging.Formatter):
    """
    Форматтер для вывода логов в JSON формате.

    Преобразует LogRecord в структурированный JSON для:
    - Легкого парсинга логов автоматизированными системами
    - Удобного поиска и фильтрации
    - Интеграции с системами мониторинга (ELK, Grafana, etc.)
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Форматирует LogRecord в JSON строку.

        Args:
            record: Объект LogRecord для форматирования

        Returns:
            JSON строка с данными лога
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Добавляем информацию о процессе и потоке
        if record.process:
            log_data["process_id"] = record.process
            log_data["process_name"] = record.processName

        if record.thread:
            log_data["thread_id"] = record.thread
            log_data["thread_name"] = record.threadName

        # Добавляем exception информацию если есть
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }

        # Добавляем дополнительные поля из extra
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'telegram_id'):
            log_data["telegram_id"] = record.telegram_id
        if hasattr(record, 'task_id'):
            log_data["task_id"] = record.task_id
        if hasattr(record, 'duration'):
            log_data["duration"] = record.duration

        return json.dumps(log_data, ensure_ascii=False, default=str)
