"""
Celery tasks package
"""
from app.tasks.meal_plan_tasks import (
    generate_meal_plan_task,
    notify_user_plan_ready
)

__all__ = [
    'generate_meal_plan_task',
    'notify_user_plan_ready'
]
