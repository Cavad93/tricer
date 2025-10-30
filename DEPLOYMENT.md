# 🚀 Инструкция по развертыванию NutriAI бота

## Выбор сервера

### ✅ Иностранный VDS (США, Европа, Азия) - РЕКОМЕНДУЕТСЯ

**Преимущества:**
- Не нужны VPN/прокси для обхода геоблокировки
- Стабильное подключение к Claude API
- Простая настройка

**Где получить:**
- Oracle Cloud Always Free (бесплатно навсегда)
- AWS Free Tier (12 месяцев бесплатно)
- Google Cloud Free Tier ($300 на 90 дней)
- Vultr, DigitalOcean, Linode (от $5/месяц)

### ⚠️ VDS в России

**Требуется:**
- Cloudflare Worker ИЛИ
- VPN (WARP, ProtonVPN и т.д.)

**См. инструкции:**
- `CLOUDFLARE_WORKER_SETUP.md` - для Cloudflare Worker
- Документация в этом файле - для WARP

---

# 📋 Развертывание на Linux VDS (Ubuntu/Debian)

## Требования

- Ubuntu 20.04+ или Debian 11+
- Минимум 1 GB RAM
- 10 GB свободного места
- Root или sudo доступ

---

## Шаг 1: Подключение к серверу

```bash
ssh root@your-server-ip
# Или
ssh username@your-server-ip
```

---

## Шаг 2: Обновление системы

```bash
sudo apt update && sudo apt upgrade -y
```

---

## Шаг 3: Установка необходимого ПО

### Python 3.11+

```bash
# Установка Python 3.11
sudo apt install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev python3-pip -y

# Проверка
python3.11 --version
```

### PostgreSQL 12+

```bash
# Установка PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Запуск
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Проверка
sudo systemctl status postgresql
```

### Git

```bash
sudo apt install git -y
```

---

## Шаг 4: Создание базы данных

```bash
# Переключитесь на пользователя postgres
sudo -u postgres psql

# В консоли PostgreSQL выполните:
```

```sql
CREATE DATABASE nutriai;
CREATE USER nutriai WITH PASSWORD 'nutriai_secure_password_123';
GRANT ALL PRIVILEGES ON DATABASE nutriai TO nutriai;

-- Для PostgreSQL 15+
GRANT ALL ON SCHEMA public TO nutriai;

\q
```

**ВАЖНО:** Замените `nutriai_secure_password_123` на надежный пароль!

---

## Шаг 5: Клонирование репозитория

```bash
# Перейдите в домашнюю папку
cd ~

# Клонируйте репозиторий
git clone https://github.com/Cavad93/tricer.git
cd tricer

# Переключитесь на нужную ветку (если требуется)
git checkout claude/migrate-bot-postgresql-011CUd51gLv17LD4j4snhS1m
```

---

## Шаг 6: Создание виртуального окружения

```bash
# Создайте виртуальное окружение
python3.11 -m venv venv

# Активируйте
source venv/bin/activate

# Обновите pip
pip install --upgrade pip
```

---

## Шаг 7: Установка зависимостей

```bash
pip install -r requirements.txt
```

Ожидайте 3-5 минут.

---

## Шаг 8: Настройка .env файла

```bash
# Создайте .env из примера
cp .env.example .env

# Отредактируйте
nano .env
```

**Минимальная конфигурация для иностранного VDS:**

```env
# Application Settings
APP_NAME=NutriAI
APP_ENV=production
DEBUG=False

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Anthropic Claude API
ANTHROPIC_API_KEY=your_claude_api_key
CLAUDE_MODEL=claude-sonnet-4-20250514

# ОБХОД ГЕОБЛОКИРОВКИ - НЕ НУЖЕН для иностранного VDS!
# Оставьте закомментированными:
# CLOUDFLARE_WORKER_URL=
# WARP_PROXY_URL=

# Database
DATABASE_URL=postgresql+asyncpg://nutriai:nutriai_secure_password_123@localhost:5432/nutriai
POSTGRES_USER=nutriai
POSTGRES_PASSWORD=nutriai_secure_password_123
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=nutriai

# Security
SECRET_KEY=generate_random_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Server
API_HOST=0.0.0.0
API_PORT=8000

# Rate Limiting
FREE_PHOTO_LIMIT_PER_DAY=5
FREE_CHAT_LIMIT_PER_DAY=10

# Logging
LOG_LEVEL=INFO
```

**Сохраните:** Ctrl+O → Enter → Ctrl+X

**Генерация SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Шаг 9: Инициализация базы данных

```bash
python init_db.py
```

Должно показать: `✓ Database initialized successfully!`

---

## Шаг 10: Тестовый запуск

```bash
python -m app.bot.main
```

**Проверьте логи:**
- ✅ `INFO | __main__:post_init - Database initialized`
- ✅ `INFO | __main__:main - Bot started successfully!`
- ✅ **НЕТ** строк про Cloudflare Worker или WARP (для иностранного VDS)

**Протестируйте бота:**
1. Отправьте `/start` в Telegram
2. Загрузите фото еды

Если работает - отлично! Ctrl+C для остановки.

---

## Шаг 11: Настройка systemd для автозапуска

### Создайте systemd service

```bash
sudo nano /etc/systemd/system/nutriai-bot.service
```

**Вставьте:**

```ini
[Unit]
Description=NutriAI Telegram Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/tricer
Environment="PATH=/root/tricer/venv/bin"
ExecStart=/root/tricer/venv/bin/python -m app.bot.main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**ВАЖНО:** Замените `/root/tricer` на ваш путь, если отличается!

**Сохраните:** Ctrl+O → Enter → Ctrl+X

### Активируйте сервис

```bash
# Перезагрузите конфигурацию systemd
sudo systemctl daemon-reload

# Включите автозапуск
sudo systemctl enable nutriai-bot

# Запустите
sudo systemctl start nutriai-bot

# Проверьте статус
sudo systemctl status nutriai-bot
```

**Должно показать:** `Active: active (running)`

---

## Шаг 12: Просмотр логов

```bash
# Просмотр логов в реальном времени
sudo journalctl -u nutriai-bot -f

# Последние 100 строк
sudo journalctl -u nutriai-bot -n 100

# Логи за сегодня
sudo journalctl -u nutriai-bot --since today
```

---

## 🔄 Управление ботом

```bash
# Запустить
sudo systemctl start nutriai-bot

# Остановить
sudo systemctl stop nutriai-bot

# Перезапустить
sudo systemctl restart nutriai-bot

# Статус
sudo systemctl status nutriai-bot

# Отключить автозапуск
sudo systemctl disable nutriai-bot
```

---

## 🔒 Безопасность

### 1. Настройте firewall

```bash
# Установите ufw
sudo apt install ufw -y

# Разрешите SSH
sudo ufw allow 22/tcp

# Разрешите PostgreSQL (только локально)
sudo ufw allow from 127.0.0.1 to any port 5432

# Включите firewall
sudo ufw enable

# Проверьте
sudo ufw status
```

### 2. Измените SSH порт (опционально)

```bash
sudo nano /etc/ssh/sshd_config
# Измените: Port 22 → Port 2222
sudo systemctl restart sshd
```

### 3. Настройте автоматические обновления

```bash
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 🔄 Обновление бота

```bash
# Остановите бота
sudo systemctl stop nutriai-bot

# Перейдите в папку
cd ~/tricer

# Получите обновления
git pull origin claude/migrate-bot-postgresql-011CUd51gLv17LD4j4snhS1m

# Активируйте виртуальное окружение
source venv/bin/activate

# Обновите зависимости
pip install -r requirements.txt --upgrade

# Запустите бота
sudo systemctl start nutriai-bot

# Проверьте логи
sudo journalctl -u nutriai-bot -f
```

---

## 📊 Мониторинг

### Проверка использования ресурсов

```bash
# Использование CPU и RAM
htop

# Использование диска
df -h

# Статус PostgreSQL
sudo systemctl status postgresql

# Размер базы данных
sudo -u postgres psql -c "SELECT pg_size_pretty(pg_database_size('nutriai'));"
```

---

## ❓ Решение проблем

### Бот не запускается

```bash
# Проверьте логи
sudo journalctl -u nutriai-bot -n 50

# Проверьте .env файл
cat .env

# Проверьте права доступа
ls -la /root/tricer/.env
```

### Ошибка подключения к БД

```bash
# Проверьте статус PostgreSQL
sudo systemctl status postgresql

# Проверьте подключение
sudo -u postgres psql -d nutriai -c "SELECT version();"

# Проверьте пароль в .env
cat .env | grep POSTGRES_PASSWORD
```

### Ошибка 403 от Claude API

**Если вы на иностранном VDS - это странно!**

Проверьте:
```bash
# IP адрес сервера
curl ifconfig.me

# Страну
curl ipinfo.io/country
```

Если показывает **RU** - значит сервер в России, нужен VPN!

---

## 🌐 Развертывание на других платформах

### Docker (скоро)

```bash
# Будет добавлено позже
docker-compose up -d
```

### Windows Server

**Требования:**
- Windows Server 2016+ или Windows 10/11
- PowerShell или Command Prompt с правами администратора
- Python 3.11 или 3.12 (не 3.13, нет бинарных пакетов для pandas)
- PostgreSQL 12+

**Установка зависимостей:**

```cmd
# Простой способ (рекомендуется)
install-windows.bat

# Или вручную:
python -m pip install --upgrade pip
pip install pandas numpy matplotlib --only-binary :all:
pip install -r requirements.txt
```

**ВАЖНО:** Используйте `install-windows.bat` чтобы избежать ошибок компиляции pandas/numpy/matplotlib, которые требуют Visual Studio Build Tools (10+ GB).

**Настройка:**
1. Установите PostgreSQL 12+ с https://www.postgresql.org/download/windows/
2. Создайте базу данных (через pgAdmin или psql)
3. Скопируйте `.env.example` в `.env` и настройте параметры
4. Запустите `python init_db.py`
5. Запустите бота: `python -m app.bot.main`

**Автозапуск через Task Scheduler:**
Создайте задачу в Task Scheduler с триггером "At system startup" и действием запуска `python -m app.bot.main` в папке проекта.

---

## 📝 Чеклист после развертывания

- [ ] Бот успешно запускается
- [ ] Команда `/start` работает в Telegram
- [ ] Распознавание фото работает (нет ошибок 403)
- [ ] PostgreSQL работает
- [ ] Автозапуск настроен (`systemctl enable`)
- [ ] Firewall настроен
- [ ] SECRET_KEY изменен на уникальный
- [ ] Пароль БД изменен на надежный
- [ ] Логи доступны (`journalctl -u nutriai-bot -f`)

---

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи: `sudo journalctl -u nutriai-bot -f`
2. Создайте Issue на GitHub
3. Приложите логи с ошибками

---

## 🎉 Готово!

Ваш бот работает 24/7 на надежном сервере! 🚀
