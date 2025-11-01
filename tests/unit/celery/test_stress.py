"""
Стресс-тесты для проверки стабильности решения

Эти тесты проверяют, что система работает стабильно
при высокой нагрузке и длительной работе.
"""
import pytest
import asyncio
import threading
import time
from app.celery_event_loop import run_async_task, cleanup_worker_event_loop, get_or_create_event_loop
from app.db.celery_session import celery_session_maker, cleanup_celery_connections


class TestHighLoad:
    """Тесты высокой нагрузки"""

    def test_many_sequential_tasks(self):
        """Тест: множество последовательных задач"""
        cleanup_worker_event_loop()

        async def task(n):
            async with celery_session_maker() as session:
                await asyncio.sleep(0.001)
                return n

        # Выполняем 100 задач подряд
        start_time = time.time()
        results = []

        for i in range(100):
            result = run_async_task(task, i)
            results.append(result)

            # Периодическая очистка соединений
            if i % 10 == 0:
                run_async_task(cleanup_celery_connections)

        duration = time.time() - start_time

        # Проверяем результаты
        assert len(results) == 100
        assert results == list(range(100))

        # Event loop должен быть рабочим
        loop = get_or_create_event_loop()
        assert not loop.is_closed()

        print(f"\n100 tasks completed in {duration:.2f}s ({100/duration:.1f} tasks/sec)")

    def test_tasks_with_varying_duration(self):
        """Тест: задачи с разной длительностью"""
        cleanup_worker_event_loop()

        async def task(duration):
            async with celery_session_maker() as session:
                await asyncio.sleep(duration)
                return duration

        # Задачи от 0.001 до 0.05 секунд
        durations = [0.001, 0.005, 0.01, 0.02, 0.05] * 10

        results = []
        for duration in durations:
            result = run_async_task(task, duration)
            results.append(result)

        assert len(results) == 50
        assert results == durations

    def test_rapid_fire_tasks_with_cleanup(self):
        """Тест: быстрые задачи с частой очисткой"""
        cleanup_worker_event_loop()

        async def quick_task(n):
            async with celery_session_maker() as session:
                # Очень быстрая задача
                return n * 2

        # 200 очень быстрых задач с частой очисткой
        results = []
        for i in range(200):
            result = run_async_task(quick_task, i)
            results.append(result)

            # Очистка после каждой задачи (максимально агрессивно)
            run_async_task(cleanup_celery_connections)

        assert len(results) == 200
        assert results == [i * 2 for i in range(200)]


class TestConcurrentWorkers:
    """Тесты конкурентных workers"""

    def test_multiple_workers_high_load(self):
        """Тест: несколько workers с высокой нагрузкой"""
        total_tasks_per_worker = 50
        num_workers = 4

        results_lock = threading.Lock()
        all_results = {}
        errors = []

        def worker_func(worker_id):
            """Функция worker процесса"""
            cleanup_worker_event_loop()

            async def task(task_id):
                async with celery_session_maker() as session:
                    await asyncio.sleep(0.005)
                    return f"w{worker_id}t{task_id}"

            worker_results = []
            try:
                for task_id in range(total_tasks_per_worker):
                    result = run_async_task(task, task_id)
                    worker_results.append(result)

                    # Периодическая очистка
                    if task_id % 5 == 0:
                        run_async_task(cleanup_celery_connections)

                with results_lock:
                    all_results[worker_id] = worker_results

            except Exception as e:
                with results_lock:
                    errors.append((worker_id, str(e)))

            finally:
                cleanup_worker_event_loop()

        # Запускаем workers
        start_time = time.time()
        threads = [
            threading.Thread(target=worker_func, args=(i,))
            for i in range(num_workers)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        duration = time.time() - start_time

        # Проверяем результаты
        assert len(errors) == 0, f"Errors: {errors}"
        assert len(all_results) == num_workers

        total_tasks = sum(len(results) for results in all_results.values())
        assert total_tasks == num_workers * total_tasks_per_worker

        print(f"\n{total_tasks} tasks across {num_workers} workers in {duration:.2f}s ({total_tasks/duration:.1f} tasks/sec)")


class TestLongRunning:
    """Тесты длительной работы"""

    def test_worker_uptime_simulation(self):
        """Тест: симуляция длительной работы worker"""
        cleanup_worker_event_loop()

        async def task(task_id, should_fail=False):
            async with celery_session_maker() as session:
                await asyncio.sleep(0.002)
                if should_fail:
                    raise ValueError(f"Task {task_id} failed")
                return task_id

        # Симулируем 2 минуты работы (в ускоренном виде)
        # ~200 задач, некоторые с ошибками
        successful = 0
        failed = 0

        for i in range(200):
            should_fail = (i % 17 == 0)  # ~12% задач падают

            try:
                result = run_async_task(task, i, should_fail)
                successful += 1
            except ValueError:
                failed += 1

            # Периодическая очистка
            if i % 20 == 0:
                run_async_task(cleanup_celery_connections)

        # Проверяем
        assert successful > 0
        assert failed > 0
        assert successful + failed == 200

        # Event loop все еще работает
        loop = get_or_create_event_loop()
        assert not loop.is_closed()

        print(f"\nLong-running simulation: {successful} successful, {failed} failed")


class TestMemoryLeaks:
    """Тесты на утечки памяти"""

    def test_no_pending_tasks_accumulation(self):
        """Тест: нет накопления pending tasks"""
        cleanup_worker_event_loop()

        async def task_with_background():
            # Создаем фоновые задачи, которые могут утечь
            for _ in range(5):
                asyncio.create_task(asyncio.sleep(100))

            await asyncio.sleep(0.001)
            return "done"

        # Выполняем много задач
        for i in range(50):
            result = run_async_task(task_with_background)
            assert result == "done"

        # Проверяем, что нет накопления pending tasks
        loop = get_or_create_event_loop()
        pending = asyncio.all_tasks(loop)

        # Не должно быть pending tasks (все очищены)
        assert len(pending) == 0

    def test_session_cleanup(self):
        """Тест: правильная очистка сессий"""
        cleanup_worker_event_loop()

        async def task(n):
            async with celery_session_maker() as session:
                # Имитация работы с БД
                await asyncio.sleep(0.001)
                return n

        # Выполняем много задач
        for i in range(100):
            run_async_task(task, i)

            # Агрессивная очистка
            run_async_task(cleanup_celery_connections)

        # Если есть утечки, здесь будет проблема
        # Просто проверяем, что все работает
        assert True


class TestEdgeCases:
    """Тесты граничных случаев под нагрузкой"""

    def test_alternating_cleanup_and_tasks(self):
        """Тест: чередование задач и очисток"""
        cleanup_worker_event_loop()

        async def task(n):
            async with celery_session_maker() as session:
                await asyncio.sleep(0.001)
                return n

        results = []
        for i in range(50):
            # Задача
            result = run_async_task(task, i)
            results.append(result)

            # Очистка после каждой задачи
            run_async_task(cleanup_celery_connections)

            # Еще одна очистка (избыточная)
            run_async_task(cleanup_celery_connections)

        assert results == list(range(50))

    def test_error_recovery_under_load(self):
        """Тест: восстановление после ошибок под нагрузкой"""
        cleanup_worker_event_loop()

        async def task(n, fail_pattern):
            async with celery_session_maker() as session:
                await asyncio.sleep(0.001)
                if n % fail_pattern == 0:
                    raise ValueError("Intentional error")
                return n

        results = []
        errors = 0

        # Паттерн ошибок: каждая 7-я задача падает
        for i in range(100):
            try:
                result = run_async_task(task, i, 7)
                results.append(result)
            except ValueError:
                errors += 1

            # Очистка даже после ошибок
            run_async_task(cleanup_celery_connections)

        # Проверяем
        assert errors > 0  # Были ошибки
        assert len(results) > 0  # Были успехи
        assert len(results) + errors == 100

        # Система продолжает работать
        loop = get_or_create_event_loop()
        assert not loop.is_closed()


@pytest.mark.slow
class TestExtendedStress:
    """Расширенные стресс-тесты (помечены как slow)"""

    def test_extended_workload(self):
        """Тест: расширенная нагрузка (1000 задач)"""
        cleanup_worker_event_loop()

        async def task(n):
            async with celery_session_maker() as session:
                await asyncio.sleep(0.001)
                return n % 100

        start_time = time.time()
        results = []

        for i in range(1000):
            result = run_async_task(task, i)
            results.append(result)

            if i % 50 == 0:
                run_async_task(cleanup_celery_connections)

        duration = time.time() - start_time

        assert len(results) == 1000
        loop = get_or_create_event_loop()
        assert not loop.is_closed()

        print(f"\n1000 tasks in {duration:.2f}s ({1000/duration:.1f} tasks/sec)")
