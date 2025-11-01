"""
Управление event loop для Celery задач с поддержкой asyncpg и SQLAlchemy

Этот модуль решает проблему "RuntimeError: Event loop is closed" при работе
asyncpg через SQLAlchemy в Celery задачах.

Проблема:
- asyncio.run() создает новый event loop, выполняет код и закрывает loop
- SQLAlchemy engine с пулом соединений существует на уровне модуля
- После закрытия loop, asyncpg соединения в пуле ссылаются на закрытый loop
- Следующая задача пытается использовать соединение с закрытым loop -> RuntimeError

Решение:
- Используем один event loop на весь worker процесс
- Правильно управляем жизненным циклом соединений
- Автоматически очищаем "мертвые" соединения после каждой задачи
"""
import asyncio
import threading
from typing import Callable, TypeVar, Any
from contextlib import asynccontextmanager
from loguru import logger
import sys

T = TypeVar('T')

# Thread-local хранилище для event loop каждого worker процесса
_thread_local = threading.local()


def get_or_create_event_loop() -> asyncio.AbstractEventLoop:
    """
    Получить или создать event loop для текущего потока

    Для каждого Celery worker процесса создается один event loop,
    который переиспользуется для всех задач в этом процессе.

    Returns:
        asyncio.AbstractEventLoop: Event loop для текущего потока
    """
    # Проверяем, есть ли уже loop в thread-local хранилище
    if not hasattr(_thread_local, 'loop') or _thread_local.loop is None or _thread_local.loop.is_closed():
        # Создаем новый loop
        if sys.platform == 'win32':
            # На Windows используем ProactorEventLoop для поддержки subprocesses
            loop = asyncio.WindowsProactorEventLoopPolicy().new_event_loop()
        else:
            # На Unix используем стандартный EventLoop
            loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)
        _thread_local.loop = loop
        logger.info(f"[EventLoop] Created new event loop for thread {threading.current_thread().name}")

    return _thread_local.loop


def run_async_task(coro: Callable[..., Any], *args, **kwargs) -> Any:
    """
    Выполнить асинхронную задачу с правильным управлением event loop

    Эта функция:
    1. Получает или создает event loop для текущего worker процесса
    2. Выполняет асинхронную функцию
    3. НЕ закрывает event loop (он будет переиспользован)
    4. Очищает pending tasks после выполнения

    Args:
        coro: Асинхронная функция для выполнения
        *args: Позиционные аргументы для функции
        **kwargs: Именованные аргументы для функции

    Returns:
        Any: Результат выполнения асинхронной функции

    Raises:
        Exception: Любая ошибка, возникшая при выполнении
    """
    loop = get_or_create_event_loop()

    try:
        # Выполняем корутину в существующем loop
        result = loop.run_until_complete(coro(*args, **kwargs))

        # Очищаем все pending tasks (важно для предотвращения утечек памяти)
        _cleanup_pending_tasks(loop)

        return result

    except Exception as exc:
        logger.error(f"[EventLoop] Error executing async task: {exc}")
        # Очищаем pending tasks даже при ошибке
        _cleanup_pending_tasks(loop)
        raise


def _cleanup_pending_tasks(loop: asyncio.AbstractEventLoop) -> None:
    """
    Очистить все pending tasks в event loop

    Это важно для предотвращения утечек памяти и предупреждений
    "Task was destroyed but it is pending!"

    Args:
        loop: Event loop для очистки
    """
    try:
        # Получаем все pending tasks
        pending = asyncio.all_tasks(loop)

        if pending:
            logger.debug(f"[EventLoop] Cleaning up {len(pending)} pending tasks")

            # Отменяем все pending tasks
            for task in pending:
                task.cancel()

            # Даем loop шанс обработать отмененные tasks
            # Используем wait_for с timeout чтобы не зависнуть
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        asyncio.gather(*pending, return_exceptions=True),
                        timeout=5.0
                    )
                )
            except asyncio.TimeoutError:
                logger.warning("[EventLoop] Timeout while cleaning up pending tasks")
            except Exception as e:
                # Игнорируем CancelledError и другие ожидаемые ошибки
                if not isinstance(e, asyncio.CancelledError):
                    logger.warning(f"[EventLoop] Error during cleanup: {e}")

    except Exception as e:
        logger.warning(f"[EventLoop] Failed to cleanup pending tasks: {e}")


@asynccontextmanager
async def managed_session_scope(session_maker):
    """
    Context manager для безопасной работы с SQLAlchemy сессией

    Гарантирует правильное закрытие сессии даже при ошибках,
    что критично для корректной работы пула соединений.

    Usage:
        async with managed_session_scope(async_session_maker) as session:
            # работа с session
            ...

    Args:
        session_maker: async_sessionmaker из SQLAlchemy

    Yields:
        AsyncSession: SQLAlchemy сессия
    """
    session = session_maker()
    try:
        yield session
        # Коммит только если не было ошибок
        await session.commit()
    except Exception as e:
        # Откатываем транзакцию при ошибке
        await session.rollback()
        logger.error(f"[EventLoop] Session error, rolled back: {e}")
        raise
    finally:
        # Всегда закрываем сессию
        try:
            await session.close()
        except Exception as e:
            # Логируем, но не пробрасываем ошибку закрытия
            logger.warning(f"[EventLoop] Error closing session: {e}")


def cleanup_worker_event_loop() -> None:
    """
    Очистить event loop при завершении worker процесса

    Эта функция должна вызываться при shutdown worker'а
    для корректного закрытия всех ресурсов.
    """
    if hasattr(_thread_local, 'loop') and _thread_local.loop is not None:
        loop = _thread_local.loop

        try:
            logger.info("[EventLoop] Cleaning up worker event loop")

            # Очищаем pending tasks
            _cleanup_pending_tasks(loop)

            # Закрываем loop
            if not loop.is_closed():
                loop.close()

            _thread_local.loop = None
            logger.info("[EventLoop] Worker event loop closed successfully")

        except Exception as e:
            logger.error(f"[EventLoop] Error during worker cleanup: {e}")
