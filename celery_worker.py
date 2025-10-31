#!/usr/bin/env python
"""
Запуск Celery Worker для обработки фоновых задач

Usage:
    python celery_worker.py

Or with Celery CLI:
    celery -A app.celery_app worker --loglevel=info
"""
from app.celery_app import celery_app

if __name__ == '__main__':
    # Запускаем воркер
    celery_app.start()
