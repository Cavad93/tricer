# Миграция на PostgreSQL 12

Этот документ описывает процесс миграции NutriAI бота с SQLite на PostgreSQL 12.

## Что изменилось

### Обновленные файлы

1. **requirements.txt** - Заменен `aiosqlite` на `asyncpg` и добавлен `psycopg2-binary`
2. **app/config.py** - Обновлена DATABASE_URL для PostgreSQL
3. **app/db/session.py** - Добавлены настройки пула соединений для PostgreSQL
4. **.env.example** - Обновлены переменные окружения для PostgreSQL
5. **migrations/*.sql** - Все SQL миграции обновлены для совместимости с PostgreSQL
6. **docker-compose.yml** - Добавлен для запуска PostgreSQL 12 в Docker

### Ключевые изменения в БД

- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `DATETIME` → `TIMESTAMP`
- `TEXT` (для JSON) → `JSONB`
- `BOOLEAN DEFAULT 0/1` → `BOOLEAN DEFAULT FALSE/TRUE`
- Добавлено `IF NOT EXISTS` в ALTER TABLE для безопасности

## Установка и настройка

### Шаг 1: Установка PostgreSQL

#### Вариант A: Использование Docker (рекомендуется)

```bash
# Запуск PostgreSQL 12 в Docker
docker-compose up -d postgres

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f postgres
```

#### Вариант B: Установка нативно

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql-12 postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**MacOS:**
```bash
brew install postgresql@12
brew services start postgresql@12
```

**Windows:**
Скачайте установщик с https://www.postgresql.org/download/windows/

### Шаг 2: Создание базы данных

```bash
# Войдите в PostgreSQL (если не используете Docker)
sudo -u postgres psql

# Создайте пользователя и базу данных
CREATE USER nutriai WITH PASSWORD 'nutriai';
CREATE DATABASE nutriai OWNER nutriai;
GRANT ALL PRIVILEGES ON DATABASE nutriai TO nutriai;
\q
```

Если используете Docker, БД уже создана автоматически.

### Шаг 3: Обновление зависимостей

```bash
# Установите новые зависимости
pip install -r requirements.txt
```

### Шаг 4: Настройка переменных окружения

Обновите файл `.env`:

```bash
# Database (PostgreSQL)
DATABASE_URL=postgresql+asyncpg://nutriai:nutriai@localhost:5432/nutriai

# PostgreSQL Settings (для docker-compose)
POSTGRES_USER=nutriai
POSTGRES_PASSWORD=nutriai
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=nutriai
```

Если используете Docker:
- Замените `localhost` на `postgres` в DATABASE_URL, если приложение тоже в Docker
- Или оставьте `localhost`, если приложение запускается локально

### Шаг 5: Инициализация базы данных

```bash
# Создайте таблицы в PostgreSQL
python init_db.py
```

## Миграция данных из SQLite

Если у вас уже есть данные в SQLite БД, используйте скрипт миграции:

### Подготовка

1. Убедитесь, что PostgreSQL запущен и доступен
2. Убедитесь, что файл `nutriai.db` существует
3. Убедитесь, что таблицы в PostgreSQL созданы (выполнен `init_db.py`)

### Запуск миграции

```bash
python migrate_sqlite_to_postgresql.py
```

Скрипт:
- Прочитает все данные из SQLite
- Конвертирует данные в формат PostgreSQL
- Вставит данные в PostgreSQL
- Обновит sequences для SERIAL полей
- Выведет отчет о миграции

### Проверка миграции

```bash
# Войдите в PostgreSQL
psql -U nutriai -d nutriai -h localhost

# Проверьте количество записей
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM meals;
SELECT COUNT(*) FROM chat_messages;

# Выйдите
\q
```

## Запуск приложения

```bash
# Запустите бота
python -m app.bot.main

# Или запустите API сервер
python -m app.main
```

## Полезные команды PostgreSQL

### Подключение к БД

```bash
# Через psql
psql -U nutriai -d nutriai -h localhost

# Через Docker
docker-compose exec postgres psql -U nutriai -d nutriai
```

### Просмотр структуры

```sql
-- Список всех таблиц
\dt

-- Описание таблицы
\d users
\d meals

-- Список индексов
\di

-- Размер базы данных
SELECT pg_size_pretty(pg_database_size('nutriai'));

-- Размер таблиц
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Резервное копирование

```bash
# Создание бэкапа
pg_dump -U nutriai -h localhost nutriai > backup.sql

# Или через Docker
docker-compose exec postgres pg_dump -U nutriai nutriai > backup.sql

# Восстановление из бэкапа
psql -U nutriai -h localhost nutriai < backup.sql

# Или через Docker
docker-compose exec -T postgres psql -U nutriai nutriai < backup.sql
```

### Очистка БД

```bash
# Удалить все данные из таблицы
TRUNCATE TABLE users CASCADE;

# Удалить и пересоздать БД
DROP DATABASE nutriai;
CREATE DATABASE nutriai OWNER nutriai;
```

## Управление Docker

```bash
# Запуск сервисов
docker-compose up -d

# Остановка сервисов
docker-compose down

# Остановка с удалением данных
docker-compose down -v

# Просмотр логов
docker-compose logs -f postgres

# Рестарт PostgreSQL
docker-compose restart postgres

# Статус сервисов
docker-compose ps
```

## Adminer (Web интерфейс для БД)

Docker Compose также запускает Adminer - веб-интерфейс для управления БД.

Откройте в браузере: http://localhost:8080

Параметры подключения:
- System: PostgreSQL
- Server: postgres (или localhost если не в Docker)
- Username: nutriai
- Password: nutriai
- Database: nutriai

## Производительность PostgreSQL

### Рекомендуемые настройки для production

Отредактируйте `postgresql.conf`:

```conf
# Память
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 4MB

# Параллельные операции
max_worker_processes = 4
max_parallel_workers_per_gather = 2
max_parallel_workers = 4

# Логирование медленных запросов
log_min_duration_statement = 1000  # логировать запросы > 1 секунды

# Автовакуум
autovacuum = on
```

### Мониторинг производительности

```sql
-- Активные подключения
SELECT count(*) FROM pg_stat_activity;

-- Медленные запросы
SELECT pid, now() - query_start as duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC;

-- Статистика по таблицам
SELECT * FROM pg_stat_user_tables;

-- Неиспользуемые индексы
SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0;
```

## Откат на SQLite (если потребуется)

Если необходимо вернуться на SQLite:

1. Восстановите старые файлы из git:
   ```bash
   git checkout HEAD -- requirements.txt app/config.py app/db/session.py
   ```

2. Переустановите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

3. Обновите `.env`:
   ```bash
   DATABASE_URL=sqlite+aiosqlite:///./nutriai.db
   ```

4. Перезапустите приложение

## Troubleshooting

### Ошибка: "password authentication failed"

Проверьте параметры подключения в `.env` и убедитесь, что пользователь создан:

```sql
-- Проверка пользователей
SELECT usename FROM pg_user;

-- Пересоздание пользователя
DROP USER IF EXISTS nutriai;
CREATE USER nutriai WITH PASSWORD 'nutriai';
GRANT ALL PRIVILEGES ON DATABASE nutriai TO nutriai;
```

### Ошибка: "database does not exist"

```bash
# Создайте БД
createdb -U postgres nutriai
# Или
psql -U postgres -c "CREATE DATABASE nutriai;"
```

### Ошибка подключения через Docker

Убедитесь, что:
1. PostgreSQL контейнер запущен: `docker-compose ps`
2. Порт 5432 не занят: `lsof -i :5432`
3. Используете правильный хост в DATABASE_URL

### Проблемы с миграцией данных

1. Проверьте логи: скрипт выводит подробную информацию
2. Убедитесь, что таблицы созданы: `python init_db.py`
3. Проверьте права доступа к файлу `nutriai.db`
4. Попробуйте миграцию отдельных таблиц

## Поддержка

При возникновении проблем:
1. Проверьте логи PostgreSQL: `docker-compose logs postgres`
2. Проверьте логи приложения
3. Убедитесь, что все зависимости установлены
4. Проверьте переменные окружения в `.env`

## Дополнительные ресурсы

- [PostgreSQL 12 Documentation](https://www.postgresql.org/docs/12/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
