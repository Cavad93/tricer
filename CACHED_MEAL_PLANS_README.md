# Система кэширования планов питания

## Описание

Система предназначена для **экономии токенов AI** при генерации планов питания. Вместо того чтобы каждый раз обращаться к AI для генерации плана, система использует заранее сгенерированные шаблоны для пользователей с одинаковыми параметрами.

## Архитектура

### 1. Категоризация пользователей

Пользователи группируются в категории по следующим параметрам:
- Целевые калории (округленные до 100)
- Целевые белки (округленные до 10г)
- Целевые жиры (округленные до 10г)
- Целевые углеводы (округленные до 10г)
- Тип диеты (omnivore/vegetarian/vegan/pescatarian)
- Бюджетная категория (economy/normal/premium)
- Аллергии (сортированный список)

Из этих параметров генерируется SHA256 хэш для быстрого поиска категории.

### 2. Кэширование планов

Для каждой категории хранится до 20 вариантов планов питания на каждый период (день/неделя/месяц).

При выборе плана используется **умный алгоритм**:
1. Планы сортируются по `feedback_ratio` (отношение положительных отзывов)
2. Выбирается случайный план из топ-50% для разнообразия

### 3. Логика использования

**Кэш используется когда:**
- Нет персональных предпочтений (favorite_foods, special_requests и т.д.)
- Нет изменений старого плана (old_plan_id)
- Нет особого медицинского контекста
- Не установлен флаг `force_ai`

**AI вызывается когда:**
- Есть персональные предпочтения
- Пользователь нажал "Хочу изменить" (`force_ai=True`)
- В кэше нет подходящих планов для категории

## Использование

### Генерация плана (с кэшем)

```python
from app.services.meal_plan_service import MealPlanService
from app.models.meal_plan import PlanPeriod

# По умолчанию использует кэш
meal_plan = await MealPlanService.generate_meal_plan(
    session,
    user_id=123,
    period_type=PlanPeriod.WEEK
)
```

### Принудительная генерация через AI

```python
# Для кнопки "Хочу изменить"
meal_plan = await MealPlanService.generate_meal_plan(
    session,
    user_id=123,
    period_type=PlanPeriod.WEEK,
    force_ai=True  # Игнорировать кэш
)
```

### Статистика категории

```python
from app.services.cached_meal_plan_service import CachedMealPlanService

stats = await CachedMealPlanService.get_category_stats(session, category_id=1)
# {
#     "category_id": 1,
#     "users_count": 42,
#     "target_calories": 2000,
#     "diet_type": "omnivore",
#     "budget_category": "normal",
#     "plans_by_type": {"day": 20, "week": 18, "month": 15},
#     "total_plans": 53
# }
```

## Celery задачи

### Обновление кэша (каждые 24 часа)

```python
# В celerybeat_schedule
from app.tasks.cached_meal_plan_tasks import update_cached_meal_plans_task

schedule = {
    'update-cached-meal-plans': {
        'task': 'tasks.update_cached_meal_plans',
        'schedule': crontab(hour=2, minute=0),  # Каждый день в 2:00
    },
}
```

Задача:
1. Помечает старые планы (>7 дней) как `outdated`
2. Находит категории с <20 планами
3. Генерирует новые планы через AI (макс. 50 за раз)

### Очистка неиспользуемых планов

```python
from app.tasks.cached_meal_plan_tasks import cleanup_unused_cached_plans_task

# Запускать раз в неделю
schedule = {
    'cleanup-cached-plans': {
        'task': 'tasks.cleanup_unused_cached_plans',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),  # Воскресенье 3:00
    },
}
```

Критерии удаления:
- План не использовался 30+ дней
- План в статусе `outdated` более 14 дней
- Категория имеет 0 пользователей

## База данных

### Миграция

```bash
# Применить миграцию
psql -U your_user -d your_database -f migrations/cached_meal_plans_migration.sql
```

### Таблицы

**user_categories**
- Хранит уникальные категории пользователей
- Индексируется по `params_hash` для быстрого поиска
- Отслеживает количество пользователей в категории

**cached_meal_plans**
- Хранит готовые планы питания в JSON формате
- Индексируется по `(category_id, period_type, status)`
- Отслеживает статистику использования и обратную связь

## Экономия токенов

### Примерная оценка:

- **Один план питания**: ~8000-16000 токенов
- **20 категорий** × **3 периода** × **20 планов** = **1200 планов** в кэше
- При **1000 пользователей/день** и **80% hit rate кэша**:
  - **Без кэша**: 1000 × 12000 токенов = 12 000 000 токенов/день
  - **С кэшем**: 200 × 12000 токенов = 2 400 000 токенов/день
  - **Экономия**: ~80% токенов (9 600 000 токенов/день)

## Мониторинг

### Полезные запросы

```sql
-- Топ-10 категорий по количеству пользователей
SELECT
    id,
    target_calories,
    diet_type,
    budget_category,
    users_count,
    (SELECT COUNT(*) FROM cached_meal_plans WHERE category_id = uc.id AND status = 'active') as plans_count
FROM user_categories uc
ORDER BY users_count DESC
LIMIT 10;

-- Статистика по планам
SELECT
    period_type,
    status,
    COUNT(*) as count,
    AVG(usage_count) as avg_usage,
    AVG(positive_feedback_count::float / NULLIF(positive_feedback_count + negative_feedback_count, 0)) as avg_feedback_ratio
FROM cached_meal_plans
GROUP BY period_type, status;

-- Категории нуждающиеся в планах
SELECT
    uc.id,
    uc.users_count,
    COUNT(CASE WHEN cm.period_type = 'day' THEN 1 END) as day_plans,
    COUNT(CASE WHEN cm.period_type = 'week' THEN 1 END) as week_plans,
    COUNT(CASE WHEN cm.period_type = 'month' THEN 1 END) as month_plans
FROM user_categories uc
LEFT JOIN cached_meal_plans cm ON cm.category_id = uc.id AND cm.status = 'active'
GROUP BY uc.id, uc.users_count
HAVING
    COUNT(CASE WHEN cm.period_type = 'day' THEN 1 END) < 20 OR
    COUNT(CASE WHEN cm.period_type = 'week' THEN 1 END) < 20 OR
    COUNT(CASE WHEN cm.period_type = 'month' THEN 1 END) < 20
ORDER BY uc.users_count DESC;
```

## Обратная связь

Система автоматически отслеживает обратную связь пользователей:

- **Положительная** ("Всё отлично!"): `positive_feedback_count++`
- **Отрицательная** ("Хочу изменить"): `negative_feedback_count++`

Планы с низким `feedback_ratio` автоматически реже выбираются из кэша.

## Безопасность

⚠️ **Важно**:
- Аллергии ВСЕГДА учитываются при категоризации
- Персональные предпочтения НЕ кэшируются
- Медицинские ограничения НЕ кэшируются
- Кэшируются только "базовые" планы без персонализации
