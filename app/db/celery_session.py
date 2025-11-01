"""
Конфигурация SQLAlchemy специально для Celery задач

Этот модуль создает отдельный engine и session maker для Celery задач
с оптимизированными настройками для предотвращения ошибок event loop.

Отличия от основного engine:
1. Меньший размер пула (Celery worker обрабатывает задачи последовательно)
2. Агрессивная очистка "мертвых" соединений
3. Короткое время жизни соединений
4. Специальные настройки для работы с одним event loop на процесс
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from loguru import logger

# Создаем отдельный async engine для Celery задач
celery_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,

    # === НАСТРОЙКИ ПУЛА ДЛЯ CELERY ===
    # Меньший пул, т.к. Celery обрабатывает задачи последовательно
    pool_size=5,                    # Небольшой пул (5 соединений)
    max_overflow=10,                # Максимум 15 соединений (5 + 10)

    # Критично для предотвращения ошибок с event loop
    pool_pre_ping=True,             # Проверка соединения перед использованием
    pool_recycle=1800,              # Пересоздание соединений каждые 30 минут

    # Быстрый timeout для обнаружения проблем
    pool_timeout=30,                # Ожидание свободного соединения 30 сек

    # === НАСТРОЙКИ СОЕДИНЕНИЙ ===
    connect_args={
        "server_settings": {
            "application_name": "nutriai_celery",  # Отдельное имя для мониторинга
        },
        "command_timeout": 60,      # Таймаут команд 60 сек
        "timeout": 10,              # Таймаут подключения 10 сек
    },

    # === СОБЫТИЯ ПУЛА ДЛЯ ОТЛАДКИ ===
    # Логирование событий пула для мониторинга
    echo_pool=settings.DEBUG,
)

# Создаем фабрику сессий для Celery
celery_session_maker = async_sessionmaker(
    celery_engine,
    class_=AsyncSession,
    expire_on_commit=False,        # Не истекать объекты после commit
)


async def cleanup_celery_connections():
    """
    Очистить все соединения в пуле Celery engine

    Эта функция должна вызываться:
    1. После каждой задачи (для очистки "мертвых" соединений)
    2. При shutdown worker'а

    Помогает предотвратить накопление соединений с закрытым event loop.
    """
    try:
        logger.debug("[CeleryDB] Disposing all connections in pool")

        # Закрываем все соединения в пуле
        await celery_engine.dispose()

        logger.debug("[CeleryDB] Connections disposed successfully")

    except Exception as e:
        logger.error(f"[CeleryDB] Error disposing connections: {e}")


async def check_celery_connection_health() -> bool:
    """
    Проверить здоровье соединений в пуле Celery

    Returns:
        bool: True если соединение работает, False иначе
    """
    try:
        async with celery_session_maker() as session:
            # Простой запрос для проверки соединения
            await session.execute("SELECT 1")
            return True
    except Exception as e:
        logger.error(f"[CeleryDB] Connection health check failed: {e}")
        return False


# Обработчики событий пула для логирования (только в DEBUG режиме)
if settings.DEBUG:
    from sqlalchemy import event

    @event.listens_for(celery_engine.sync_engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Логирование новых соединений"""
        logger.debug("[CeleryDB] New database connection established")

    @event.listens_for(celery_engine.sync_engine, "close")
    def receive_close(dbapi_conn, connection_record):
        """Логирование закрытия соединений"""
        logger.debug("[CeleryDB] Database connection closed")

    @event.listens_for(celery_engine.sync_engine, "checkin")
    def receive_checkin(dbapi_conn, connection_record):
        """Логирование возврата соединения в пул"""
        logger.debug("[CeleryDB] Connection returned to pool")

    @event.listens_for(celery_engine.sync_engine, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        """Логирование получения соединения из пула"""
        logger.debug("[CeleryDB] Connection checked out from pool")
