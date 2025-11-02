#!/usr/bin/env python3
"""
Тестовый скрипт для проверки регистрации Celery задач

Запуск: python test_celery_tasks.py
"""
import sys
import os

# Добавляем корневую директорию проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_celery_tasks_registration():
    """
    Тест регистрации всех периодических задач в Celery
    """
    print("="*60)
    print("🧪 ТЕСТ РЕГИСТРАЦИИ CELERY ЗАДАЧ")
    print("="*60)

    try:
        # Импортируем Celery app
        from app.celery_app import celery_app

        print("✅ Celery app импортирован успешно")

        # Получаем список зарегистрированных задач
        registered_tasks = list(celery_app.tasks.keys())

        print(f"\n📋 Всего зарегистрировано задач: {len(registered_tasks)}")

        # Задачи которые должны быть зарегистрированы
        expected_tasks = [
            'tasks.generate_meal_plan',
            'tasks.notify_user_plan_ready',
            'tasks.update_cached_meal_plans',
            'tasks.cleanup_unused_cached_plans',
            'tasks.deactivate_expired_plans',
            'tasks.initialize_cached_plans_for_new_user'
        ]

        print("\n🔍 Проверка наличия критических задач:")
        print("-" * 60)

        missing_tasks = []
        for task in expected_tasks:
            if task in registered_tasks:
                print(f"✅ {task}")
            else:
                print(f"❌ {task} - НЕ НАЙДЕНА!")
                missing_tasks.append(task)

        # Проверяем расписание Celery Beat
        print("\n📅 Проверка Celery Beat расписания:")
        print("-" * 60)

        beat_schedule = celery_app.conf.beat_schedule

        for schedule_name, schedule_config in beat_schedule.items():
            task_name = schedule_config['task']
            schedule = schedule_config['schedule']

            if task_name in registered_tasks:
                print(f"✅ {schedule_name}")
                print(f"   Задача: {task_name}")
                print(f"   Расписание: {schedule}")
            else:
                print(f"❌ {schedule_name}")
                print(f"   Задача {task_name} НЕ ЗАРЕГИСТРИРОВАНА!")
                if task_name not in missing_tasks:
                    missing_tasks.append(task_name)

        # Финальный результат
        print("\n" + "="*60)
        if missing_tasks:
            print(f"❌ ТЕСТ ПРОВАЛЕН! Не найдено задач: {len(missing_tasks)}")
            for task in missing_tasks:
                print(f"   - {task}")
            return False
        else:
            print("✅ ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
            print("✅ Все критические задачи зарегистрированы")
            print("✅ Celery Beat расписание настроено корректно")
            return True

    except Exception as e:
        print(f"❌ ОШИБКА ПРИ ТЕСТИРОВАНИИ: {e}")
        import traceback
        print(traceback.format_exc())
        return False

    finally:
        print("="*60)


if __name__ == "__main__":
    success = test_celery_tasks_registration()
    sys.exit(0 if success else 1)
