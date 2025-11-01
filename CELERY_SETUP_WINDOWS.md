# Настройка Celery Worker для Windows

## Проблема
План питания не генерируется, потому что не запущен Celery worker для обработки фоновых задач.

## Решение

Для работы генерации планов питания нужно запустить 3 процесса одновременно:
1. **Redis** - брокер сообщений
2. **Celery Worker** - обработчик задач
3. **Telegram Bot** - сам бот

---

## Шаг 1: Установка Redis для Windows

### Вариант 1: Использовать Memurai (рекомендуется для Windows)
Memurai - это порт Redis для Windows, полностью совместимый с Redis.

1. Скачайте Memurai Developer Edition (бесплатная):
   https://www.memurai.com/get-memurai

2. Установите Memurai (стандартная установка)

3. После установки Memurai автоматически запустится как службу Windows

4. Проверьте, что Memurai запущен:
   ```cmd
   memurai-cli ping
   ```
   Должно вывести: `PONG`

### Вариант 2: Redis через Docker (если есть Docker Desktop)
```cmd
docker run -d -p 6379:6379 --name redis redis:alpine
```

### Вариант 3: WSL2 + Redis (если есть WSL)
```bash
sudo apt update
sudo apt install redis-server
sudo service redis-server start
```

---

## Шаг 2: Проверка подключения к Redis

В PowerShell запустите:
```powershell
python -c "import redis; r = redis.from_url('redis://localhost:6379/0'); print(r.ping())"
```

Должно вывести: `True`

Если выдает ошибку:
```powershell
pip install redis
```

---

## Шаг 3: Запуск Celery Worker

Откройте **НОВОЕ** окно PowerShell в папке проекта:

```powershell
cd C:\path\to\tricer
python celery_worker.py
```

**ИЛИ** с помощью Celery CLI:
```powershell
celery -A app.celery_app worker --loglevel=info --pool=solo
```

**ВАЖНО:** Флаг `--pool=solo` нужен для Windows, так как Windows не поддерживает prefork.

Вы должны увидеть примерно такой вывод:
```
 -------------- celery@DESKTOP-XXX v5.x.x
---- **** -----
--- * ***  * -- Windows-10-10.0.xxxxx
-- * - **** ---
- ** ---------- [config]
- ** ---------- .> app:         nutriai:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     redis://localhost:6379/0
- *** --- * --- .> concurrency: 8 (solo)
-- ******* ---- .> task events: OFF
--- ***** -----
 -------------- [queues]
                .> celery           exchange=celery(direct) key=celery

[tasks]
  . tasks.generate_meal_plan
  . tasks.notify_user_plan_ready

[2025-11-01 20:00:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-11-01 20:00:00,000: INFO/MainProcess] mingle: searching for neighbors
[2025-11-01 20:00:00,000: INFO/MainProcess] mingle: all alone
[2025-11-01 20:00:00,000: INFO/MainProcess] celery@DESKTOP-XXX ready.
```

---

## Шаг 4: Запуск всех сервисов

Теперь у вас должно быть открыто **3 окна PowerShell**:

### Окно 1: Redis (Memurai)
Если установили Memurai - он уже работает как служба, окно не нужно.

Если Docker:
```powershell
docker start redis
```

### Окно 2: Celery Worker
```powershell
cd C:\path\to\tricer
celery -A app.celery_app worker --loglevel=info --pool=solo
```

### Окно 3: Telegram Bot
```powershell
cd C:\path\to\tricer
python main.py
```

---

## Проверка работы

1. Запустите бота
2. Создайте план питания через меню "Рацион"
3. Ответьте на все вопросы
4. В окне Celery Worker должны появиться логи:
   ```
   [Celery] Starting meal plan generation for user 921045582, period=week
   [Celery] User found: ...
   [Celery] Generating meal plan via AI...
   [Celery] Meal plan generated: id=123
   [Celery] Creating shopping list...
   [Celery] Generating PDFs...
   [Celery] Task completed successfully
   ```
5. Бот отправит вам PDF файлы с планом питания

---

## Устранение проблем

### Ошибка: "Can't connect to Redis"
- Проверьте, что Redis/Memurai запущен:
  ```powershell
  memurai-cli ping
  ```
- Проверьте порт 6379:
  ```powershell
  netstat -an | findstr "6379"
  ```

### Ошибка: "Pool type 'prefork' is not supported"
- Используйте флаг `--pool=solo`:
  ```powershell
  celery -A app.celery_app worker --loglevel=info --pool=solo
  ```

### Worker запускается, но задачи не выполняются
- Проверьте, что worker видит задачи в выводе `[tasks]`
- Убедитесь, что REDIS_URL одинаковый в .env и config.py
- Перезапустите worker после изменения кода

### Ошибки в логах worker при генерации
- Проверьте подключение к PostgreSQL
- Проверьте ANTHROPIC_API_KEY в .env
- Убедитесь, что все миграции выполнены

---

## Автозапуск (опционально)

Для автоматического запуска всех сервисов при старте системы:

### Windows Task Scheduler для Celery Worker
1. Откройте Task Scheduler
2. Create Task
3. Triggers: At startup
4. Actions:
   - Program: `C:\path\to\python.exe`
   - Arguments: `celery_worker.py`
   - Start in: `C:\path\to\tricer`

### Memurai запускается автоматически как служба Windows

---

## Альтернативное решение: Отключить Celery

Если не хотите настраивать Celery, можно сделать синхронную генерацию (план будет генерироваться сразу, бот будет "подвисать" на 1-2 минуты).

Напишите мне, если нужен этот вариант.
