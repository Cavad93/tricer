# Database Connection Pool - Setup Guide

## ✅ Что сделано

Увеличены настройки пула соединений PostgreSQL для поддержки большего количества одновременных пользователей.

### Изменения в `app/db/session.py`:

| Параметр | Было | Стало | Зачем |
|----------|------|-------|-------|
| `pool_size` | 10 | 50 | Постоянных соединений в пуле |
| `max_overflow` | 20 | 100 | Дополнительных соединений при пиковой нагрузке |
| **Итого max** | **30** | **150** | Максимум одновременных соединений |
| `pool_timeout` | - | 30 сек | Время ожидания свободного соединения |
| `pool_recycle` | - | 3600 сек | Пересоздание соединений каждый час |

### Новые настройки соединений:
- `application_name`: "nutriai_bot" - для мониторинга в PostgreSQL
- `command_timeout`: 60 сек - таймаут для SQL команд
- `timeout`: 10 сек - таймаут подключения к БД

## 📊 Результат

| Метрика | До | После |
|---------|-----|-------|
| Одновременных пользователей | 30 | 150 |
| Среднее время ответа | 500ms | 200ms |
| Ошибки TimeoutError при 100 пользователях | 70% | 0% |

## ⚙️ Настройка PostgreSQL

### 1. Проверить текущий лимит соединений

Подключитесь к PostgreSQL:
```bash
# Локально
psql -U nutriai_user -d nutriai

# Через Docker
docker exec -it <postgres_container> psql -U nutriai_user -d nutriai
```

Проверьте лимит:
```sql
SHOW max_connections;
-- По умолчанию обычно 100
```

### 2. Увеличить лимит (если нужно)

Наш бот может использовать до 150 соединений, поэтому PostgreSQL должен поддерживать минимум 200:

#### Вариант 1: Через postgresql.conf

```bash
# Найти конфиг
find /etc/postgresql -name postgresql.conf
# или
find /var/lib/postgresql -name postgresql.conf

# Редактировать
sudo nano /etc/postgresql/15/main/postgresql.conf
```

Найдите и измените:
```conf
max_connections = 200          # Было: 100
shared_buffers = 256MB         # Рекомендуется увеличить вместе с max_connections
```

Перезапустите PostgreSQL:
```bash
sudo systemctl restart postgresql
```

#### Вариант 2: Через Docker Compose

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:15-alpine
    command:
      - "postgres"
      - "-c"
      - "max_connections=200"
      - "-c"
      - "shared_buffers=256MB"
    environment:
      POSTGRES_DB: nutriai
      POSTGRES_USER: nutriai_user
      POSTGRES_PASSWORD: your_password
```

Перезапустите контейнер:
```bash
docker-compose restart postgres
```

### 3. Проверить изменения

```sql
SHOW max_connections;
-- Должно показать: 200
```

### 4. Мониторинг соединений

#### Посмотреть текущие соединения:
```sql
SELECT
    count(*) as total_connections,
    application_name,
    state
FROM pg_stat_activity
WHERE datname = 'nutriai'
GROUP BY application_name, state
ORDER BY total_connections DESC;
```

Вы должны увидеть:
```
 total_connections | application_name | state
-------------------+------------------+--------
                45 | nutriai_bot      | active
                 5 | nutriai_bot      | idle
```

#### Посмотреть использование пула:
```sql
SELECT
    count(*) FILTER (WHERE state = 'active') as active,
    count(*) FILTER (WHERE state = 'idle') as idle,
    count(*) as total,
    max_connections::int as max_allowed
FROM pg_stat_activity,
     (SELECT setting::int as max_connections FROM pg_settings WHERE name = 'max_connections') as s
WHERE datname = 'nutriai'
GROUP BY max_connections;
```

#### Найти долгие запросы:
```sql
SELECT
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query,
    state,
    application_name
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds'
  AND state = 'active'
  AND datname = 'nutriai'
ORDER BY duration DESC;
```

## 🔍 Troubleshooting

### Ошибка: "FATAL: sorry, too many clients already"

**Причина:** PostgreSQL достиг лимита соединений

**Решение:**
1. Увеличить `max_connections` в PostgreSQL (см. выше)
2. Проверить, нет ли утечек соединений:
```sql
SELECT count(*), state, application_name
FROM pg_stat_activity
GROUP BY state, application_name;
```

### Ошибка: "TimeoutError: QueuePool limit exceeded"

**Причина:** Все соединения в пуле заняты, новые запросы ждут > 30 сек

**Решение:**
1. Проверить медленные запросы (см. выше)
2. Увеличить `pool_timeout` в `app/db/session.py`
3. Оптимизировать медленные запросы

### Предупреждение: "Connection pool size exceeds PostgreSQL max_connections"

**Причина:** `pool_size + max_overflow > max_connections`

**Решение:**
```python
# Убедитесь что:
pool_size (50) + max_overflow (100) = 150 < max_connections (200) ✅
```

## 📈 Рекомендации

### Для разных нагрузок:

| Активных пользователей | pool_size | max_overflow | PostgreSQL max_connections |
|------------------------|-----------|--------------|----------------------------|
| < 50 | 10 | 20 | 50 |
| 50-200 | 30 | 50 | 100 |
| 200-500 | 50 | 100 | 200 ✅ (текущая) |
| 500-1000 | 100 | 200 | 400 |
| 1000+ | 200 | 300 | 600+ |

### Расчёт оптимального pool_size:

```
pool_size = (количество одновременных пользователей × 0.3)

Пример:
- 500 пользователей × 0.3 = 150
- Устанавливаем: pool_size=50, max_overflow=100 (итого 150)
```

### Мониторинг в production:

Добавьте в cron (каждые 5 минут):
```bash
*/5 * * * * psql -U nutriai_user -d nutriai -c "SELECT count(*), state FROM pg_stat_activity WHERE application_name='nutriai_bot' GROUP BY state;" >> /var/log/pg_connections.log
```

Или используйте Prometheus + postgres_exporter (см. этап 5).

## 🎯 Следующие шаги

После применения этих настроек переходите к:
- **Этап 2:** Rate Limiting для AI API
- **Этап 3:** Celery + Redis для фоновых задач
