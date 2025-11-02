"""
Celery приложение для фоновой обработки задач

Включает обработчики сигналов для правильного управления
event loop и database соединениями
"""
from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown, task_postrun
from app.config import settings
from loguru import logger

# Создание Celery приложения
celery_app = Celery(
    'nutriai',
    broker=settings.REDIS_URL,           # Redis как брокер сообщений
    backend=settings.REDIS_URL,          # Redis для хранения результатов
    include=[
        'app.tasks.meal_plan_tasks',
        'app.tasks.cached_meal_plan_tasks'  # ИСПРАВЛЕНО: Добавлен импорт кэшированных задач
    ]
)

# Конфигурация Celery
celery_app.conf.update(
    # === СЕРИАЛИЗАЦИЯ ===
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # === ПРОИЗВОДИТЕЛЬНОСТЬ ===
    worker_prefetch_multiplier=1,        # Сколько задач брать за раз (1 = по одной)
    worker_max_tasks_per_child=100,      # Перезапуск worker после 100 задач (против утечек памяти)
    task_acks_late=True,                 # Подтверждать задачу после выполнения (не до)

    # === RETRY НАСТРОЙКИ ===
    task_default_retry_delay=30,         # Задержка между retry (30 сек)
    task_max_retries=3,                  # Максимум попыток по умолчанию

    # === ТАЙМАУТЫ ===
    task_soft_time_limit=300,            # Мягкий лимит: 5 минут (warning)
    task_time_limit=360,                 # Жёсткий лимит: 6 минут (kill)

    # === РЕЗУЛЬТАТЫ ===
    result_expires=3600,                 # Хранить результаты 1 час
    result_backend_transport_options={
        'master_name': 'mymaster'
    },

    # === ЛОГИРОВАНИЕ ===
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
)

# Автоопределение задач из модулей
celery_app.autodiscover_tasks(['app.tasks'])


# === CELERY BEAT SCHEDULE (Периодические задачи) ===
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Обновление кэшированных планов питания (каждый день в 2:00 UTC)
    'update-cached-meal-plans': {
        'task': 'tasks.update_cached_meal_plans',
        'schedule': crontab(hour=2, minute=0),  # Каждый день в 2:00
        'options': {
            'expires': 3600,  # Задача истекает через 1 час если не выполнена
        }
    },

    # Очистка неиспользуемых кэшированных планов (каждое воскресенье в 3:00 UTC)
    'cleanup-unused-cached-plans': {
        'task': 'tasks.cleanup_unused_cached_plans',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),  # Воскресенье 3:00
        'options': {
            'expires': 3600,
        }
    },

    # Деактивация истекших планов питания (каждый день в 1:00 UTC)
    'deactivate-expired-meal-plans': {
        'task': 'tasks.deactivate_expired_plans',
        'schedule': crontab(hour=1, minute=0),  # Каждый день в 1:00
        'options': {
            'expires': 600,
        }
    },
}


# === ОБРАБОТЧИКИ СИГНАЛОВ ДЛЯ УПРАВЛЕНИЯ РЕСУРСАМИ ===

@worker_process_init.connect
def init_worker_process(**kwargs):
    """
    Инициализация worker процесса

    Вызывается при старте каждого worker процесса.
    Здесь можно инициализировать ресурсы, специфичные для процесса.
    """
    logger.info("[Celery] Worker process initialized")

    # Event loop будет создан автоматически при первой задаче
    # благодаря get_or_create_event_loop() в celery_event_loop.py


@worker_process_shutdown.connect
def shutdown_worker_process(**kwargs):
    """
    Завершение worker процесса

    Вызывается при остановке worker процесса.
    Критично важно правильно очистить все ресурсы.
    """
    logger.info("[Celery] Worker process shutting down, cleaning up resources...")

    try:
        # Очищаем event loop
        from app.celery_event_loop import cleanup_worker_event_loop, run_async_task
        cleanup_worker_event_loop()

        # Очищаем database соединения
        from app.db.celery_session import cleanup_celery_connections
        try:
            run_async_task(cleanup_celery_connections)
        except Exception as e:
            # Event loop может быть уже закрыт, это нормально
            logger.warning(f"[Celery] Could not cleanup connections via event loop: {e}")

    except Exception as e:
        logger.error(f"[Celery] Error during worker shutdown: {e}")

    logger.info("[Celery] Worker process shutdown complete")


@task_postrun.connect
def cleanup_after_task(sender=None, task_id=None, task=None, **kwargs):
    """
    Очистка после выполнения каждой задачи

    ВАЖНО: Это дополнительный уровень защиты.
    Даже если задача забыла очистить соединения в finally блоке,
    этот обработчик гарантирует очистку.

    Вызывается после завершения каждой задачи (успешной или с ошибкой).
    """
    try:
        logger.debug(f"[Celery] Post-run cleanup for task {task.name}[{task_id}]")

        # Периодическая проверка и очистка соединений
        # (это быстрая операция благодаря pool_pre_ping)
        from app.celery_event_loop import run_async_task
        from app.db.celery_session import cleanup_celery_connections

        try:
            run_async_task(cleanup_celery_connections)
        except Exception as e:
            # Логируем, но не падаем - это не критическая ошибка
            logger.debug(f"[Celery] Post-task cleanup skipped: {e}")

    except Exception as e:
        # Никогда не роняем Celery из-за ошибки очистки
        logger.warning(f"[Celery] Error in post-task cleanup: {e}")
