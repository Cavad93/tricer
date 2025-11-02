#!/usr/bin/env python3
"""
Простой тест импортов Celery задач (не требует запущенного Redis/Celery)

Запуск: python3 test_celery_imports.py
"""
import sys
import os

# Добавляем корневую директорию проекта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*70)
print("🧪 ТЕСТ ИМПОРТОВ CELERY ЗАДАЧ")
print("="*70)

errors = []

# Тест 1: Импорт celery_app
print("\n1️⃣  Импорт app.celery_app...")
try:
    import app.celery_app
    print("   ✅ app.celery_app импортирован")
except Exception as e:
    print(f"   ❌ ОШИБКА: {e}")
    errors.append(("app.celery_app", str(e)))

# Тест 2: Импорт meal_plan_tasks
print("\n2️⃣  Импорт app.tasks.meal_plan_tasks...")
try:
    import app.tasks.meal_plan_tasks
    print("   ✅ app.tasks.meal_plan_tasks импортирован")
except Exception as e:
    print(f"   ❌ ОШИБКА: {e}")
    errors.append(("app.tasks.meal_plan_tasks", str(e)))

# Тест 3: Импорт cached_meal_plan_tasks
print("\n3️⃣  Импорт app.tasks.cached_meal_plan_tasks...")
try:
    import app.tasks.cached_meal_plan_tasks
    print("   ✅ app.tasks.cached_meal_plan_tasks импортирован")

    # Проверяем наличие задач
    print("   Проверка задач:")
    tasks = [
        'update_cached_meal_plans_task',
        'cleanup_unused_cached_plans_task',
        'deactivate_expired_plans_task',
        'initialize_cached_plans_for_new_user_task'
    ]
    for task_name in tasks:
        if hasattr(app.tasks.cached_meal_plan_tasks, task_name):
            print(f"      ✅ {task_name}")
        else:
            print(f"      ❌ {task_name} НЕ НАЙДЕНА!")
            errors.append((f"cached_meal_plan_tasks.{task_name}", "Задача не определена"))

except Exception as e:
    print(f"   ❌ ОШИБКА: {e}")
    errors.append(("app.tasks.cached_meal_plan_tasks", str(e)))

# Тест 4: Импорт __init__
print("\n4️⃣  Импорт app.tasks.__init__...")
try:
    import app.tasks
    print("   ✅ app.tasks импортирован")

    # Проверяем __all__
    if hasattr(app.tasks, '__all__'):
        print(f"   ℹ️  Экспортируется задач: {len(app.tasks.__all__)}")
        for task in app.tasks.__all__:
            print(f"      • {task}")
    else:
        print("   ⚠️  __all__ не определён")

except Exception as e:
    print(f"   ❌ ОШИБКА: {e}")
    errors.append(("app.tasks", str(e)))

# Финальный результат
print("\n" + "="*70)
if errors:
    print(f"❌ ТЕСТ ПРОВАЛЕН! Найдено ошибок: {len(errors)}")
    print("\nСписок ошибок:")
    for module, error in errors:
        print(f"  • {module}: {error}")
    sys.exit(1)
else:
    print("✅ ВСЕ ИМПОРТЫ ПРОШЛИ УСПЕШНО!")
    print("✅ Все задачи определены корректно")
    print("\n💡 Для проверки регистрации в Celery запустите worker:")
    print("   celery -A app.celery_app worker --loglevel=info")
    sys.exit(0)

print("="*70)
