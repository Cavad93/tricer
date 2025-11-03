# 📊 Профессиональная система логирования NutriAI

## 🎯 Обзор

Проект использует профессиональную систему логирования с полным разделением по компонентам, ротацией файлов, автоочисткой и структурированным форматом.

### ✅ Реализованные функции

- ✅ **Отдельные файлы** для бота, воркера и планировщика
- ✅ **Ротация логов** по размеру (50MB) и времени (ежедневно)
- ✅ **Автоочистка** старых логов (30 дней)
- ✅ **Разделение по уровням** (all, info, error)
- ✅ **Структурированное логирование** (JSON формат)

---

## 📁 Структура папок

```
logs/
├── bot/                    # Логи Telegram бота
│   ├── all.log            # Все уровни (DEBUG, INFO, WARNING, ERROR, CRITICAL)
│   ├── info.log           # INFO и выше (без DEBUG)
│   ├── error.log          # ⚠️ Только ERROR и CRITICAL
│   └── structured.json    # JSON формат для парсинга
│
├── worker/                 # Логи Celery Worker
│   ├── all.log
│   ├── info.log
│   ├── error.log
│   └── structured.json
│
└── beat/                   # Логи Celery Beat (планировщик)
    ├── all.log
    ├── info.log
    ├── error.log
    └── structured.json
```

---

## 🔧 Конфигурация

### Параметры ротации

| Параметр | Значение | Описание |
|----------|----------|----------|
| **Размер файла** | 50 MB | Автоматическая ротация при достижении размера |
| **Время ротации** | Полночь (00:00) | Ежедневная ротация для info и JSON |
| **Хранение** | 30 дней | Автоматическое удаление старых файлов |
| **Сжатие** | ZIP | Архивирование ротированных файлов |
| **Кодировка** | UTF-8 | Поддержка кириллицы |

### Уровни логирования

| Файл | Уровни | Когда использовать |
|------|--------|-------------------|
| **all.log** | DEBUG, INFO, WARNING, ERROR, CRITICAL | Полная информация для отладки |
| **info.log** | INFO, WARNING, ERROR, CRITICAL | Рабочие логи без DEBUG |
| **error.log** | ERROR, CRITICAL | ⚠️ **Только ошибки** - смотрите в первую очередь! |
| **structured.json** | Все уровни | Автоматический парсинг и анализ |

---

## 🚀 Использование

### 1. В коде бота (уже настроено)

```python
from loguru import logger

# Логгер автоматически настроен в app/bot/main.py
logger.info("Пользователь начал онбординг")
logger.warning("Некорректный формат данных")
logger.error("Ошибка подключения к БД")
```

### 2. В Celery Worker (уже настроено)

```python
from loguru import logger

# Логгер автоматически настроен в app/celery_app.py
logger.info("Задача генерации плана питания запущена")
logger.error("Ошибка вызова AI API")
```

### 3. В Celery Beat (уже настроено)

```python
from loguru import logger

# Логгер автоматически настроен в celery_beat.py
logger.info("Запуск периодической задачи обновления кэша")
```

### 4. Расширенное логирование с контекстом

```python
from loguru import logger

# С дополнительными полями
logger.bind(user_id=123, telegram_id=456789).info("Действие пользователя")

# С exception traceback
try:
    # код
except Exception as e:
    logger.exception("Произошла ошибка")  # Автоматически добавит traceback
```

---

## 🔍 Поиск ошибок

### Быстрый поиск последних ошибок

```bash
# Последние 50 ошибок в боте
tail -n 50 logs/bot/error.log

# Последние 50 ошибок в воркере
tail -n 50 logs/worker/error.log

# Последние 50 ошибок в планировщике
tail -n 50 logs/beat/error.log
```

### Мониторинг ошибок в реальном времени

```bash
# Следить за ошибками бота
tail -f logs/bot/error.log

# Следить за ошибками воркера
tail -f logs/worker/error.log

# Следить за ошибками планировщика
tail -f logs/beat/error.log
```

### Поиск по ключевому слову

```bash
# Найти все логи с ключевым словом "database"
grep -r "database" logs/bot/

# Найти ошибки связанные с конкретным пользователем
grep "user_id.*123" logs/bot/all.log

# Найти ошибки за последний час (примерный поиск по timestamp)
grep "2025-11-03 06:" logs/bot/error.log
```

### Парсинг JSON логов

```bash
# Все ERROR логи из JSON (требует jq)
cat logs/bot/structured.json | jq 'select(.record.level.name == "ERROR")'

# Статистика по уровням
cat logs/bot/structured.json | jq -r '.record.level.name' | sort | uniq -c

# Ошибки конкретного модуля
cat logs/worker/structured.json | jq 'select(.record.module == "meal_plan_service")'
```

---

## 🧹 Обслуживание

### Автоматическая очистка

Система автоматически:
- ✅ Ротирует файлы при достижении 50MB
- ✅ Создает новый файл каждую полночь (для info и JSON)
- ✅ Сжимает старые файлы в ZIP
- ✅ Удаляет файлы старше 30 дней

### Ручная очистка (если нужно)

```bash
# Удалить все логи старше 7 дней
find logs/ -name "*.log*" -mtime +7 -delete

# Удалить все сжатые архивы
find logs/ -name "*.zip" -delete

# Очистить все логи (ОСТОРОЖНО!)
rm -rf logs/*/all.log logs/*/info.log logs/*/error.log logs/*/structured.json
```

### Проверка размера логов

```bash
# Общий размер всех логов
du -sh logs/

# Размер по компонентам
du -sh logs/*

# Самые большие файлы
find logs/ -type f -exec du -h {} + | sort -rh | head -20
```

---

## 📈 Мониторинг производительности

### Анализ частоты ошибок

```bash
# Количество ошибок за сегодня
grep "$(date +%Y-%m-%d)" logs/bot/error.log | wc -l

# Топ-10 самых частых ошибок
grep "ERROR" logs/bot/all.log | cut -d'|' -f4 | sort | uniq -c | sort -rn | head -10
```

### Анализ времени выполнения задач

```bash
# Все задачи воркера с их временем
grep "Task.*succeeded" logs/worker/all.log

# Медленные задачи (>30 секунд)
grep "Task.*succeeded.*runtime" logs/worker/all.log | awk '{if ($NF > 30) print}'
```

---

## 🛠️ Интеграция с внешними системами

### ELK Stack (Elasticsearch, Logstash, Kibana)

```bash
# Отправка JSON логов в Elasticsearch
tail -f logs/bot/structured.json | while read line; do
    curl -XPOST 'localhost:9200/nutriai-logs/_doc' \
         -H 'Content-Type: application/json' \
         -d "$line"
done
```

### Grafana + Loki

```yaml
# promtail-config.yaml
clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: nutriai
    static_configs:
      - targets:
          - localhost
        labels:
          job: nutriai
          __path__: /app/logs/*/*.log
```

### Sentry (для ERROR уровня)

```python
import sentry_sdk
from loguru import logger

# Интеграция с Sentry
sentry_sdk.init(dsn="YOUR_SENTRY_DSN")

# Логи уровня ERROR автоматически отправляются в Sentry
logger.error("Критическая ошибка")  # Попадет в Sentry
```

---

## 🎓 Best Practices

### ✅ Рекомендуется

```python
# Используйте правильные уровни
logger.debug("Отладочная информация: {}", variable)      # Разработка
logger.info("Пользователь {} выполнил действие", user_id) # Информация
logger.warning("Подозрительная активность: {}", data)     # Предупреждение
logger.error("Ошибка обработки: {}", error)               # Ошибка

# Добавляйте контекст
logger.bind(user_id=123, action="meal_plan").info("Действие выполнено")

# Используйте exception для traceback
try:
    risky_operation()
except Exception as e:
    logger.exception("Операция провалена")  # Включает полный traceback
```

### ❌ Избегайте

```python
# НЕ используйте print()
print("Что-то произошло")  # ❌ Не попадет в логи

# НЕ логируйте чувствительные данные
logger.info(f"Пароль: {password}")  # ❌ Утечка данных
logger.info(f"Токен: {api_key}")    # ❌ Утечка данных

# НЕ переполняйте логи в циклах
for item in huge_list:
    logger.debug(f"Processing {item}")  # ❌ Миллионы записей

# Вместо этого используйте агрегацию
logger.info(f"Обработано {len(huge_list)} элементов")  # ✅
```

---

## 📊 Примеры анализа

### Подсчет активности пользователей

```bash
# Уникальные пользователи за сегодня
grep "$(date +%Y-%m-%d)" logs/bot/all.log | grep "user_id" | \
  grep -oP 'user_id.*?(\d+)' | sort -u | wc -l
```

### Анализ производительности AI запросов

```bash
# Среднее время ответа Claude AI
grep "Claude API response" logs/worker/all.log | \
  grep -oP 'duration.*?(\d+\.\d+)' | \
  awk '{sum+=$1; count++} END {print "Avg:", sum/count, "sec"}'
```

### Детекция аномалий

```bash
# Найти задачи, которые провалились более 3 раз
grep "retry" logs/worker/error.log | \
  grep -oP 'task_id.*?([a-f0-9-]+)' | \
  sort | uniq -c | awk '$1 > 3 {print}'
```

---

## 🔐 Безопасность

### Что НЕ логируется (по дизайну)

- ❌ Пароли пользователей
- ❌ API ключи и токены
- ❌ Персональные медицинские данные (152-ФЗ, 323-ФЗ)
- ❌ Номера банковских карт
- ❌ Секретные ключи шифрования

### Что логируется

- ✅ User ID (не Telegram ID для безопасности)
- ✅ Типы действий (без детальных данных)
- ✅ Ошибки выполнения (без чувствительных данных)
- ✅ Метрики производительности
- ✅ Технические события системы

---

## 📞 Troubleshooting

### Логи не создаются

```bash
# Проверьте права на запись
ls -la logs/

# Создайте папки вручную
mkdir -p logs/{bot,worker,beat}
chmod 755 logs/
```

### Логи растут слишком быстро

```bash
# Уменьшите уровень логирования
export LOG_LEVEL=INFO  # Вместо DEBUG

# Или измените в .env
LOG_LEVEL=WARNING
```

### JSON логи не парсятся

```bash
# Проверьте валидность JSON
cat logs/bot/structured.json | jq empty

# Если ошибка, удалите поврежденные строки
grep -v "^$" logs/bot/structured.json > temp.json
mv temp.json logs/bot/structured.json
```

---

## 📚 Дополнительные ресурсы

- [Loguru Documentation](https://loguru.readthedocs.io/)
- [Celery Logging](https://docs.celeryproject.org/en/stable/userguide/tasks.html#logging)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)

---

## 🎉 Готово!

Теперь у вас есть профессиональная система логирования с:
- 📁 Удобной структурой папок
- 🔄 Автоматической ротацией
- 🧹 Автоочисткой
- 🎯 Разделением по уровням
- 📊 Структурированным форматом

**Для поиска ошибок просто открывайте:**
- `logs/bot/error.log` - ошибки бота
- `logs/worker/error.log` - ошибки воркера
- `logs/beat/error.log` - ошибки планировщика

Удачной отладки! 🚀
