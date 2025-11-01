#!/usr/bin/env python
"""
Запуск Celery Beat для периодических задач

Celery Beat отвечает за запуск задач по расписанию (cron-like).
Должен работать в паре с Celery Worker.

Usage:
    python celery_beat.py

Or with Celery CLI:
    celery -A app.celery_app beat --loglevel=info

ВАЖНО: Должен быть запущен только 1 экземпляр Celery Beat!
        Несколько экземпляров приведут к дублированию задач.
"""
from app.celery_app import celery_app
from loguru import logger


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("Запуск Celery Beat (планировщик периодических задач)")
    logger.info("=" * 80)
    logger.info("Расписание задач:")

    for task_name, task_config in celery_app.conf.beat_schedule.items():
        schedule = task_config['schedule']
        logger.info(f"  - {task_name}: {schedule}")

    logger.info("=" * 80)

    # Запускаем beat
    celery_app.start(['beat', '--loglevel=info'])
