"""
Celery приложение для фоновой обработки задач
"""
from celery import Celery
from app.config import settings

# Создание Celery приложения
celery_app = Celery(
    'nutriai',
    broker=settings.REDIS_URL,           # Redis как брокер сообщений
    backend=settings.REDIS_URL,          # Redis для хранения результатов
    include=['app.tasks.meal_plan_tasks']  # Автоматически импортировать задачи
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
