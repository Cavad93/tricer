# Prometheus + Grafana Monitoring - Complete Implementation Guide

## ✅ Status: FULLY IMPLEMENTED

All monitoring components have been implemented and are ready to use.

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
  → Claude API: 429 errors (rate limit)
  → DB pool: 48/50 connections used
  → Решение найдено за 2 минуты ✅
```

## 📊 Что мониторим?

### Bot Metrics (app/metrics.py):
- ✅ **Counters**: messages_total, errors_total, claude_api_calls_total, user_registrations_total, meal_plans_created_total
- ✅ **Histograms**: command_duration_seconds, claude_api_duration_seconds, meal_plan_generation_duration_seconds, db_query_duration_seconds
- ✅ **Gauges**: active_users, concurrent_requests, db_pool_connections, celery_queue_size, claude_rate_limiter_available

### System Metrics (Node Exporter):
- ✅ CPU usage, RAM usage, Disk usage, Network I/O

### Database Metrics (PostgreSQL Exporter):
- ✅ Connections, queries per second, transaction rate, slow queries

### Redis Metrics (Redis Exporter):
- ✅ Memory usage, keys count, commands per second, connected clients

## 🚀 Quick Start (15 минут)

### 1. Запустите monitoring stack

```bash
# Из корневой директории проекта
docker-compose -f docker-compose.monitoring.yml up -d

# Проверьте статус
docker-compose -f docker-compose.monitoring.yml ps
```

Должны запуститься:
- ✅ Prometheus (http://localhost:9090)
- ✅ Grafana (http://localhost:3000)
- ✅ Node Exporter (http://localhost:9100/metrics)
- ✅ PostgreSQL Exporter (http://localhost:9187/metrics)
- ✅ Redis Exporter (http://localhost:9121/metrics)

### 2. Запустите бот с metrics endpoint

Бот автоматически запустит Prometheus metrics HTTP server на порту 8000.

```bash
# В .env добавьте (опционально):
METRICS_PORT=8000  # По умолчанию 8000
ENVIRONMENT=production  # production/staging/development

# Запустите бота
python -m app.bot.main
```

В логах вы увидите:
```
Prometheus metrics server started on port 8000
Metrics available at: http://0.0.0.0:8000/metrics
```

### 3. Проверьте что metrics собираются

```bash
# Проверьте metrics endpoint бота
curl http://localhost:8000/metrics

# Должны увидеть metrics в формате Prometheus:
# bot_messages_total{command="start",user_type="free"} 42.0
# bot_command_duration_seconds_bucket{command="start",le="0.5"} 35.0
# ...
```

### 4. Откройте Grafana Dashboard

1. Откройте Grafana: http://localhost:3000
2. Войдите:
   - Username: `admin`
   - Password: `admin` (или из `GRAFANA_PASSWORD` в .env)
3. Первый раз попросит сменить пароль - можно skip
4. Откройте: **Dashboards → NutriAI Bot Monitoring Dashboard**

Если dashboard не появился автоматически:
1. Configuration → Data Sources → Verify Prometheus is connected
2. Dashboards → Import → Upload `deployment/grafana/dashboards/nutriai-bot-dashboard.json`

### 5. Проверьте что все работает

В Grafana dashboard вы должны увидеть:
- ✅ Message Rate (messages per second)
- ✅ Concurrent Requests (текущее количество)
- ✅ Active Users (количество активных пользователей)
- ✅ Command Response Time (p50, p95)
- ✅ Claude API Response Time (p50, p95)
- ✅ Database Connection Pool (in_use/available/total)
- ✅ Error Rate (errors per second)
- ✅ Celery Queue Size
- ✅ Statistics (24h): New Users, Meal Plans, Messages, Errors

Если панели пустые - отправьте несколько команд боту (/start, /menu, /help) и обновите dashboard (Ctrl+R).

## 📈 Implemented Metrics Details

### 1. Bot Application Metrics

**Файл:** `app/metrics.py` (380+ строк)

#### Counters (всегда растут):
```python
# Примеры использования в коде:
from app.metrics import track_command, track_user_registration, track_meal_plan_created

@track_command('start')  # Автоматически отслеживает duration, errors, concurrent requests
async def start_command(update, context):
    # ... your code ...
    pass

# При создании пользователя:
track_user_registration()

# При создании плана питания:
track_meal_plan_created('week')  # day/week/month
```

#### Histograms (распределение значений):
```python
# Автоматически собираются через decorators:
@track_command('meal_plan')  # Собирает command_duration_seconds
@track_api_call('analyze_food_photo')  # Собирает claude_api_duration_seconds

# Queries в Prometheus:
# p95 response time за последние 5 минут:
histogram_quantile(0.95, rate(bot_command_duration_seconds_bucket[5m]))
```

#### Gauges (могут расти и падать):
```python
# Автоматически обновляются через MetricsUpdater каждые 15 секунд:
- bot_active_users
- bot_concurrent_requests
- bot_db_pool_connections{state="in_use|available|total"}
- celery_queue_size{queue_name="default"}
- claude_rate_limiter_available
```

### 2. Интегрированные обработчики

Metrics decorators добавлены в:
- ✅ `app/bot/main.py`: help_command, menu_command, profile_command, wellness_insights_command
- ✅ `app/bot/handlers/start.py`: start_command + track_user_registration()
- ✅ `app/services/claude_ai.py`: ALL 8 API methods с @track_api_call():
  - analyze_food_photo
  - chat
  - analyze_text
  - extract_medical_analysis
  - detect_food_inquiry
  - generate_meal_recommendation
  - check_meal_safety
  - generate_harm_minimization_advice

### 3. MetricsUpdater Background Task

Автоматически запускается в `app/bot/main.py` при старте бота:

```python
# В post_init():
metrics_updater = MetricsUpdater(
    db_pool=engine.pool,
    celery_app=celery_app,
    update_interval=15  # секунд
)
await metrics_updater.start()
```

Обновляет каждые 15 секунд:
- Database pool metrics
- Celery queue metrics

## 📊 Grafana Dashboard

**Файл:** `deployment/grafana/dashboards/nutriai-bot-dashboard.json`

### Панели (13 шт):

| # | Название | Метрика | Описание |
|---|----------|---------|----------|
| 1 | Message Rate | `rate(bot_messages_total[5m])` | Сообщений в секунду |
| 2 | Concurrent Requests | `bot_concurrent_requests` | Одновременных запросов |
| 3 | Active Users | `bot_active_users` | Активных пользователей |
| 4 | Command Response Time | `histogram_quantile(0.95, rate(bot_command_duration_seconds_bucket[5m]))` | p50, p95 latency |
| 5 | Claude API Response Time | `histogram_quantile(0.95, rate(claude_api_duration_seconds_bucket[5m]))` | p50, p95 latency |
| 6 | Claude API Call Rate | `rate(claude_api_calls_total{status="success|failure"}[5m])` | Success/Failure |
| 7 | Database Connection Pool | `bot_db_pool_connections{state="in_use|available|total"}` | Состояние пула |
| 8 | Error Rate | `rate(bot_errors_total[5m])` | Ошибок в секунду |
| 9 | Celery Queue Size | `celery_queue_size` | Задач в очереди |
| 10 | New Users (24h) | `sum(increase(bot_user_registrations_total[24h]))` | Новых пользователей |
| 11 | Meal Plans (24h) | `sum(increase(bot_meal_plans_created_total[24h]))` | Созданных планов |
| 12 | Total Messages (24h) | `sum(increase(bot_messages_total[24h]))` | Всего сообщений |
| 13 | Total Errors (24h) | `sum(increase(bot_errors_total[24h]))` | Всего ошибок |

### Кастомизация Dashboard

1. В Grafana откройте dashboard → Settings (⚙️)
2. Variables → Add variable для фильтрации:
   - `$environment` - фильтр по окружению
   - `$command` - фильтр по командам
   - `$user_type` - free/premium
3. Добавьте новые панели:
   - Dashboards → Add panel → Выберите метрику
   - Настройте visualization (Graph, Gauge, Stat, etc.)
   - Save dashboard

## 🔧 Configuration Files

### Prometheus Configuration
**Файл:** `deployment/prometheus/prometheus.yml`

```yaml
scrape_configs:
  - job_name: 'nutriai-bot'
    static_configs:
      - targets: ['nutriai-bot:8000']  # Bot metrics
    scrape_interval: 10s

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']  # System metrics

  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']  # DB metrics

  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['redis-exporter:9121']  # Redis metrics
```

### Grafana Datasource
**Файл:** `deployment/grafana/datasources/prometheus.yml`

```yaml
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

## 🎯 Useful Prometheus Queries

### Bot Performance

```promql
# Средний response time за последний час
avg(rate(bot_command_duration_seconds_sum[1h]) / rate(bot_command_duration_seconds_count[1h])) by (command)

# Процент успешных Claude API calls
sum(rate(claude_api_calls_total{status="success"}[5m])) / sum(rate(claude_api_calls_total[5m])) * 100

# Топ-5 самых используемых команд
topk(5, sum by (command) (rate(bot_messages_total[1h])))

# Error rate по типу
sum by (error_type) (rate(bot_errors_total[5m]))
```

### System Health

```promql
# CPU usage %
100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)

# RAM usage %
(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100

# Disk free %
(node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"}) * 100

# Database connections utilization
bot_db_pool_connections{state="in_use"} / bot_db_pool_connections{state="total"} * 100
```

### Celery

```promql
# Задач в очереди
celery_queue_size{queue_name="default"}

# Скорость создания задач
rate(celery_tasks_total{status="pending"}[5m])

# Скорость выполнения задач
rate(celery_tasks_total{status="success"}[5m])
```

## ⚠️ Alerts Setup (опционально)

### Создайте alerts в Prometheus:

**Файл:** `deployment/prometheus/alerts/bot-alerts.yml`

```yaml
groups:
  - name: bot_alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(bot_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      # Slow response time
      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, rate(bot_command_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow bot response time"
          description: "p95 latency is {{ $value }} seconds"

      # Database pool exhausted
      - alert: DatabasePoolExhausted
        expr: (bot_db_pool_connections{state="available"} / bot_db_pool_connections{state="total"}) < 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool almost exhausted"
          description: "Only {{ $value }}% connections available"

      # High Celery queue size
      - alert: HighCeleryQueueSize
        expr: celery_queue_size > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Celery queue size is high"
          description: "{{ $value }} tasks waiting in queue"
```

### Настройте Alertmanager (опционально):

```yaml
# alertmanager.yml
route:
  receiver: 'telegram'
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h

receivers:
  - name: 'telegram'
    telegram_configs:
      - bot_token: 'YOUR_BOT_TOKEN'
        chat_id: YOUR_CHAT_ID
        message: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ .Annotations.description }}\n{{ end }}'
```

## 📊 Результат

**С мониторингом вы будете знать:**
- ✅ Сколько пользователей онлайн (реал-тайм)
- ✅ Какие команды используются чаще всего
- ✅ Где и когда возникают ошибки
- ✅ Performance bottlenecks (медленные команды/API calls)
- ✅ Состояние ресурсов (CPU, RAM, DB connections, Celery queue)
- ✅ Когда нужно масштабироваться

### Примеры выводов из dashboard:

**Сценарий 1: Медленная генерация планов**
```
Dashboard показывает:
→ meal_plan command: p95 = 65s (слишком медленно)
→ claude_api_duration (generate_meal_plan): p95 = 55s (большая часть времени)
→ Решение: Оптимизировать промпт или увеличить Celery workers
```

**Сценарий 2: База данных перегружена**
```
Dashboard показывает:
→ db_pool_connections: in_use=48, available=2 (почти исчерпаны)
→ db_query_duration: p95 = 2.5s (медленные запросы)
→ Решение: Увеличить pool_size в config или добавить индексы
```

**Сценарий 3: Ошибки Claude API**
```
Dashboard показывает:
→ claude_api_calls (failure): 30% последние 5 минут
→ Error type: RateLimitError
→ Решение: Уменьшить CLAUDE_RATE_LIMIT или апгрейд API tier
```

## 🔍 Advanced Topics

### 1. Production Setup (SystemD)

Если запускаете бота через systemd (не Docker), убедитесь что:

```ini
# /etc/systemd/system/nutriai-bot.service
[Service]
# Metrics port должен быть доступен для Prometheus
Environment="METRICS_PORT=8000"
```

И настройте Prometheus scrape с правильным target:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'nutriai-bot'
    static_configs:
      - targets: ['localhost:8000']  # Или IP сервера
```

### 2. Multiple Bot Instances

Если запускаете несколько инстансов бота:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'nutriai-bot'
    static_configs:
      - targets:
        - 'bot1:8000'
        - 'bot2:8001'
        - 'bot3:8002'
        labels:
          instance: 'bot-{{ $index }}'
```

В Grafana queries используйте `sum()` для агрегации:

```promql
# Total messages across all instances
sum(rate(bot_messages_total[5m]))
```

### 3. Long-term Storage

По умолчанию Prometheus хранит данные 30 дней. Для долгосрочного хранения:

**Вариант 1: Увеличить retention**
```yaml
# docker-compose.monitoring.yml
command:
  - '--storage.tsdb.retention.time=90d'  # 90 дней
```

**Вариант 2: Remote Write в VictoriaMetrics/Thanos**
```yaml
# prometheus.yml
remote_write:
  - url: http://victoriametrics:8428/api/v1/write
```

### 4. Custom Metrics

Добавьте свои метрики в `app/metrics.py`:

```python
# Пример: Отслеживание времени генерации PDF
from prometheus_client import Histogram

pdf_generation_duration = Histogram(
    'pdf_generation_duration_seconds',
    'PDF generation duration',
    ['plan_type']  # Label: day/week/month
)

# Использование:
with pdf_generation_duration.labels(plan_type='week').time():
    generate_pdf(...)  # Your code
```

## 💡 Best Practices

1. **Start Simple**: Сначала смотрите только system metrics (CPU/RAM), затем добавляйте bot metrics
2. **Set Baselines**: Запишите нормальные значения метрик, чтобы знать когда что-то не так
3. **Alert Fatigue**: Не создавайте слишком много alerts, только для критичных проблем
4. **Regular Reviews**: Проверяйте dashboard раз в день, чтобы заметить тренды
5. **Document Changes**: Когда меняете конфигурацию - документируйте почему и что изменилось

## 🚀 Next Steps

После настройки мониторинга:

1. **Webhook Mode** (см. `WEBHOOK_SETUP.md`):
   - Снизит CPU usage с 5% до 0.1%
   - Уменьшит latency с 1-3s до <100ms

2. **Multiple Bot Instances** (см. `SCALING_GUIDE.md` раздел 6):
   - Запустите 2-3 инстанса для high availability
   - Load balancing через nginx

3. **Performance Optimization**:
   - Найдите bottlenecks в dashboard
   - Оптимизируйте медленные команды/queries

## 📚 Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Cheat Sheet](https://promlabs.com/promql-cheat-sheet/)
- [Grafana Dashboards Community](https://grafana.com/grafana/dashboards/)

## ⚠️ Troubleshooting

### Проблема: Metrics endpoint не отвечает

```bash
# Проверьте что бот запущен
ps aux | grep "python -m app.bot.main"

# Проверьте что порт открыт
curl http://localhost:8000/metrics

# Проверьте логи бота
tail -f logs/bot.log | grep metrics
```

### Проблема: Dashboard пустой

```bash
# Проверьте что Prometheus scrapes bot metrics
curl http://localhost:9090/api/v1/targets

# Должен быть target 'nutriai-bot' со статусом UP

# Проверьте что metrics есть в Prometheus
curl 'http://localhost:9090/api/v1/query?query=bot_messages_total'
```

### Проблема: Grafana не подключается к Prometheus

```bash
# Проверьте что Prometheus доступен
docker exec nutriai_grafana ping prometheus -c 3

# Проверьте datasource в Grafana
# Settings → Data Sources → Prometheus → Test
```

## 🎉 Done!

Теперь у вас полноценный production-grade мониторинг!

**Не забудьте:**
- [ ] Сменить пароль Grafana в production
- [ ] Настроить alerts для критичных метрик
- [ ] Добавить мониторинг в ваш runbook
- [ ] Регулярно проверять dashboard (раз в день)

**Следующий этап:** Переходите к `WEBHOOK_SETUP.md` для снижения latency и CPU usage.
