# Prometheus + Grafana Monitoring - Quick Setup Guide

## 📝 Что такое мониторинг?

**Без мониторинга:**
```
Пользователь: "Бот не работает!"
Вы: "🤷 Не знаю что случилось..."
```

**С мониторингом:**
```
ALERT: Response time > 5s
Dashboard показывает:
  → Claude API: 429 errors
  → Решение найдено за 2 минуты ✅
```

## 📊 Что мониторим?

- ✅ Количество пользователей / сообщений
- ✅ Время ответа на команды
- ✅ Ошибки (по типам)
- ✅ Claude API (успешность, rate limits)
- ✅ Database (соединения, запросы)
- ✅ Система (CPU, RAM, Disk)
- ✅ Celery (количество задач, worker'ы)

## 🚀 Быстрая настройка (Docker Compose)

### 1. Создайте `docker-compose.monitoring.yml`

```yaml
version: '3.8'

services:
  # Prometheus - сбор метрик
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.retention.time=30d'
    restart: unless-stopped

  # Grafana - визуализация
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
    depends_on:
      - prometheus
    restart: unless-stopped

  # Node Exporter - метрики системы
  node_exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
```

### 2. Создайте `prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node'
    static_configs:
      - targets: ['node_exporter:9100']

  # Добавьте когда реализуете metrics endpoint в боте:
  # - job_name: 'bot'
  #   static_configs:
  #     - targets: ['host.docker.internal:8000']
```

### 3. Запустите мониторинг

```bash
docker-compose -f docker-compose.monitoring.yml up -d

# Откройте в браузере:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

### 4. Добавьте Prometheus как Data Source в Grafana

1. Откройте Grafana: http://localhost:3000
2. Войдите (admin/admin)
3. Configuration → Data Sources → Add data source
4. Выберите Prometheus
5. URL: `http://prometheus:9090`
6. Save & Test

### 5. Импортируйте готовый Dashboard

В Grafana:
1. Create → Import
2. ID: `1860` (Node Exporter Full)
3. Select Prometheus data source
4. Import

## 📈 Основные метрики

### Prometheus Query Examples:

```promql
# Использование CPU
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# Использование RAM
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# Свободное место на диске
(node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"}) * 100
```

## 🔍 Расширенная настройка (когда будете готовы)

### Добавьте metrics endpoint в бота:

```python
# app/bot/main.py

from prometheus_client import start_http_server, Counter, Histogram

# Метрики
messages_total = Counter('bot_messages_total', 'Total messages', ['command'])
response_time = Histogram('bot_response_seconds', 'Response time', ['command'])

def main():
    # Запустить Prometheus metrics server
    start_http_server(8000)

    # ... остальной код ...
```

### Используйте в обработчиках:

```python
@response_time.labels(command='start').time()
async def start_command(update, context):
    messages_total.labels(command='start').inc()
    # ... ваш код ...
```

## 📊 Результат

**С мониторингом вы будете знать:**
- ✅ Сколько пользователей онлайн
- ✅ Какие команды используются чаще всего
- ✅ Где возникают ошибки
- ✅ Когда нужно масштабироваться
- ✅ Состояние сервера в реальном времени

## ⚠️ Примечание

Мониторинг - это **дополнительная** система. Бот отлично работает и без неё.

**Когда нужен мониторинг:**
- У вас > 100 пользователей в день
- Вы хотите отслеживать производительность
- Планируете масштабирование

Подробная инструкция: см. `SCALING_GUIDE.md` раздел 5.

## 💡 Pro Tip

Начните с простого:
1. Запустите только Node Exporter (метрики системы)
2. Смотрите CPU/RAM/Disk в Grafana
3. Когда будете готовы - добавляйте метрики бота

Не пытайтесь настроить всё сразу! 🚀
