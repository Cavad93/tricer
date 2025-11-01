"""
Интеграционные тесты для Celery задач

Проверяем работу задач с реальной БД (или моками)
и правильное управление event loop
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from app.celery_event_loop import run_async_task, cleanup_worker_event_loop
from app.db.celery_session import celery_session_maker, cleanup_celery_connections


class TestCelerySessionIntegration:
    """Тесты интеграции с БД через celery_session_maker"""

    def test_celery_session_maker_creates_session(self):
        """Тест: создание сессии"""
        cleanup_worker_event_loop()

        async def create_session():
            async with celery_session_maker() as session:
                assert session is not None
                return True

        result = run_async_task(create_session)
        assert result is True

    def test_multiple_sequential_sessions(self):
        """Тест: множественные последовательные сессии"""
        cleanup_worker_event_loop()

        async def use_session(session_id):
            async with celery_session_maker() as session:
                # Имитация работы с БД
                await asyncio.sleep(0.01)
                return f"session-{session_id}"

        # Выполняем несколько сессий подряд
        results = [run_async_task(use_session, i) for i in range(5)]

        assert results == [f"session-{i}" for i in range(5)]

    def test_cleanup_celery_connections(self):
        """Тест: очистка соединений"""
        cleanup_worker_event_loop()

        async def test_cleanup():
            # Создаем сессию
            async with celery_session_maker() as session:
                await asyncio.sleep(0.01)

            # Очищаем соединения
            await cleanup_celery_connections()

            # Должно работать без ошибок
            return True

        result = run_async_task(test_cleanup)
        assert result is True

    def test_session_after_connection_cleanup(self):
        """Тест: создание сессии после очистки соединений"""
        cleanup_worker_event_loop()

        async def test_scenario():
            # Первая сессия
            async with celery_session_maker() as session:
                await asyncio.sleep(0.01)

            # Очистка
            await cleanup_celery_connections()

            # Вторая сессия (должна создать новое соединение)
            async with celery_session_maker() as session:
                await asyncio.sleep(0.01)

            return True

        result = run_async_task(test_scenario)
        assert result is True


class TestEventLoopStability:
    """Тесты стабильности event loop"""

    def test_event_loop_survives_multiple_tasks(self):
        """Тест: event loop стабилен при множественных задачах"""
        cleanup_worker_event_loop()

        async def task(n):
            await asyncio.sleep(0.01)
            return n * 2

        # Выполняем много задач подряд
        results = [run_async_task(task, i) for i in range(20)]

        assert results == [i * 2 for i in range(20)]

        # Event loop должен быть все еще рабочим
        from app.celery_event_loop import get_or_create_event_loop
        loop = get_or_create_event_loop()
        assert not loop.is_closed()

    def test_event_loop_handles_task_errors(self):
        """Тест: event loop стабилен при ошибках в задачах"""
        cleanup_worker_event_loop()

        async def failing_task(should_fail):
            await asyncio.sleep(0.01)
            if should_fail:
                raise ValueError("Test error")
            return "success"

        # Чередуем успешные и неуспешные задачи
        results = []
        for i in range(10):
            try:
                result = run_async_task(failing_task, i % 2 == 0)
                results.append(result)
            except ValueError:
                results.append("error")

        # Должны быть и успехи, и ошибки
        assert "success" in results
        assert "error" in results

        # Event loop должен быть рабочим
        from app.celery_event_loop import get_or_create_event_loop
        loop = get_or_create_event_loop()
        assert not loop.is_closed()


class TestSimulatedCeleryWorkflow:
    """Тесты, симулирующие реальный Celery workflow"""

    def test_simulated_task_lifecycle(self):
        """Тест: симуляция жизненного цикла Celery задачи"""
        # Имитация старта worker
        cleanup_worker_event_loop()

        async def mock_generate_plan(user_id):
            """Имитация generate_meal_plan_task"""
            async with celery_session_maker() as session:
                # Имитация работы с БД
                await asyncio.sleep(0.02)
                return {"plan_id": user_id, "status": "success"}

        # Выполняем несколько "задач"
        task_results = []
        for user_id in range(5):
            try:
                result = run_async_task(mock_generate_plan, user_id)
                task_results.append(result)

                # Очистка после задачи (как в task_postrun)
                run_async_task(cleanup_celery_connections)
            except Exception as e:
                task_results.append({"error": str(e)})

        # Все задачи должны быть успешными
        assert len(task_results) == 5
        assert all(r.get("status") == "success" for r in task_results)

        # Имитация shutdown worker
        cleanup_worker_event_loop()

    def test_simulated_concurrent_workers(self):
        """Тест: симуляция нескольких worker процессов"""
        import threading

        results = {}
        errors = {}

        def worker_process(worker_id):
            """Симуляция отдельного worker процесса"""
            # Каждый worker имеет свой event loop
            cleanup_worker_event_loop()

            async def task(task_id):
                async with celery_session_maker() as session:
                    await asyncio.sleep(0.01)
                    return f"worker-{worker_id}-task-{task_id}"

            try:
                # Каждый worker выполняет несколько задач
                worker_results = []
                for task_id in range(3):
                    result = run_async_task(task, task_id)
                    worker_results.append(result)
                    run_async_task(cleanup_celery_connections)

                results[worker_id] = worker_results

            except Exception as e:
                errors[worker_id] = str(e)

            finally:
                cleanup_worker_event_loop()

        # Запускаем 3 "worker процесса"
        threads = [
            threading.Thread(target=worker_process, args=(i,))
            for i in range(3)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Проверяем результаты
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 3

        for worker_id in range(3):
            assert len(results[worker_id]) == 3
            for task_id in range(3):
                assert results[worker_id][task_id] == f"worker-{worker_id}-task-{task_id}"


class TestErrorRecovery:
    """Тесты восстановления после ошибок"""

    def test_recovery_from_session_error(self):
        """Тест: восстановление после ошибки сессии"""
        cleanup_worker_event_loop()

        async def task_with_session_error():
            try:
                async with celery_session_maker() as session:
                    # Имитация ошибки
                    raise ValueError("Database error")
            except ValueError:
                pass

            # Следующая попытка должна работать
            async with celery_session_maker() as session:
                await asyncio.sleep(0.01)
                return "recovered"

        result = run_async_task(task_with_session_error)
        assert result == "recovered"

    def test_recovery_from_event_loop_cleanup(self):
        """Тест: восстановление после очистки event loop"""
        cleanup_worker_event_loop()

        async def task1():
            return "task1"

        result1 = run_async_task(task1)
        assert result1 == "task1"

        # Очищаем event loop (имитация критической ошибки)
        cleanup_worker_event_loop()

        # Следующая задача должна работать (создаст новый loop)
        async def task2():
            return "task2"

        result2 = run_async_task(task2)
        assert result2 == "task2"
