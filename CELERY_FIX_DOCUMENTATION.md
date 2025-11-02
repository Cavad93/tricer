# 🛠️ Исправление: Незарегистрированные Celery задачи

## 📋 Проблема

При запуске Celery worker появлялись ошибки о незарегистрированных задачах:

```
[ERROR] Received unregistered task of type 'tasks.deactivate_expired_plans'
[ERROR] Received unregistered task of type 'tasks.update_cached_meal_plans'
[ERROR] Received unregistered task of type 'tasks.cleanup_unused_cached_plans'
```

## 🔍 Анализ причин

### Найдено 3 проблемы:

1. **Отсутствие импорта `cached_meal_plan_tasks` в celery_app.py**
   - Файл `app/celery_app.py:17` импортировал только `meal_plan_tasks`
   - Задачи из `cached_meal_plan_tasks.py` не регистрировались в Celery

2. **Отсутствие задачи `deactivate_expired_plans`**
   - В расписании Celery Beat была ссылка на `tasks.deactivate_expired_plans`
   - Но эта задача не существовала как Celery task
   - Был только метод сервиса `MealPlanService.deactivate_expired_plans()`

3. **Неполный экспорт в `__init__.py`**
   - Файл `app/tasks/__init__.py` экспортировал только 2 задачи
   - Остальные задачи не были видны при импорте пакета

## ✅ Решение

### 1. Исправлен `app/celery_app.py`

**Было:**
```python
include=['app.tasks.meal_plan_tasks']
```

**Стало:**
```python
include=[
    'app.tasks.meal_plan_tasks',
    'app.tasks.cached_meal_plan_tasks'  # ДОБАВЛЕНО
]
```

### 2. Создана задача `deactivate_expired_plans_task`

**Добавлено в `app/tasks/cached_meal_plan_tasks.py`:**

```python
@celery_app.task(name='tasks.deactivate_expired_plans')
def deactivate_expired_plans_task():
    """
    Деактивирует истёкшие планы питания.
    Запускается каждый день в 1:00 UTC через Celery Beat.
    """
    try:
        logger.info("🔄 Starting deactivation of expired meal plans...")
        return run_async_task(_deactivate_expired_plans_async)
    finally:
        try:
            run_async_task(cleanup_celery_connections)
        except Exception as cleanup_error:
            logger.warning(f"Error during connection cleanup: {cleanup_error}")


async def _deactivate_expired_plans_async():
    """Асинхронная часть деактивации истёкших планов"""
    try:
        async with celery_session_maker() as session:
            deactivated_count = await MealPlanService.deactivate_expired_plans(session)
            logger.info(f"✅ Deactivated {deactivated_count} expired meal plans")
            return {
                "status": "success",
                "deactivated_count": deactivated_count,
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"❌ Error deactivating expired plans: {repr(e)}")
        raise
```

### 3. Обновлён `app/tasks/__init__.py`

**Было:**
```python
from app.tasks.meal_plan_tasks import (
    generate_meal_plan_task,
    notify_user_plan_ready
)

__all__ = [
    'generate_meal_plan_task',
    'notify_user_plan_ready'
]
```

**Стало:**
```python
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
```

## 🚀 Применение исправлений

### Шаг 1: Обновить код

Код уже обновлён в ветке `claude/medical-risks-rf-laws-011CUjVuaetNQNBPxaQJrP8q`

### Шаг 2: Перезапустить Celery Worker

**КРИТИЧЕСКИ ВАЖНО!** После обновления кода необходимо перезапустить Celery worker:

```bash
# Остановить текущий worker
# В Windows: Ctrl+C в окне с worker
pkill -f "celery.*worker"

# Запустить заново
celery -A app.celery_app worker --loglevel=info --pool=solo
```

### Шаг 3: Перезапустить Celery Beat (если используется)

```bash
# Остановить beat
pkill -f "celery.*beat"

# Запустить заново
celery -A app.celery_app beat --loglevel=info
```

### Шаг 4: Проверить регистрацию задач

После перезапуска worker, в логах должно быть видно:

```
[tasks]
  . tasks.cleanup_unused_cached_plans
  . tasks.deactivate_expired_plans
  . tasks.generate_meal_plan
  . tasks.initialize_cached_plans_for_new_user
  . tasks.notify_user_plan_ready
  . tasks.update_cached_meal_plans
```

Если все 6 задач видны - исправление применено успешно! ✅

## 📊 Celery Beat расписание

После исправления будут работать 3 периодические задачи:

| Задача | Расписание | Описание |
|--------|-----------|----------|
| `deactivate_expired_plans` | Каждый день в 1:00 UTC | Деактивирует истёкшие планы питания |
| `update_cached_meal_plans` | Каждый день в 2:00 UTC | Обновляет кэш планов питания |
| `cleanup_unused_cached_plans` | Воскресенье в 3:00 UTC | Очищает неиспользуемые кэшированные планы |

## 🧪 Тестирование

### Ручной запуск задач (для проверки):

```bash
# Запустить деактивацию истёкших планов
celery -A app.celery_app call tasks.deactivate_expired_plans

# Запустить обновление кэша
celery -A app.celery_app call tasks.update_cached_meal_plans

# Запустить очистку
celery -A app.celery_app call tasks.cleanup_unused_cached_plans
```

### Проверка логов:

После ручного запуска проверьте логи worker'а. Успешное выполнение должно выглядеть так:

```
[INFO] 🔄 Starting deactivation of expired meal plans...
[INFO] ✅ Deactivated 3 expired meal plans
[INFO] Task tasks.deactivate_expired_plans succeeded
```

## ⚠️ Важные замечания

1. **Перезапуск обязателен**: Celery worker НЕ подхватывает изменения в коде автоматически
2. **Redis должен быть запущен**: Все задачи используют Redis как брокер
3. **База данных**: Убедитесь что PostgreSQL запущен и доступен
4. **Расписание**: Celery Beat должен быть запущен отдельным процессом для автоматического выполнения задач

## 🎯 Результат

После применения исправлений:

✅ Все задачи корректно зарегистрированы в Celery
✅ Периодические задачи выполняются по расписанию
✅ Нет ошибок "Received unregistered task"
✅ Логи чистые, без KeyError

## 📝 Изменённые файлы

1. `app/celery_app.py` - добавлен импорт `cached_meal_plan_tasks`
2. `app/tasks/cached_meal_plan_tasks.py` - добавлена задача `deactivate_expired_plans_task`
3. `app/tasks/__init__.py` - обновлён список экспортируемых задач

---

**Автор исправления**: Claude (AI Assistant)
**Дата**: 2025-11-02
**Уровень**: Супер-профессионал ✨
