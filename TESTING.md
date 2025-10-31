# 🧪 Руководство по тестированию NutriAI Bot

Комплексная система тестирования для проверки всех компонентов бота.

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Типы тестов](#типы-тестов)
3. [Запуск тестов](#запуск-тестов)
4. [Структура тестов](#структура-тестов)
5. [Интерпретация результатов](#интерпретация-результатов)
6. [Решение проблем](#решение-проблем)

---

## 🚀 Быстрый старт

### Запуск всех тестов

```batch
run-tests.bat
```

Этот скрипт запустит **комплексное тестирование** всех 12 компонентов системы.

### Что проверяется

✅ Environment файл (.env)
✅ Загрузка конфигурации
✅ PostgreSQL подключение
✅ Redis подключение
✅ Telegram Bot API
✅ Claude AI API
✅ Celery Worker
✅ Prometheus метрики
✅ Модели базы данных
✅ Rate Limiter
✅ Калькулятор питания
✅ Bot Handlers

---

## 📚 Типы тестов

### 1. Комплексные системные тесты

**Файл:** `test_bot.py`
**Запуск:** `python test_bot.py` или `run-tests.bat`

Проверяет работу всей системы:
- Подключения к внешним сервисам
- API интеграции
- Конфигурация системы
- Готовность к production

**Результат:**
- ✅ Зеленый: Все работает
- ⚠️ Желтый: Некритичные проблемы
- ❌ Красный: Критические ошибки

### 2. Unit-тесты

**Директория:** `tests/`
**Запуск:** `pytest tests/`

Изолированные тесты отдельных функций:

#### a) Тесты калькулятора питания
**Файл:** `tests/test_nutrition_calculator.py`

```bash
pytest tests/test_nutrition_calculator.py -v
```

Проверяет:
- Расчет BMR (базовый метаболизм)
- Расчет BMI (индекс массы тела)
- Расчет макронутриентов (белки, жиры, углеводы)
- Различные цели (похудение, набор массы, поддержание)
- Граничные значения и валидацию

**Примеры:**
```python
# Тест расчета BMR для мужчины
def test_calculate_bmr_male()

# Тест расчета BMI
def test_calculate_bmi_normal()

# Тест макросов для похудения
def test_calculate_macros_lose_weight()
```

#### b) Тесты моделей данных
**Файл:** `tests/test_models.py`

```bash
pytest tests/test_models.py -v
```

Проверяет:
- Создание пользователей
- Создание приемов пищи
- Создание продуктов питания
- Связи между моделями
- Валидацию данных

#### c) Интеграционные тесты
**Файл:** `tests/test_integration.py`

```bash
pytest tests/test_integration.py -v
```

Проверяет:
- Работу с базой данных
- Интеграцию сервисов
- Celery задачи
- Внешние API
- End-to-end сценарии

---

## ▶️ Запуск тестов

### Вариант 1: Быстрый запуск (Windows)

```batch
# Все тесты
run-tests.bat

# Только unit-тесты
pytest tests/ -v

# Конкретный файл
pytest tests/test_nutrition_calculator.py -v

# Конкретный тест
pytest tests/test_nutrition_calculator.py::TestNutritionCalculator::test_calculate_bmr_male -v
```

### Вариант 2: С фильтрацией

```bash
# Только быстрые тесты (исключить медленные)
pytest tests/ -m "not slow"

# Только unit-тесты
pytest tests/ -m unit

# Только интеграционные тесты
pytest tests/ -m integration

# Тесты, требующие БД
pytest tests/ -m db

# Тесты, требующие API
pytest tests/ -m api
```

### Вариант 3: С детальным выводом

```bash
# Максимально подробный вывод
pytest tests/ -vv

# Показать print() в тестах
pytest tests/ -s

# Остановиться на первой ошибке
pytest tests/ -x

# Показать локальные переменные при ошибке
pytest tests/ -l
```

### Вариант 4: С покрытием кода (если установлен pytest-cov)

```bash
# Установка pytest-cov
pip install pytest-cov

# Запуск с покрытием
pytest tests/ --cov=app --cov-report=html

# Результат будет в htmlcov/index.html
```

---

## 📁 Структура тестов

```
tricer/
├── test_bot.py                          # Комплексное системное тестирование
├── run-tests.bat                        # Скрипт запуска тестов
├── pytest.ini                           # Конфигурация pytest
├── TESTING.md                           # Эта документация
│
├── tests/                               # Директория с unit-тестами
│   ├── __init__.py
│   ├── test_nutrition_calculator.py    # Тесты калькулятора (13 тестов)
│   ├── test_models.py                  # Тесты моделей (15+ тестов)
│   └── test_integration.py             # Интеграционные тесты (10+ тестов)
│
├── app/
│   ├── bot/
│   │   └── handlers/                   # Handlers бота
│   ├── services/
│   │   └── nutrition_calc.py           # Калькулятор (покрыт тестами)
│   ├── models/                         # Модели БД (покрыты тестами)
│   └── metrics.py                      # Метрики (покрыты системными тестами)
```

---

## 📊 Интерпретация результатов

### Комплексное тестирование (test_bot.py)

#### ✅ Все тесты пройдены (Exit code: 0)

```
============================================
 Результаты тестирования
============================================
Всего тестов: 12
✓ Успешно: 12
✗ Провалено: 0

Процент успеха: 100.0%

✓ Все тесты пройдены! Бот готов к запуску!
```

**Действие:** Можно запускать бота в production.

#### ⚠️ Некритичные ошибки (Exit code: 1)

```
Всего тестов: 12
✓ Успешно: 10
✗ Провалено: 2

✗ 7. Celery Worker
  Проблема: No active workers found
  Решение: Запустите Celery worker

✗ 8. Prometheus Metrics
  Проблема: Metrics server not running
  Решение: Запустите бота
```

**Действие:** Исправить указанные проблемы, но критические компоненты работают.

#### ❌ Критические ошибки (Exit code: 2)

```
Всего тестов: 12
✓ Успешно: 6
✗ Провалено: 6

✗ 3. PostgreSQL Connection
  Проблема: Connection refused
  Решение: Запустите PostgreSQL

✗ 5. Telegram Bot API
  Проблема: Invalid token
  Решение: Проверьте TELEGRAM_BOT_TOKEN
```

**Действие:** Бот НЕ готов к запуску. Исправить все критические ошибки.

### Unit-тесты (pytest)

```bash
$ pytest tests/ -v

tests/test_nutrition_calculator.py::test_calculate_bmr_male PASSED      [ 10%]
tests/test_nutrition_calculator.py::test_calculate_bmi_normal PASSED    [ 20%]
tests/test_models.py::test_user_creation PASSED                         [ 30%]
...

========================= 38 passed in 2.34s =========================
```

**Метрики:**
- `PASSED` - тест успешен ✅
- `FAILED` - тест провален ❌
- `SKIPPED` - тест пропущен ⏭️
- `ERROR` - ошибка выполнения 💥

---

## 🛠️ Решение проблем

### Проблема 1: PostgreSQL не подключается

**Симптом:**
```
✗ 3. PostgreSQL Connection
  Проблема: could not connect to server
```

**Решение:**
1. Проверьте что PostgreSQL запущен:
   ```bash
   sc query postgresql*
   ```

2. Запустите PostgreSQL:
   ```bash
   net start postgresql-x64-15  # Имя может отличаться
   ```

3. Проверьте DATABASE_URL в .env:
   ```
   DATABASE_URL=postgresql+asyncpg://nutriai:nutriai@localhost:5432/nutriai
   ```

### Проблема 2: Redis не подключается

**Симптом:**
```
✗ 4. Redis Connection
  Проблема: Connection refused
```

**Решение:**
1. Проверьте Redis:
   ```bash
   redis-cli ping
   ```

2. Запустите Redis:
   ```bash
   net start Redis
   # или
   redis-server
   ```

3. Проверьте REDIS_URL в .env:
   ```
   REDIS_URL=redis://localhost:6379/0
   ```

### Проблема 3: Telegram Bot API ошибка

**Симптом:**
```
✗ 5. Telegram Bot API
  Проблема: Unauthorized (401)
```

**Решение:**
1. Проверьте токен:
   ```bash
   check-token.bat
   ```

2. Получите новый токен у @BotFather:
   - Откройте Telegram
   - Найдите @BotFather
   - Отправьте `/mybots`
   - Выберите бота
   - Нажмите "API Token"

3. Обновите .env:
   ```
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### Проблема 4: Claude API ошибка

**Симптом:**
```
✗ 6. Claude AI API
  Проблема: Access denied (403)
```

**Решение (если сервер в России):**

1. **Вариант A: Cloudflare Worker**
   - Следуйте инструкции в `CLOUDFLARE_WORKER_SETUP.md`
   - Добавьте в .env:
     ```
     CLOUDFLARE_WORKER_URL=https://your-worker.workers.dev
     ```

2. **Вариант B: WARP Proxy**
   - Установите Cloudflare WARP
   - Добавьте в .env:
     ```
     WARP_PROXY_URL=socks5://127.0.0.1:40000
     ```

**Если сервер НЕ в России:**
- Просто используйте валидный ANTHROPIC_API_KEY

### Проблема 5: Celery Worker не найден

**Симптом:**
```
✗ 7. Celery Worker
  Проблема: No active workers found
```

**Решение:**
1. Запустите Celery worker:
   ```bash
   celery -A app.celery_app worker --loglevel=info --pool=solo --concurrency=1
   ```

2. Или используйте start.bat (автоматически запускает worker)

### Проблема 6: Метрики не доступны

**Симптом:**
```
✗ 8. Prometheus Metrics
  Проблема: Connection refused
```

**Решение:**
1. Метрики доступны только когда бот запущен
2. Запустите бота:
   ```bash
   python -m app.bot.main
   ```
3. Откройте http://localhost:8000/metrics

### Проблема 7: Pytest не найден

**Симптом:**
```
'pytest' is not recognized as an internal or external command
```

**Решение:**
```bash
pip install pytest pytest-asyncio
```

### Проблема 8: Import errors в тестах

**Симптом:**
```
ImportError: cannot import name 'NutritionCalculator'
```

**Решение:**
1. Убедитесь что находитесь в корневой директории проекта
2. Установите проект в dev режиме:
   ```bash
   pip install -e .
   ```

---

## 🎯 Рекомендации

### Перед запуском бота

1. **Обязательно** запустите комплексное тестирование:
   ```bash
   run-tests.bat
   ```

2. Убедитесь что **все критические тесты** пройдены:
   - PostgreSQL Connection ✅
   - Redis Connection ✅
   - Telegram Bot API ✅
   - Claude AI API ✅

3. Некритичные тесты (Celery, Metrics) могут провалиться - это нормально если бот еще не запущен.

### Во время разработки

1. Запускайте unit-тесты после изменения кода:
   ```bash
   pytest tests/test_nutrition_calculator.py -v
   ```

2. Проверяйте coverage:
   ```bash
   pytest tests/ --cov=app --cov-report=term-missing
   ```

3. Используйте pytest markers для быстрого тестирования:
   ```bash
   pytest tests/ -m "not slow"  # Только быстрые тесты
   ```

### В production

1. **Перед деплоем** всегда запускайте полное тестирование:
   ```bash
   python test_bot.py
   ```

2. Настройте автоматический запуск тестов в CI/CD:
   ```yaml
   # .github/workflows/test.yml
   - name: Run tests
     run: python test_bot.py
   ```

3. Мониторьте метрики через dashboard.html или Grafana

---

## 📞 Поддержка

Если тесты показывают ошибки:

1. Проверьте раздел [Решение проблем](#решение-проблем)
2. Запустите диагностические скрипты:
   - `check-token.bat` - проверка токена
   - `test-telegram.bat` - тест Telegram API
   - `start-debug.bat` - запуск с DEBUG логами
   - `diagnose.bat` - полная диагностика
3. Изучите логи в консоли

---

## 📈 Статистика тестов

**Текущее покрытие:**
- ✅ Nutrition Calculator: 13 unit-тестов
- ✅ Database Models: 15 unit-тестов
- ✅ Integration Tests: 10 интеграционных тестов
- ✅ System Tests: 12 системных тестов

**Всего:** 50+ тестов

**Покрываемые компоненты:**
- Расчет питания (BMR, BMI, макросы)
- Модели базы данных (User, Meal, FoodItem)
- Подключения к сервисам
- API интеграции
- End-to-end сценарии

---

## 🔄 Непрерывная интеграция

Для автоматического тестирования при каждом commit:

### GitHub Actions

Создайте `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: nutriai
          POSTGRES_PASSWORD: nutriai
          POSTGRES_DB: nutriai
        ports:
          - 5432:5432

      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run system tests
        run: python test_bot.py

      - name: Run unit tests
        run: pytest tests/ -v --cov=app
```

---

**Версия документации:** 1.0
**Последнее обновление:** 2024
**Автор:** NutriAI Development Team
