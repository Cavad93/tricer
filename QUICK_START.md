# Быстрый старт: Система кэширования планов питания

## Ваши данные подключения:
```
POSTGRES_USER=nutriai
POSTGRES_PASSWORD=nutriai
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=nutriai
```

## Шаг 1: Применить миграцию БД (5 минут)

```bash
cd /home/user/tricer

# Применить миграцию через Python
python apply_cached_plans_migration.py
```

**Ожидаемый результат:**
```
✅ Миграция успешно применена!
✅ Таблицы созданы: user_categories, cached_meal_plans
```

Если возникла ошибка - проверьте:
1. PostgreSQL запущен: `ps aux | grep postgres`
2. Доступен по localhost:5432
3. База данных `nutriai` существует

---

## Шаг 2: Запустить Celery Worker и Beat (Development)

### Терминал 1 - Celery Worker:
```bash
cd /home/user/tricer

# Активировать виртуальное окружение (если есть)
# source venv/bin/activate

# Запустить worker
celery -A app.celery_app worker --loglevel=info
```

### Терминал 2 - Celery Beat:
```bash
cd /home/user/tricer

# Активировать виртуальное окружение (если есть)
# source venv/bin/activate

# Запустить beat (планировщик)
python celery_beat.py
```

**Ожидаемый результат в Терминале 2:**
```
Расписание задач:
  - update-cached-meal-plans: <crontab: 0 2 * * * (m/h/d/dM/MY)>
  - cleanup-unused-cached-plans: <crontab: 0 3 * * 0 (m/h/d/dM/MY)>
  - deactivate-expired-meal-plans: <crontab: 0 1 * * * (m/h/d/dM/MY)>
```

---

## Шаг 3: Протестировать (опционально)

### Тест 1: Проверить созданные таблицы
```bash
python -c "
import asyncio
from app.db.session import async_engine
from sqlalchemy import text

async def check():
    async with async_engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT table_name,
                   (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as columns
            FROM information_schema.tables t
            WHERE table_schema = 'public'
            AND table_name IN ('user_categories', 'cached_meal_plans')
        '''))
        for table, cols in result:
            print(f'✅ {table}: {cols} столбцов')

asyncio.run(check())
"
```

### Тест 2: Запустить задачу обновления кэша вручную
```bash
python -c "
from app.tasks.cached_meal_plan_tasks import update_cached_meal_plans_task
print('Запускаю задачу обновления кэша...')
result = update_cached_meal_plans_task.delay()
print(f'Задача запущена с ID: {result.id}')
print('Проверьте логи Celery Worker для деталей')
"
```

### Тест 3: Проверить статистику кэша
```bash
python -c "
import asyncio
from app.db.session import async_session_maker
from sqlalchemy import select, func
from app.models.cached_meal_plan import UserCategory, CachedMealPlan

async def check_stats():
    async with async_session_maker() as session:
        result = await session.execute(select(func.count(UserCategory.id)))
        categories = result.scalar()

        result = await session.execute(select(func.count(CachedMealPlan.id)))
        plans = result.scalar()

        print(f'📊 Категорий пользователей: {categories}')
        print(f'📊 Кэшированных планов: {plans}')

asyncio.run(check_stats())
"
```

---

## Как это работает:

### 1. Обычный пользователь (БЕЗ предпочтений)
```
Пользователь запрашивает план → Бот определяет категорию →
Ищет в кэше → Находит готовый план → Возвращает БЕЗ вызова AI ✅
```
**Экономия: 100% токенов**

### 2. Пользователь с предпочтениями (любимые блюда, особые пожелания)
```
Пользователь запрашивает план → Есть предпочтения →
Вызывает AI → Генерирует персональный план → НЕ сохраняет в кэш
```
**Экономия: 0% (но план персонализирован)**

### 3. Пользователь нажимает "Хочу изменить"
```
Пользователь недоволен планом → Нажимает "Хочу изменить" →
force_ai=True → Вызывает AI → Генерирует новый план
```
**Экономия: 0% (персонализация)**

---

## Расписание автообновления кэша:

| Время (UTC) | Задача | Что делает |
|-------------|--------|------------|
| 01:00 каждый день | Деактивация истекших планов | Помечает старые планы пользователей как неактивные |
| 02:00 каждый день | Обновление кэша | Создает новые варианты планов для категорий |
| 03:00 воскресенье | Очистка кэша | Удаляет неиспользуемые планы (>30 дней) |

**Примечание:** UTC = Московское время - 3 часа
- 01:00 UTC = 04:00 МСК
- 02:00 UTC = 05:00 МСК
- 03:00 UTC = 06:00 МСК

---

## Что дальше?

### Development:
- Держите 2 терминала открытыми (Worker + Beat)
- Проверяйте логи при тестировании
- Система будет автоматически обновлять кэш по расписанию

### Production:
- Настройте systemd/supervisor (см. `SETUP_INSTRUCTIONS.md`)
- Настройте мониторинг (Flower, логи)
- Настройте автозапуск при перезагрузке сервера

---

## Полезные команды:

```bash
# Остановить Worker (Ctrl+C в терминале)
# Остановить Beat (Ctrl+C в терминале)

# Очистить очередь задач (если что-то зависло)
celery -A app.celery_app purge

# Посмотреть активные задачи
celery -A app.celery_app inspect active

# Посмотреть зарегистрированные задачи
celery -A app.celery_app inspect registered

# Перезапустить всё (если изменили код)
# Ctrl+C в обоих терминалах, потом запустить заново
```

---

## Нужна помощь?

1. **Подробная инструкция:** `SETUP_INSTRUCTIONS.md`
2. **Документация системы:** `CACHED_MEAL_PLANS_README.md`
3. **Логи Celery:** смотрите в терминалах Worker и Beat
4. **Проблемы с миграцией:** проверьте подключение к PostgreSQL

---

## Коммиты:

- `630d0e7` - Реализация системы кэширования
- `91ebd90` - Скрипты и инструкции

Ветка: `claude/fix-russian-error-011CUhRX6AHeueUvrNUCuVxZ`
