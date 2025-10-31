"""
Комплексное тестирование всех компонентов NutriAI Bot
"""
import asyncio
import sys
from datetime import datetime
from typing import Dict, List, Tuple
import httpx

# Цветной вывод для Windows
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Красивый заголовок"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE} {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.RESET}\n")


def print_test(name: str, status: str, details: str = ""):
    """Вывод результата теста"""
    if status == "OK":
        icon = "✓"
        color = Colors.GREEN
    elif status == "FAIL":
        icon = "✗"
        color = Colors.RED
    else:
        icon = "⚠"
        color = Colors.YELLOW

    print(f"[{color}{icon}{Colors.RESET}] {name:<50} {color}{status}{Colors.RESET}")
    if details:
        print(f"    {details}")


async def test_env_file() -> Tuple[bool, str]:
    """Тест 1: Проверка .env файла"""
    try:
        from pathlib import Path
        env_path = Path(".env")

        if not env_path.exists():
            return False, ".env file not found"

        # Читаем .env
        with open(env_path, 'r', encoding='utf-8') as f:
            env_content = f.read()

        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'ANTHROPIC_API_KEY',
            'DATABASE_URL',
            'REDIS_URL'
        ]

        missing = []
        placeholders = []

        for var in required_vars:
            if var not in env_content:
                missing.append(var)
            elif f"{var}=your_" in env_content or f"{var}=<" in env_content:
                placeholders.append(var)

        if missing:
            return False, f"Missing variables: {', '.join(missing)}"
        if placeholders:
            return False, f"Placeholder values: {', '.join(placeholders)}"

        return True, "All required variables present"

    except Exception as e:
        return False, str(e)


async def test_config_loading() -> Tuple[bool, str]:
    """Тест 2: Загрузка конфигурации"""
    try:
        from app.config import settings

        # Проверяем критические настройки
        checks = {
            'TELEGRAM_BOT_TOKEN': len(settings.TELEGRAM_BOT_TOKEN) > 20,
            'ANTHROPIC_API_KEY': len(settings.ANTHROPIC_API_KEY) > 20,
            'DATABASE_URL': settings.DATABASE_URL.startswith('postgresql'),
            'REDIS_URL': settings.REDIS_URL.startswith('redis'),
        }

        failed = [k for k, v in checks.items() if not v]

        if failed:
            return False, f"Invalid config: {', '.join(failed)}"

        return True, f"Config loaded (METRICS_PORT={settings.METRICS_PORT})"

    except Exception as e:
        return False, str(e)


async def test_database_connection() -> Tuple[bool, str]:
    """Тест 3: Подключение к PostgreSQL"""
    try:
        from app.db.session import async_session_maker, engine
        from sqlalchemy import text

        async with async_session_maker() as session:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar()

            # Проверяем количество таблиц
            result = await session.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            table_count = result.scalar()

            return True, f"PostgreSQL connected, {table_count} tables"

    except Exception as e:
        return False, str(e)


async def test_redis_connection() -> Tuple[bool, str]:
    """Тест 4: Подключение к Redis"""
    try:
        import redis
        from app.config import settings

        r = redis.from_url(settings.REDIS_URL)

        # Проверка ping
        if not r.ping():
            return False, "Redis PING failed"

        # Проверка set/get
        test_key = "test:nutriai:connection"
        r.set(test_key, "test_value", ex=10)
        value = r.get(test_key)
        r.delete(test_key)

        if value != b"test_value":
            return False, "Redis SET/GET failed"

        # Проверка информации
        info = r.info()
        used_memory = info.get('used_memory_human', 'unknown')

        return True, f"Redis connected (memory: {used_memory})"

    except Exception as e:
        return False, str(e)


async def test_telegram_api() -> Tuple[bool, str]:
    """Тест 5: Telegram Bot API"""
    try:
        from app.config import settings

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Проверка getMe
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
            response = await client.get(url)

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            data = response.json()
            if not data.get('ok'):
                return False, data.get('description', 'Unknown error')

            bot_info = data.get('result', {})
            bot_name = bot_info.get('first_name', 'Unknown')
            bot_username = bot_info.get('username', 'unknown')

            # Проверка webhook
            url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getWebhookInfo"
            response = await client.get(url)
            webhook_data = response.json()
            webhook_info = webhook_data.get('result', {})
            webhook_url = webhook_info.get('url', '')

            if webhook_url:
                return False, f"Webhook active: {webhook_url} (should be empty for polling)"

            return True, f"Bot: @{bot_username} ({bot_name})"

    except Exception as e:
        return False, str(e)


async def test_claude_api() -> Tuple[bool, str]:
    """Тест 6: Claude AI API"""
    try:
        from anthropic import AsyncAnthropic
        from app.config import settings

        # Проверяем наличие прокси/воркера
        kwargs = {"api_key": settings.ANTHROPIC_API_KEY}

        if settings.CLOUDFLARE_WORKER_URL:
            kwargs["base_url"] = settings.CLOUDFLARE_WORKER_URL
            proxy_info = "via Cloudflare Worker"
        elif settings.WARP_PROXY_URL:
            import httpx
            kwargs["http_client"] = httpx.AsyncClient(
                proxy=settings.WARP_PROXY_URL,
                timeout=30.0
            )
            proxy_info = "via WARP Proxy"
        else:
            proxy_info = "direct connection"

        client = AsyncAnthropic(**kwargs)

        # Простой тестовый запрос
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )

        if not response.content:
            return False, "Empty response from Claude"

        return True, f"Claude API OK ({proxy_info})"

    except Exception as e:
        error_str = str(e)
        if "401" in error_str:
            return False, "Invalid API key"
        elif "403" in error_str:
            return False, "Access denied (check geo-restrictions)"
        elif "429" in error_str:
            return False, "Rate limit exceeded"
        else:
            return False, str(e)[:60]


async def test_celery_worker() -> Tuple[bool, str]:
    """Тест 7: Celery Worker"""
    try:
        from app.celery_app import celery_app

        # Проверка активных воркеров
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()

        if not active_workers:
            return False, "No active workers found (start Celery worker)"

        worker_names = list(active_workers.keys())
        worker_count = len(worker_names)

        # Проверка очереди
        reserved = inspect.reserved()
        total_tasks = sum(len(tasks) for tasks in reserved.values()) if reserved else 0

        return True, f"{worker_count} worker(s) active, {total_tasks} tasks in queue"

    except Exception as e:
        return False, str(e)


async def test_metrics_endpoint() -> Tuple[bool, str]:
    """Тест 8: Prometheus метрики"""
    try:
        from app.config import settings

        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"http://localhost:{settings.METRICS_PORT}/metrics"
            response = await client.get(url)

            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"

            content = response.text

            # Проверяем наличие ключевых метрик
            required_metrics = [
                'bot_messages_total',
                'claude_api_calls_total',
                'bot_active_users',
                'bot_db_pool_connections'
            ]

            missing = [m for m in required_metrics if m not in content]
            if missing:
                return False, f"Missing metrics: {', '.join(missing)}"

            # Считаем количество метрик
            metric_count = len([line for line in content.split('\n') if line and not line.startswith('#')])

            return True, f"Metrics endpoint active ({metric_count} data points)"

    except httpx.ConnectError:
        return False, "Metrics server not running (bot not started?)"
    except Exception as e:
        return False, str(e)


async def test_database_models() -> Tuple[bool, str]:
    """Тест 9: Модели базы данных"""
    try:
        from app.db.session import async_session_maker
        from app.models.user import User
        from sqlalchemy import select, func

        async with async_session_maker() as session:
            # Проверяем количество пользователей
            result = await session.execute(select(func.count(User.id)))
            user_count = result.scalar()

            # Проверяем недавних пользователей
            result = await session.execute(
                select(User).order_by(User.created_at.desc()).limit(1)
            )
            latest_user = result.scalar_one_or_none()

            if latest_user:
                latest_info = f"Latest: {latest_user.telegram_id}"
            else:
                latest_info = "No users yet"

            return True, f"{user_count} users in DB ({latest_info})"

    except Exception as e:
        return False, str(e)


async def test_rate_limiter() -> Tuple[bool, str]:
    """Тест 10: Rate Limiter"""
    try:
        from aiolimiter import AsyncLimiter
        from app.config import settings

        # Создаем тестовый лимитер (10 запросов в секунду)
        limiter = AsyncLimiter(10, 1)

        # Проверяем работу
        start = asyncio.get_event_loop().time()
        for _ in range(5):
            async with limiter:
                pass
        elapsed = asyncio.get_event_loop().time() - start

        # Проверяем конфигурацию из settings
        rate_limit = settings.CLAUDE_RATE_LIMIT
        max_retries = settings.CLAUDE_MAX_RETRIES

        return True, f"Rate limiter OK (Claude: {rate_limit} req/min, {max_retries} retries)"

    except Exception as e:
        return False, str(e)


async def test_nutrition_calculator() -> Tuple[bool, str]:
    """Тест 11: Калькулятор питания"""
    try:
        from app.services.nutrition_calc import NutritionCalculator

        # Тест расчета BMR
        bmr = NutritionCalculator.calculate_bmr(
            gender='male',
            age=30,
            weight=80,
            height=180,
            activity_level='moderate'
        )

        if bmr < 1000 or bmr > 5000:
            return False, f"Invalid BMR: {bmr}"

        # Тест расчета BMI
        bmi = NutritionCalculator.calculate_bmi(80, 180)
        category = NutritionCalculator.get_bmi_category(bmi)

        if not category:
            return False, "BMI category calculation failed"

        # Тест расчета макросов
        macros = NutritionCalculator.calculate_macros(
            target_calories=2000,
            goal='maintain',
            age=30,
            gender='male'
        )

        if not all(k in macros for k in ['proteins', 'fats', 'carbs']):
            return False, "Macros calculation incomplete"

        return True, f"Calculator OK (BMR={int(bmr)}, BMI={bmi:.1f})"

    except Exception as e:
        return False, str(e)


async def test_bot_handlers() -> Tuple[bool, str]:
    """Тест 12: Проверка импортов handlers"""
    try:
        # Проверяем что все handlers импортируются без ошибок
        from app.bot.handlers import start
        from app.bot.handlers import photo
        from app.bot.handlers import chat
        from app.bot.handlers import meal_plan
        from app.bot.handlers import diary
        from app.bot.handlers import restaurant
        from app.bot.handlers import reminders
        from app.bot.handlers import reports
        from app.bot.handlers import wellness
        from app.bot.handlers import medical_analysis
        from app.bot.handlers import pantry

        handlers = [
            'start', 'photo', 'chat', 'meal_plan', 'diary',
            'restaurant', 'reminders', 'reports', 'wellness',
            'medical_analysis', 'pantry'
        ]

        return True, f"{len(handlers)} handler modules loaded"

    except Exception as e:
        return False, str(e)


async def run_all_tests():
    """Запуск всех тестов"""
    print_header("NutriAI Bot - Комплексное тестирование")
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    tests = [
        ("1. Environment File", test_env_file),
        ("2. Configuration Loading", test_config_loading),
        ("3. PostgreSQL Connection", test_database_connection),
        ("4. Redis Connection", test_redis_connection),
        ("5. Telegram Bot API", test_telegram_api),
        ("6. Claude AI API", test_claude_api),
        ("7. Celery Worker", test_celery_worker),
        ("8. Prometheus Metrics", test_metrics_endpoint),
        ("9. Database Models", test_database_models),
        ("10. Rate Limiter", test_rate_limiter),
        ("11. Nutrition Calculator", test_nutrition_calculator),
        ("12. Bot Handlers", test_bot_handlers),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            success, details = await test_func()
            status = "OK" if success else "FAIL"
            print_test(test_name, status, details)
            results.append((test_name, success, details))
        except Exception as e:
            print_test(test_name, "FAIL", f"Exception: {str(e)}")
            results.append((test_name, False, str(e)))

    # Итоги
    print_header("Результаты тестирования")

    total = len(results)
    passed = sum(1 for _, success, _ in results if success)
    failed = total - passed

    print(f"Всего тестов: {total}")
    print(f"{Colors.GREEN}✓ Успешно: {passed}{Colors.RESET}")
    print(f"{Colors.RED}✗ Провалено: {failed}{Colors.RESET}")
    print(f"\nПроцент успеха: {(passed/total*100):.1f}%\n")

    # Рекомендации
    if failed > 0:
        print_header("Рекомендации по исправлению")

        for test_name, success, details in results:
            if not success:
                print(f"\n{Colors.RED}✗ {test_name}{Colors.RESET}")
                print(f"  Проблема: {details}")

                # Даем рекомендации
                if "Redis" in test_name:
                    print(f"  {Colors.YELLOW}Решение:{Colors.RESET} Запустите Redis: redis-server или net start Redis")
                elif "PostgreSQL" in test_name:
                    print(f"  {Colors.YELLOW}Решение:{Colors.RESET} Запустите PostgreSQL и проверьте DATABASE_URL в .env")
                elif "Telegram" in test_name:
                    print(f"  {Colors.YELLOW}Решение:{Colors.RESET} Проверьте TELEGRAM_BOT_TOKEN в .env (запустите check-token.bat)")
                elif "Claude" in test_name:
                    print(f"  {Colors.YELLOW}Решение:{Colors.RESET} Проверьте ANTHROPIC_API_KEY и геоблокировку")
                elif "Celery" in test_name:
                    print(f"  {Colors.YELLOW}Решение:{Colors.RESET} Запустите Celery worker: celery -A app.celery_app worker")
                elif "Metrics" in test_name:
                    print(f"  {Colors.YELLOW}Решение:{Colors.RESET} Запустите бота: python -m app.bot.main")
                elif ".env" in test_name:
                    print(f"  {Colors.YELLOW}Решение:{Colors.RESET} Создайте .env файл из .env.example")
        print()

    # Проверка готовности к production
    critical_tests = [
        "PostgreSQL Connection",
        "Redis Connection",
        "Telegram Bot API",
        "Claude AI API"
    ]

    critical_passed = all(
        success for name, success, _ in results
        if any(ct in name for ct in critical_tests)
    )

    if critical_passed and passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Все тесты пройдены! Бот готов к запуску!{Colors.RESET}\n")
        return 0
    elif critical_passed:
        print(f"\n{Colors.YELLOW}⚠ Критические компоненты работают, но есть некритичные ошибки{Colors.RESET}\n")
        return 1
    else:
        print(f"\n{Colors.RED}✗ Критические ошибки! Бот не готов к запуску{Colors.RESET}\n")
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
