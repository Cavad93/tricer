# Инструкция по внедрению системы кэширования планов питания

## Предварительные требования

- PostgreSQL 12 запущен и доступен
- Redis запущен и доступен
- Python окружение активировано
- Все зависимости установлены

## Шаг 1: Применение миграции БД

### Вариант 1: Через Python скрипт (РЕКОМЕНДУЕТСЯ)

```bash
cd /home/user/tricer

# Применить миграцию
python apply_cached_plans_migration.py
```

**Ожидаемый вывод:**
```
================================================================================
Применение миграции системы кэширования планов питания
================================================================================
Читаю миграцию из /home/user/tricer/migrations/cached_meal_plans_migration.sql
Применяю миграцию...
Выполняю команду 1/15
✅ Команда 1 выполнена успешно
...
✅ Миграция успешно применена!
Проверяю созданные таблицы...
✅ Таблицы созданы: user_categories, cached_meal_plans
  - user_categories: 12 столбцов
  - cached_meal_plans: 13 столбцов
================================================================================
✅ Миграция успешно применена и проверена!
================================================================================
```

### Вариант 2: Вручную через psql (если есть доступ)

```bash
# Найти путь к psql
find / -name psql 2>/dev/null | grep bin

# Применить миграцию (замените путь на свой)
/usr/lib/postgresql/12/bin/psql \
  -h localhost \
  -p 5432 \
  -U nutriai \
  -d nutriai \
  -f /home/user/tricer/migrations/cached_meal_plans_migration.sql
```

### Проверка миграции

```bash
# Проверить что таблицы созданы
python -c "
import asyncio
from app.db.session import async_engine
from sqlalchemy import text

async def check():
    async with async_engine.begin() as conn:
        result = await conn.execute(text('''
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('user_categories', 'cached_meal_plans')
        '''))
        tables = [row[0] for row in result]
        print(f'Созданные таблицы: {tables}')

asyncio.run(check())
"
```

**Ожидаемый вывод:**
```
Созданные таблицы: ['user_categories', 'cached_meal_plans']
```

## Шаг 2: Настройка Celery Beat

### 2.1. Проверка конфигурации

Конфигурация уже добавлена в `app/celery_app.py`:

```python
celery_app.conf.beat_schedule = {
    'update-cached-meal-plans': {
        'task': 'tasks.update_cached_meal_plans',
        'schedule': crontab(hour=2, minute=0),  # Каждый день в 2:00 UTC
    },
    'cleanup-unused-cached-plans': {
        'task': 'tasks.cleanup_unused_cached_plans',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),  # Воскресенье 3:00 UTC
    },
    'deactivate-expired-meal-plans': {
        'task': 'tasks.deactivate_expired_plans',
        'schedule': crontab(hour=1, minute=0),  # Каждый день в 1:00 UTC
    },
}
```

### 2.2. Запуск Celery Worker

В **первом терминале** запустите worker:

```bash
cd /home/user/tricer

# Запуск worker
celery -A app.celery_app worker --loglevel=info

# ИЛИ через Python скрипт
python celery_worker.py
```

**Ожидаемый вывод:**
```
[2025-11-01 10:00:00] [INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-11-01 10:00:00] [INFO/MainProcess] mingle: searching for neighbors
[2025-11-01 10:00:01] [INFO/MainProcess] mingle: all alone
[2025-11-01 10:00:01] [INFO/MainProcess] celery@hostname ready.
```

### 2.3. Запуск Celery Beat

Во **втором терминале** запустите beat:

```bash
cd /home/user/tricer

# Запуск beat
celery -A app.celery_app beat --loglevel=info

# ИЛИ через Python скрипт
python celery_beat.py
```

**Ожидаемый вывод:**
```
================================================================================
Запуск Celery Beat (планировщик периодических задач)
================================================================================
Расписание задач:
  - update-cached-meal-plans: <crontab: 0 2 * * * (m/h/d/dM/MY)>
  - cleanup-unused-cached-plans: <crontab: 0 3 * * 0 (m/h/d/dM/MY)>
  - deactivate-expired-meal-plans: <crontab: 0 1 * * * (m/h/d/dM/MY)>
================================================================================
[2025-11-01 10:00:00] [INFO/Beat] Scheduler: Sending due task update-cached-meal-plans
```

## Шаг 3: Production запуск (через systemd или supervisor)

### Вариант 1: Systemd

Создайте файлы службы:

**`/etc/systemd/system/nutriai-celery-worker.service`:**
```ini
[Unit]
Description=Nutriai Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/user/tricer
Environment="PATH=/home/user/tricer/venv/bin"
ExecStart=/home/user/tricer/venv/bin/celery -A app.celery_app worker --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/nutriai-celery-beat.service`:**
```ini
[Unit]
Description=Nutriai Celery Beat
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=your_user
WorkingDirectory=/home/user/tricer
Environment="PATH=/home/user/tricer/venv/bin"
ExecStart=/home/user/tricer/venv/bin/celery -A app.celery_app beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск служб:

```bash
# Перезагрузить конфигурацию systemd
sudo systemctl daemon-reload

# Запустить службы
sudo systemctl start nutriai-celery-worker
sudo systemctl start nutriai-celery-beat

# Включить автозапуск
sudo systemctl enable nutriai-celery-worker
sudo systemctl enable nutriai-celery-beat

# Проверить статус
sudo systemctl status nutriai-celery-worker
sudo systemctl status nutriai-celery-beat

# Просмотр логов
sudo journalctl -u nutriai-celery-worker -f
sudo journalctl -u nutriai-celery-beat -f
```

### Вариант 2: Supervisor

Создайте файл `/etc/supervisor/conf.d/nutriai-celery.conf`:

```ini
[program:nutriai-celery-worker]
command=/home/user/tricer/venv/bin/celery -A app.celery_app worker --loglevel=info
directory=/home/user/tricer
user=your_user
numprocs=1
autostart=true
autorestart=true
stopwaitsecs=600
stdout_logfile=/var/log/nutriai/celery-worker.log
stderr_logfile=/var/log/nutriai/celery-worker-error.log

[program:nutriai-celery-beat]
command=/home/user/tricer/venv/bin/celery -A app.celery_app beat --loglevel=info
directory=/home/user/tricer
user=your_user
numprocs=1
autostart=true
autorestart=true
stopwaitsecs=60
stdout_logfile=/var/log/nutriai/celery-beat.log
stderr_logfile=/var/log/nutriai/celery-beat-error.log
```

Запуск:

```bash
# Создать директорию для логов
sudo mkdir -p /var/log/nutriai
sudo chown your_user:your_user /var/log/nutriai

# Перечитать конфигурацию
sudo supervisorctl reread
sudo supervisorctl update

# Запустить процессы
sudo supervisorctl start nutriai-celery-worker
sudo supervisorctl start nutriai-celery-beat

# Проверить статус
sudo supervisorctl status
```

## Шаг 4: Тестирование системы

### 4.1. Ручной запуск задачи обновления кэша

```bash
cd /home/user/tricer

# Запустить задачу вручную
python -c "
from app.tasks.cached_meal_plan_tasks import update_cached_meal_plans_task
result = update_cached_meal_plans_task.delay()
print(f'Задача запущена: {result.id}')
print('Ожидание результата...')
print(result.get(timeout=300))
"
```

### 4.2. Проверка создания категорий

```bash
python -c "
import asyncio
from app.db.session import async_session_maker
from sqlalchemy import select, func
from app.models.cached_meal_plan import UserCategory, CachedMealPlan

async def check_stats():
    async with async_session_maker() as session:
        # Количество категорий
        result = await session.execute(select(func.count(UserCategory.id)))
        categories_count = result.scalar()
        print(f'Категорий пользователей: {categories_count}')

        # Количество кэшированных планов
        result = await session.execute(select(func.count(CachedMealPlan.id)))
        plans_count = result.scalar()
        print(f'Кэшированных планов: {plans_count}')

        # Статистика по типам
        result = await session.execute(
            select(
                CachedMealPlan.period_type,
                CachedMealPlan.status,
                func.count(CachedMealPlan.id)
            ).group_by(CachedMealPlan.period_type, CachedMealPlan.status)
        )

        print('\nСтатистика по планам:')
        for period, status, count in result:
            print(f'  {period} ({status}): {count}')

asyncio.run(check_stats())
"
```

### 4.3. Тестирование генерации плана с кэшем

```bash
python -c "
import asyncio
from app.db.session import async_session_maker
from app.services.meal_plan_service import MealPlanService
from app.models.meal_plan import PlanPeriod

async def test_cached_plan():
    async with async_session_maker() as session:
        # Замените на реальный telegram_id из БД
        user_id = 123456789

        print('Генерация плана питания (с использованием кэша)...')

        meal_plan = await MealPlanService.generate_meal_plan(
            session,
            user_id=user_id,
            period_type=PlanPeriod.WEEK
        )

        print(f'План создан: ID={meal_plan.id}')
        print(f'Период: {meal_plan.period_type.value}')
        print(f'Даты: {meal_plan.start_date} - {meal_plan.end_date}')

asyncio.run(test_cached_plan())
"
```

## Шаг 5: Мониторинг

### 5.1. Проверка задач в очереди (Redis)

```bash
# Через redis-cli
redis-cli

# В консоли redis
KEYS celery*
LLEN celery
```

### 5.2. Мониторинг через Flower (опционально)

```bash
# Установить Flower
pip install flower

# Запустить Flower
celery -A app.celery_app flower --port=5555

# Открыть в браузере
# http://localhost:5555
```

### 5.3. Проверка логов

```bash
# Логи Celery Worker
tail -f /var/log/nutriai/celery-worker.log

# Логи Celery Beat
tail -f /var/log/nutriai/celery-beat.log

# ИЛИ через journalctl (если systemd)
sudo journalctl -u nutriai-celery-worker -f
sudo journalctl -u nutriai-celery-beat -f
```

## Расписание задач

| Задача | Расписание | Описание |
|--------|-----------|----------|
| `update-cached-meal-plans` | Каждый день в 2:00 UTC | Обновляет кэш планов (помечает старые как outdated, генерирует новые) |
| `cleanup-unused-cached-plans` | Воскресенье в 3:00 UTC | Удаляет неиспользуемые планы (>30 дней без использования) |
| `deactivate-expired-meal-plans` | Каждый день в 1:00 UTC | Деактивирует истекшие планы пользователей |

## Полезные команды

```bash
# Остановить все задачи Celery
celery -A app.celery_app control shutdown

# Очистить очередь задач
celery -A app.celery_app purge

# Посмотреть активные задачи
celery -A app.celery_app inspect active

# Посмотреть зарегистрированные задачи
celery -A app.celery_app inspect registered

# Посмотреть расписание
celery -A app.celery_app inspect scheduled
```

## Устранение неполадок

### Проблема: Задачи не запускаются по расписанию

**Решение:**
1. Проверьте что Celery Beat запущен: `ps aux | grep "celery.*beat"`
2. Проверьте логи Beat: `sudo journalctl -u nutriai-celery-beat -n 50`
3. Убедитесь что часовой пояс настроен правильно (UTC)

### Проблема: Ошибка "Table 'user_categories' doesn't exist"

**Решение:**
1. Применить миграцию: `python apply_cached_plans_migration.py`
2. Проверить что таблицы созданы в правильной БД

### Проблема: Worker падает с ошибкой памяти

**Решение:**
1. Уменьшить `worker_max_tasks_per_child` в `celery_app.py`
2. Увеличить доступную память для процесса
3. Проверить утечки памяти в коде задач

## Дополнительная информация

- Подробная документация: `CACHED_MEAL_PLANS_README.md`
- Код моделей: `app/models/cached_meal_plan.py`
- Код сервиса: `app/services/cached_meal_plan_service.py`
- Код задач: `app/tasks/cached_meal_plan_tasks.py`
