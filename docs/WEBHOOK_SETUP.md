# Webhook Mode - Quick Setup Guide

## 📝 Что такое Webhook Mode?

**Polling (текущий режим):**
- Бот постоянно спрашивает Telegram: "Есть новые сообщения?"
- Задержка: 1-3 секунды
- Нагрузка на CPU: высокая (постоянные запросы)

**Webhook:**
- Telegram сам отправляет обновления на ваш сервер
- Задержка: <100ms
- Нагрузка на CPU: низкая (только при событиях)

## ✅ Требования

1. **Публичный домен** (например, `bot.example.com`)
2. **SSL сертификат** (Let's Encrypt бесплатно)
3. **Статический IP** или динамический DNS
4. **Открытый порт** 443 или 8443

## 🚀 Быстрая настройка

### 1. Получите SSL сертификат

```bash
# Установить certbot
sudo apt-get install certbot

# Получить сертификат
sudo certbot certonly --standalone -d bot.example.com

# Сертификаты будут в:
# /etc/letsencrypt/live/bot.example.com/fullchain.pem
# /etc/letsencrypt/live/bot.example.com/privkey.pem
```

### 2. Обновите конфигурацию

```bash
# .env

USE_WEBHOOK=true
WEBHOOK_URL=https://bot.example.com/webhook
WEBHOOK_SECRET=$(openssl rand -hex 32)  # Сгенерируйте секрет
```

### 3. Обновите `app/bot/main.py`

```python
def main():
    """Главная функция запуска бота"""
    # ... существующий код ...

    if settings.USE_WEBHOOK:
        # Webhook mode
        logger.info("Starting in WEBHOOK mode")
        application.run_webhook(
            listen="0.0.0.0",
            port=8443,
            url_path="webhook",
            webhook_url=f"{settings.WEBHOOK_URL}",
            secret_token=settings.WEBHOOK_SECRET,
            cert="/etc/letsencrypt/live/bot.example.com/fullchain.pem",
            key="/etc/letsencrypt/live/bot.example.com/privkey.pem"
        )
    else:
        # Polling mode (текущий)
        logger.info("Starting in POLLING mode")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
```

### 4. Перезапустите бота

```bash
sudo systemctl restart nutriai-bot
```

## 📊 Результат

| Метрика | Polling | Webhook |
|---------|---------|---------|
| Задержка | 1-3s | <100ms ✅ |
| CPU (idle) | 5% | 0.1% ✅ |
| Пропускная способность | ~10 RPS | ~100 RPS ✅ |

## ⚠️ Примечание

**Webhook требует дополнительной настройки сервера.** Если у вас нет публичного домена или SSL, продолжайте использовать Polling mode - он работает отлично для большинства случаев.

**Когда переходить на Webhook:**
- У вас > 200 активных пользователей в день
- Нужна быстрая реакция (<1 сек)
- Есть выделенный сервер с доменом

Подробная инструкция: см. `SCALING_GUIDE.md` раздел 4.
