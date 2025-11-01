"""
Тесты для модуля celery_event_loop

Проверяем корректность управления event loop в Celery задачах
"""
import pytest
import asyncio
import threading
from app.celery_event_loop import (
    get_or_create_event_loop,
    run_async_task,
    cleanup_worker_event_loop,
    managed_session_scope,
    _cleanup_pending_tasks
)


class TestEventLoopManagement:
    """Тесты управления event loop"""

    def test_get_or_create_event_loop_creates_new_loop(self):
        """Тест: создание нового event loop"""
        # Очищаем перед тестом
        cleanup_worker_event_loop()

        loop = get_or_create_event_loop()

        assert loop is not None
        assert isinstance(loop, asyncio.AbstractEventLoop)
        assert not loop.is_closed()

    def test_get_or_create_event_loop_reuses_existing_loop(self):
        """Тест: переиспользование существующего loop"""
        cleanup_worker_event_loop()

        loop1 = get_or_create_event_loop()
        loop2 = get_or_create_event_loop()

        # Должен вернуть тот же loop
        assert loop1 is loop2

    def test_get_or_create_event_loop_recreates_closed_loop(self):
        """Тест: пересоздание закрытого loop"""
        cleanup_worker_event_loop()

        loop1 = get_or_create_event_loop()
        loop1.close()

        loop2 = get_or_create_event_loop()

        # Должен создать новый loop
        assert loop2 is not loop1
        assert not loop2.is_closed()

    def test_cleanup_worker_event_loop(self):
        """Тест: очистка event loop"""
        cleanup_worker_event_loop()
        loop = get_or_create_event_loop()

        cleanup_worker_event_loop()

        assert loop.is_closed()


class TestRunAsyncTask:
    """Тесты выполнения асинхронных задач"""

    def test_run_async_task_executes_coroutine(self):
        """Тест: выполнение простой корутины"""
        cleanup_worker_event_loop()

        async def simple_task():
            await asyncio.sleep(0.01)
            return "success"

        result = run_async_task(simple_task)

        assert result == "success"

    def test_run_async_task_with_arguments(self):
        """Тест: выполнение корутины с аргументами"""
        cleanup_worker_event_loop()

        async def task_with_args(a, b, c=None):
            await asyncio.sleep(0.01)
            return f"{a}-{b}-{c}"

        result = run_async_task(task_with_args, "x", "y", c="z")

        assert result == "x-y-z"

    def test_run_async_task_handles_exceptions(self):
        """Тест: обработка исключений"""
        cleanup_worker_event_loop()

        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            run_async_task(failing_task)

    def test_run_async_task_multiple_times(self):
        """Тест: множественное выполнение задач"""
        cleanup_worker_event_loop()

        async def counter_task(n):
            await asyncio.sleep(0.01)
            return n * 2

        # Выполняем несколько задач подряд
        results = [run_async_task(counter_task, i) for i in range(5)]

        assert results == [0, 2, 4, 6, 8]

    def test_run_async_task_cleans_up_pending_tasks(self):
        """Тест: очистка pending tasks"""
        cleanup_worker_event_loop()

        async def task_with_background():
            # Создаем background task, который не будет awaited
            asyncio.create_task(asyncio.sleep(100))
            await asyncio.sleep(0.01)
            return "done"

        result = run_async_task(task_with_background)

        assert result == "done"

        # Проверяем, что нет pending tasks
        loop = get_or_create_event_loop()
        pending = asyncio.all_tasks(loop)
        assert len(pending) == 0


class TestManagedSessionScope:
    """Тесты для managed_session_scope"""

    def test_managed_session_scope_commits_on_success(self):
        """Тест: commit при успешном выполнении"""
        cleanup_worker_event_loop()

        # Мок session maker
        class MockSession:
            def __init__(self):
                self.committed = False
                self.rolled_back = False
                self.closed = False

            async def commit(self):
                self.committed = True

            async def rollback(self):
                self.rolled_back = True

            async def close(self):
                self.closed = True

        session_instance = MockSession()

        def mock_session_maker():
            return session_instance

        async def use_session():
            async with managed_session_scope(mock_session_maker) as session:
                assert session is session_instance
                # Успешная операция
                pass

        run_async_task(use_session)

        assert session_instance.committed is True
        assert session_instance.rolled_back is False
        assert session_instance.closed is True

    def test_managed_session_scope_rollbacks_on_error(self):
        """Тест: rollback при ошибке"""
        cleanup_worker_event_loop()

        class MockSession:
            def __init__(self):
                self.committed = False
                self.rolled_back = False
                self.closed = False

            async def commit(self):
                self.committed = True

            async def rollback(self):
                self.rolled_back = True

            async def close(self):
                self.closed = True

        session_instance = MockSession()

        def mock_session_maker():
            return session_instance

        async def use_session_with_error():
            async with managed_session_scope(mock_session_maker) as session:
                raise ValueError("Test error")

        with pytest.raises(ValueError):
            run_async_task(use_session_with_error)

        assert session_instance.committed is False
        assert session_instance.rolled_back is True
        assert session_instance.closed is True


class TestThreadSafety:
    """Тесты потокобезопасности"""

    def test_different_threads_get_different_loops(self):
        """Тест: разные потоки получают разные loops"""
        cleanup_worker_event_loop()

        results = {}

        def thread_func(thread_id):
            loop = get_or_create_event_loop()
            results[thread_id] = loop

        threads = [
            threading.Thread(target=thread_func, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Проверяем, что каждый поток получил свой loop
        loops = list(results.values())
        assert len(loops) == 3
        assert len(set(id(loop) for loop in loops)) == 3  # Все разные

    def test_concurrent_tasks_in_different_threads(self):
        """Тест: конкурентное выполнение задач в разных потоках"""
        results = {}

        def thread_func(thread_id):
            cleanup_worker_event_loop()

            async def task():
                await asyncio.sleep(0.01)
                return f"thread-{thread_id}"

            result = run_async_task(task)
            results[thread_id] = result

        threads = [
            threading.Thread(target=thread_func, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        assert results == {0: "thread-0", 1: "thread-1", 2: "thread-2"}


class TestEdgeCases:
    """Тесты граничных случаев"""

    def test_cleanup_pending_tasks_with_no_tasks(self):
        """Тест: очистка без pending tasks"""
        cleanup_worker_event_loop()
        loop = get_or_create_event_loop()

        # Не должно вызвать ошибок
        _cleanup_pending_tasks(loop)

    def test_multiple_cleanups(self):
        """Тест: множественная очистка"""
        cleanup_worker_event_loop()
        get_or_create_event_loop()

        # Должно работать без ошибок
        cleanup_worker_event_loop()
        cleanup_worker_event_loop()
        cleanup_worker_event_loop()

    def test_run_async_task_after_cleanup(self):
        """Тест: выполнение задачи после очистки"""
        cleanup_worker_event_loop()
        get_or_create_event_loop()
        cleanup_worker_event_loop()

        async def task():
            await asyncio.sleep(0.01)
            return "recreated"

        # Должен создать новый loop и выполнить задачу
        result = run_async_task(task)

        assert result == "recreated"
