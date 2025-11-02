"""
Celery tasks package

ВАЖНО: Все задачи должны быть импортированы здесь для их автоматической регистрации в Celery
"""
from app.tasks.meal_plan_tasks import (
    generate_meal_plan_task,
    notify_user_plan_ready
)
from app.tasks.cached_meal_plan_tasks import (
    update_cached_meal_plans_task,
    cleanup_unused_cached_plans_task,
    deactivate_expired_plans_task,
    initialize_cached_plans_for_new_user_task
)

__all__ = [
    # Основные задачи планов питания
    'generate_meal_plan_task',
    'notify_user_plan_ready',

    # Задачи кэширования и обслуживания
    'update_cached_meal_plans_task',
    'cleanup_unused_cached_plans_task',
    'deactivate_expired_plans_task',
    'initialize_cached_plans_for_new_user_task'
]
