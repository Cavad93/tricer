# Celery + Redis для фоновых задач - Setup Guide

## ✅ Что сделано

Вынесены долгие операции (генерация планов питания) в фоновый режим с использованием Celery + Redis.

### Установленные компоненты:

| Компонент | Версия | Назначение |
|-----------|--------|------------|
| celery | 5.3.4 | Distributed task queue |
| redis | 5.0.1 | Message broker + result backend |
| flower | 2.0.1 | Web-интерфейс для мониторинга |

### Архитектура:

```
┌─────────────┐
│ Telegram Bot│ (основной процесс)
└──────┬──────┘
       │ 1. Пользователь: /create_plan
       ↓
┌──────────────┐
│ meal_plan.py │ → Создаёт задачу в очереди (0.1s)
└──────┬───────┘   → Отвечает пользователю сразу
       │
       ↓
┌──────────────┐
│    Redis     │ (очередь задач)
└──────┬───────┘
       │
       ↓
┌──────────────┐
│Celery Worker │ (фоновый процесс)
└──────┬───────┘
       │ 2. Генерация плана (60-120s)
       │ 3. Создание PDF (10s)
       │ 4. Расчёт цен (20s)
       ↓
┌──────────────┐
│Уведомление   │ → Отправка пользователю
└──────────────┘
```

## 📦 Установка

### 1. Установить Redis

#### Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Проверка
redis-cli ping
# Должно вернуть: PONG
```

#### MacOS:
```bash
brew install redis
brew services start redis

# Проверка
redis-cli ping
```

#### Docker (рекомендуется):
```bash
# Запустить Redis через docker-compose
docker-compose up -d redis

# Проверка
docker-compose exec redis redis-cli ping
# Должно вернуть: PONG
```

### 2. Установить Python зависимости

```bash
pip install -r requirements.txt
```

Или вручную:
```bash
pip install celery==5.3.4 redis==5.0.1 flower==2.0.1
```

### 3. Настроить переменные окружения

```bash
# .env

# Redis URL
REDIS_URL=redis://localhost:6379/0

# Для Docker (если используете):
# REDIS_URL=redis://nutriai_redis:6379/0
```

## 🚀 Запуск

### Вариант 1: Вручную (для разработки)

#### Терминал 1 - Telegram Bot:
```bash
python -m app.bot.main
```

#### Терминал 2 - Celery Worker:
```bash
# Базовый запуск
celery -A app.celery_app worker --loglevel=info

# С автоперезагрузкой (для разработки)
celery -A app.celery_app worker --loglevel=info --reload

# С несколькими воркерами (для продакшена)
celery -A app.celery_app worker --loglevel=info --concurrency=4
```

#### Терминал 3 - Flower (мониторинг, опционально):
```bash
celery -A app.celery_app flower --port=5555

# Откройте в браузере: http://localhost:5555
```

### Вариант 2: Docker Compose (для продакшена)

Добавьте в `docker-compose.yml`:
```yaml
services:
  bot:
    build: .
    command: python -m app.bot.main
    depends_on:
      - postgres
      - redis

  celery_worker:
    build: .
    command: celery -A app.celery_app worker --loglevel=info --concurrency=4
    depends_on:
      - postgres
      - redis
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379/0

  flower:
    build: .
    command: celery -A app.celery_app flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis
```

Запуск:
```bash
docker-compose up -d
```

### Вариант 3: Systemd Services (для VPS)

#### /etc/systemd/system/nutriai-bot.service
```ini
[Unit]
Description=NutriAI Telegram Bot
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=nutriai
Group=nutriai
WorkingDirectory=/home/nutriai/tricer
Environment="PATH=/home/nutriai/tricer/venv/bin"
ExecStart=/home/nutriai/tricer/venv/bin/python -m app.bot.main

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### /etc/systemd/system/nutriai-celery.service
```ini
[Unit]
Description=NutriAI Celery Worker
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=nutriai
Group=nutriai
WorkingDirectory=/home/nutriai/tricer
Environment="PATH=/home/nutriai/tricer/venv/bin"
ExecStart=/home/nutriai/tricer/venv/bin/celery -A app.celery_app worker --loglevel=info --concurrency=4

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Установка и запуск:
```bash
sudo systemctl daemon-reload
sudo systemctl enable nutriai-bot nutriai-celery
sudo systemctl start nutriai-bot nutriai-celery

# Проверка
sudo systemctl status nutriai-bot
sudo systemctl status nutriai-celery

# Логи
sudo journalctl -u nutriai-celery -f
```

## 📊 Результат

### До внедрения Celery:

| Метрика | Значение |
|---------|----------|
| Время ответа на /create_plan | 60-120 секунд ⏳ |
| Блокировка бота | Да ❌ |
| Одновременных генераций планов | 1 |
| Пользовательский опыт | Плохо (долгое ожидание) |

### После внедрения Celery:

| Метрика | Значение |
|---------|----------|
| Время ответа на /create_plan | 0.1 секунда ✅ |
| Блокировка бота | Нет ✅ |
| Одновременных генераций планов | 10-50 (зависит от воркеров) ✅ |
| Пользовательский опыт | Отлично (может продолжать работу) ✅ |

## 🔍 Мониторинг

### 1. Flower Web UI

Откройте http://localhost:5555 в браузере

Доступно:
- ✅ Количество запущенных задач
- ✅ История выполнения
- ✅ Графики производительности
- ✅ Список воркеров
- ✅ Retry и failed tasks

### 2. Командная строка

#### Проверить активные задачи:
```bash
celery -A app.celery_app inspect active
```

#### Проверить статус воркеров:
```bash
celery -A app.celery_app inspect stats
```

#### Количество задач в очереди:
```bash
redis-cli llen celery
```

#### Очистить очередь (осторожно!):
```bash
celery -A app.celery_app purge
```

### 3. Логи задач

```bash
# Логи Celery worker
tail -f logs/celery.log

# Или через systemd
sudo journalctl -u nutriai-celery -f --lines=100

# Фильтр по пользователю
tail -f logs/celery.log | grep "user 123456789"
```

## ⚙️ Конфигурация

### Настройка concurrency (количество одновременных задач):

```bash
# 1 задача за раз (медленный сервер)
celery -A app.celery_app worker --concurrency=1

# 4 задачи (средний сервер)
celery -A app.celery_app worker --concurrency=4

# 8 задач (мощный сервер)
celery -A app.celery_app worker --concurrency=8

# Авто (CPU cores * 2)
celery -A app.celery_app worker --autoscale=10,3
```

### Настройка таймаутов:

В `app/celery_app.py`:
```python
celery_app.conf.update(
    task_soft_time_limit=300,    # 5 минут (предупреждение)
    task_time_limit=360,         # 6 минут (принудительная остановка)
)
```

### Приоритизация задач:

```python
# Высокий приоритет (Premium пользователи)
task_chain.apply_async(priority=9)

# Обычный приоритет
task_chain.apply_async(priority=5)

# Низкий приоритет (фоновые задачи)
task_chain.apply_async(priority=1)
```

## 🎯 Примеры использования

### Создание новой задачи:

```python
# app/tasks/example_task.py

from app.celery_app import celery_app
from loguru import logger

@celery_app.task(bind=True, max_retries=3)
def send_email_task(self, user_id: int, subject: str, body: str):
    """
    Отправка email в фоне
    """
    try:
        logger.info(f"Sending email to user {user_id}")
        # ... логика отправки email ...
        return {"status": "sent"}
    except Exception as exc:
        logger.error(f"Error sending email: {exc}")
        raise self.retry(exc=exc, countdown=60)  # Retry через 60 сек
```

Использование:
```python
# В обработчике бота
from app.tasks.example_task import send_email_task

send_email_task.delay(user_id=123, subject="Hello", body="World")
```

### Периодические задачи (cron):

```python
# app/celery_app.py

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'check-expired-plans': {
        'task': 'tasks.check_expired_meal_plans',
        'schedule': crontab(hour=0, minute=0),  # Каждый день в полночь
    },
    'send-daily-reminders': {
        'task': 'tasks.send_daily_reminders',
        'schedule': crontab(hour='*/1'),  # Каждый час
    },
}
```

Запуск beat scheduler:
```bash
# Отдельный процесс для периодических задач
celery -A app.celery_app beat --loglevel=info
```

## ⚠️ Troubleshooting

### Проблема: Задачи не выполняются

**Проверка 1: Redis работает?**
```bash
redis-cli ping
# Должно вернуть: PONG
```

**Проверка 2: Celery worker запущен?**
```bash
celery -A app.celery_app inspect active
# Должно показать список воркеров
```

**Проверка 3: Задачи в очереди?**
```bash
celery -A app.celery_app inspect reserved
```

### Проблема: Worker падает с ошибкой памяти

**Причина:** Утечка памяти или слишком много задач

**Решение:**
```python
# app/celery_app.py
celery_app.conf.update(
    worker_max_tasks_per_child=50,  # Уменьшите с 100 до 50
)
```

Или перезапускайте worker периодически:
```bash
# Cron: каждые 6 часов
0 */6 * * * systemctl restart nutriai-celery
```

### Проблема: Задачи выполняются слишком медленно

**Причина:** Мало воркеров

**Решение:**
```bash
# Увеличьте concurrency
celery -A app.celery_app worker --concurrency=8

# Или запустите несколько воркеров
celery -A app.celery_app worker --concurrency=4 --hostname=worker1@%h &
celery -A app.celery_app worker --concurrency=4 --hostname=worker2@%h &
```

### Проблема: "Connection refused" к Redis

**Причина:** Redis не запущен или неправильный URL

**Решение:**
```bash
# Проверьте Redis
sudo systemctl status redis

# Проверьте URL в .env
echo $REDIS_URL

# Тест подключения
redis-cli -h localhost -p 6379 ping
```

### Проблема: Задачи "stuck" (зависли)

**Просмотр зависших:**
```bash
celery -A app.celery_app inspect active
```

**Отмена задачи:**
```python
from celery.result import AsyncResult

result = AsyncResult('task-id-here')
result.revoke(terminate=True)
```

**Очистка всех задач:**
```bash
celery -A app.celery_app purge  # ⚠️ Удалит ВСЕ задачи!
```

## 📈 Производительность

### Рекомендуемая конфигурация по нагрузке:

| Пользователей/день | Workers | Concurrency | Redis Memory |
|--------------------|---------|-------------|--------------|
| < 100 | 1 | 2 | 256 MB |
| 100-500 | 1 | 4 | 512 MB |
| 500-1000 | 2 | 4 каждый | 1 GB |
| 1000-5000 | 4 | 4 каждый | 2 GB |
| 5000+ | 8+ | 4-8 каждый | 4+ GB |

### Расчёт необходимых ресурсов:

```
CPU = (количество_воркеров × concurrency) + 2 ядра для бота
RAM = (количество_воркеров × 500 MB) + 1 GB для Redis + 1 GB для бота

Пример для 1000 пользователей/день:
- CPU: (2 × 4) + 2 = 10 cores (рекомендуется 12+)
- RAM: (2 × 500) + 1 + 1 = 3 GB (рекомендуется 4+ GB)
```

## 🔐 Безопасность

### Redis authentication (рекомендуется):

```bash
# redis.conf
requirepass your_strong_password_here
```

```bash
# .env
REDIS_URL=redis://:your_strong_password_here@localhost:6379/0
```

### Celery result encryption (опционально):

```python
# app/celery_app.py
celery_app.conf.update(
    result_backend='redis://:password@localhost:6379/0',
    result_serializer='json',
    result_compression='gzip',
)
```

## 🎯 Следующие шаги

После настройки Celery:

1. **Мониторьте Flower** первые несколько дней
2. **Проверьте логи** на ошибки
3. **Оптимизируйте concurrency** под вашу нагрузку
4. Переходите к **Этапу 4: Webhook Mode** для снижения latency

## 💡 Pro Tips

### Graceful shutdown:

```bash
# SIGTERM для graceful shutdown (завершит текущие задачи)
kill -TERM $(pidof celery)

# SIGKILL для немедленной остановки (может потерять данные)
kill -KILL $(pidof celery)
```

### Логирование в файл:

```bash
celery -A app.celery_app worker \
    --loglevel=info \
    --logfile=/var/log/celery/worker.log \
    --pidfile=/var/run/celery/worker.pid
```

### Автоматическое масштабирование:

```bash
# Автоматически увеличивать/уменьшать воркеры
celery -A app.celery_app worker \
    --autoscale=10,3  # max=10, min=3
```

## 📚 Дополнительные ресурсы

- [Celery Documentation](https://docs.celeryq.dev/)
- [Redis Documentation](https://redis.io/documentation)
- [Flower Documentation](https://flower.readthedocs.io/)
- [Best Practices for Celery](https://docs.celeryq.dev/en/stable/userguide/tasks.html#best-practices)
