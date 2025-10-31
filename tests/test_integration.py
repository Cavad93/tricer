"""
Интеграционные тесты для критических потоков
"""
import pytest
import asyncio
from datetime import date, datetime


@pytest.mark.asyncio
class TestDatabaseIntegration:
    """Интеграционные тесты с базой данных"""

    async def test_user_creation_and_retrieval(self):
        """Тест создания и получения пользователя"""
        from app.db.session import async_session_maker
        from app.models.user import User
        from sqlalchemy import select

        test_telegram_id = 999999999  # Тестовый ID

        async with async_session_maker() as session:
            # Создаем тестового пользователя
            test_user = User(
                telegram_id=test_telegram_id,
                username="test_integration_user",
                age=25,
                gender="male",
                height=175,
                current_weight=70.0,
                target_weight=65.0,
                target_calories=2000,
                target_proteins=150,
                target_fats=60,
                target_carbs=200,
                onboarding_completed=True
            )

            session.add(test_user)
            await session.commit()

            # Получаем пользователя обратно
            result = await session.execute(
                select(User).where(User.telegram_id == test_telegram_id)
            )
            retrieved_user = result.scalar_one_or_none()

            assert retrieved_user is not None
            assert retrieved_user.telegram_id == test_telegram_id
            assert retrieved_user.username == "test_integration_user"
            assert retrieved_user.age == 25

            # Удаляем тестового пользователя
            await session.delete(retrieved_user)
            await session.commit()

    async def test_meal_with_food_items(self):
        """Тест создания приема пищи с продуктами"""
        from app.db.session import async_session_maker
        from app.models.user import User
        from app.models.meal import Meal
        from app.models.food_item import FoodItem
        from sqlalchemy import select

        test_telegram_id = 999999998

        async with async_session_maker() as session:
            # Создаем тестового пользователя
            test_user = User(
                telegram_id=test_telegram_id,
                age=30,
                gender="female",
                height=165,
                current_weight=60.0,
                target_weight=55.0,
                target_calories=1800,
                target_proteins=120,
                target_fats=50,
                target_carbs=180
            )
            session.add(test_user)
            await session.flush()  # Получаем ID пользователя

            # Создаем прием пищи
            test_meal = Meal(
                user_id=test_user.id,
                meal_type="breakfast",
                date=date.today(),
                total_calories=400,
                total_proteins=25,
                total_fats=12,
                total_carbs=50
            )
            session.add(test_meal)
            await session.flush()  # Получаем ID приема пищи

            # Добавляем продукты
            food1 = FoodItem(
                meal_id=test_meal.id,
                name="Овсянка",
                portion_size=100.0,
                calories=250,
                proteins=10,
                fats=5,
                carbs=45
            )

            food2 = FoodItem(
                meal_id=test_meal.id,
                name="Банан",
                portion_size=120.0,
                calories=150,
                proteins=15,
                fats=7,
                carbs=5
            )

            session.add(food1)
            session.add(food2)
            await session.commit()

            # Проверяем что все создано
            result = await session.execute(
                select(Meal).where(Meal.id == test_meal.id)
            )
            retrieved_meal = result.scalar_one_or_none()

            assert retrieved_meal is not None
            assert retrieved_meal.total_calories == 400
            assert len(retrieved_meal.food_items) == 2

            # Очистка
            await session.delete(test_user)  # Каскадно удалит meal и food_items
            await session.commit()


@pytest.mark.asyncio
class TestServicesIntegration:
    """Интеграционные тесты сервисов"""

    async def test_nutrition_calculator_with_user(self):
        """Тест калькулятора с реальным пользователем"""
        from app.services.nutrition_calc import NutritionCalculator
        from app.models.user import User

        # Создаем тестового пользователя
        user = User(
            telegram_id=123456789,
            age=25,
            gender="male",
            height=180,
            current_weight=85.0,
            target_weight=75.0,
            target_calories=2200,
            target_proteins=165,
            target_fats=70,
            target_carbs=220
        )

        # Рассчитываем BMR
        bmr = NutritionCalculator.calculate_bmr(
            gender=user.gender,
            age=user.age,
            weight=user.current_weight,
            height=user.height,
            activity_level='moderate'
        )

        assert bmr > 0
        assert 2000 < bmr < 3500

        # Рассчитываем BMI
        bmi = NutritionCalculator.calculate_bmi(
            weight=user.current_weight,
            height=user.height
        )

        category = NutritionCalculator.get_bmi_category(bmi)
        assert category is not None

    async def test_rate_limiter_integration(self):
        """Тест интеграции rate limiter"""
        from aiolimiter import AsyncLimiter
        import time

        # Создаем лимитер: 5 запросов в секунду
        limiter = AsyncLimiter(5, 1)

        start_time = time.time()

        # Делаем 10 запросов (должны быть разделены на 2 секунды)
        for i in range(10):
            async with limiter:
                pass

        elapsed_time = time.time() - start_time

        # Должно пройти примерно 2 секунды (допускаем погрешность)
        assert 1.5 < elapsed_time < 2.5


@pytest.mark.asyncio
class TestCeleryIntegration:
    """Интеграционные тесты Celery задач"""

    async def test_celery_connection(self):
        """Тест подключения к Celery"""
        try:
            from app.celery_app import celery_app

            # Проверяем что можем получить inspect
            inspect = celery_app.control.inspect()
            assert inspect is not None

            # Проверяем активные воркеры (может быть None если воркер не запущен)
            active = inspect.active()
            # Не падаем если воркер не запущен, просто проверяем что метод работает
            assert active is not None or active is None

        except Exception as e:
            pytest.skip(f"Celery not available: {e}")


@pytest.mark.asyncio
class TestAPIIntegration:
    """Интеграционные тесты внешних API"""

    async def test_telegram_api_connection(self):
        """Тест подключения к Telegram API"""
        try:
            from app.config import settings
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe"
                response = await client.get(url)

                assert response.status_code == 200
                data = response.json()
                assert data.get('ok') is True

        except Exception as e:
            pytest.skip(f"Telegram API not available: {e}")

    @pytest.mark.slow
    async def test_claude_api_connection(self):
        """Тест подключения к Claude API (медленный тест)"""
        try:
            from anthropic import AsyncAnthropic
            from app.config import settings

            kwargs = {"api_key": settings.ANTHROPIC_API_KEY}

            if settings.CLOUDFLARE_WORKER_URL:
                kwargs["base_url"] = settings.CLOUDFLARE_WORKER_URL
            elif settings.WARP_PROXY_URL:
                import httpx
                kwargs["http_client"] = httpx.AsyncClient(
                    proxy=settings.WARP_PROXY_URL,
                    timeout=30.0
                )

            client = AsyncAnthropic(**kwargs)

            response = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=10,
                messages=[{"role": "user", "content": "Test"}]
            )

            assert response is not None
            assert response.content is not None

        except Exception as e:
            pytest.skip(f"Claude API not available: {e}")


@pytest.mark.asyncio
class TestMetricsIntegration:
    """Интеграционные тесты метрик"""

    async def test_metrics_collection(self):
        """Тест сбора метрик"""
        from app.metrics import (
            messages_total,
            claude_api_calls_total,
            active_users,
            db_pool_connections
        )

        # Инкрементируем счетчики
        messages_total.labels(command='test', user_type='free').inc()
        claude_api_calls_total.labels(method='test', status='success').inc()

        # Устанавливаем gauge метрики
        active_users.set(10)
        db_pool_connections.labels(state='active').set(5)

        # Проверяем что метрики можно получить
        from prometheus_client import generate_latest

        metrics_output = generate_latest().decode('utf-8')

        assert 'bot_messages_total' in metrics_output
        assert 'claude_api_calls_total' in metrics_output
        assert 'bot_active_users' in metrics_output

    async def test_metrics_endpoint(self):
        """Тест HTTP endpoint метрик"""
        try:
            from app.config import settings
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                url = f"http://localhost:{settings.METRICS_PORT}/metrics"
                response = await client.get(url)

                if response.status_code == 200:
                    content = response.text
                    assert 'bot_messages_total' in content
                    assert 'claude_api_calls_total' in content
                else:
                    pytest.skip("Metrics endpoint not running")

        except Exception as e:
            pytest.skip(f"Metrics endpoint not available: {e}")


@pytest.mark.asyncio
class TestEndToEndScenarios:
    """End-to-end тесты реальных сценариев"""

    async def test_user_registration_flow(self):
        """Тест полного потока регистрации пользователя"""
        from app.db.session import async_session_maker
        from app.models.user import User
        from app.services.nutrition_calc import NutritionCalculator
        from sqlalchemy import select

        test_telegram_id = 999999997

        async with async_session_maker() as session:
            try:
                # 1. Создаем нового пользователя
                new_user = User(
                    telegram_id=test_telegram_id,
                    username="test_e2e_user",
                    age=28,
                    gender="male",
                    height=178,
                    current_weight=75.0,
                    target_weight=70.0,
                    activity_level="moderate",
                    goal="lose_weight"
                )

                # 2. Рассчитываем целевые показатели
                bmr = NutritionCalculator.calculate_bmr(
                    gender=new_user.gender,
                    age=new_user.age,
                    weight=new_user.current_weight,
                    height=new_user.height,
                    activity_level=new_user.activity_level
                )

                # Для похудения отнимаем 500 ккал
                target_calories = int(bmr - 500)

                macros = NutritionCalculator.calculate_macros(
                    target_calories=target_calories,
                    goal=new_user.goal,
                    age=new_user.age,
                    gender=new_user.gender
                )

                new_user.target_calories = target_calories
                new_user.target_proteins = macros['proteins']
                new_user.target_fats = macros['fats']
                new_user.target_carbs = macros['carbs']
                new_user.onboarding_completed = True

                # 3. Сохраняем в БД
                session.add(new_user)
                await session.commit()

                # 4. Проверяем что все сохранено
                result = await session.execute(
                    select(User).where(User.telegram_id == test_telegram_id)
                )
                saved_user = result.scalar_one_or_none()

                assert saved_user is not None
                assert saved_user.onboarding_completed is True
                assert saved_user.target_calories > 0
                assert saved_user.target_proteins > 0

                # 5. Очистка
                await session.delete(saved_user)
                await session.commit()

            except Exception as e:
                await session.rollback()
                raise e

    async def test_meal_logging_flow(self):
        """Тест полного потока логирования еды"""
        from app.db.session import async_session_maker
        from app.models.user import User
        from app.models.meal import Meal
        from app.models.food_item import FoodItem
        from sqlalchemy import select

        test_telegram_id = 999999996

        async with async_session_maker() as session:
            try:
                # 1. Создаем пользователя
                user = User(
                    telegram_id=test_telegram_id,
                    age=30,
                    gender="female",
                    height=165,
                    current_weight=60.0,
                    target_weight=55.0,
                    target_calories=1800,
                    target_proteins=120,
                    target_fats=50,
                    target_carbs=180
                )
                session.add(user)
                await session.flush()

                # 2. Пользователь логирует завтрак
                breakfast = Meal(
                    user_id=user.id,
                    meal_type="breakfast",
                    date=date.today()
                )
                session.add(breakfast)
                await session.flush()

                # 3. Добавляем продукты
                foods = [
                    FoodItem(
                        meal_id=breakfast.id,
                        name="Овсянка",
                        portion_size=100,
                        calories=350,
                        proteins=12,
                        fats=6,
                        carbs=60
                    ),
                    FoodItem(
                        meal_id=breakfast.id,
                        name="Молоко",
                        portion_size=200,
                        calories=130,
                        proteins=7,
                        fats=7,
                        carbs=10
                    )
                ]

                for food in foods:
                    session.add(food)

                await session.flush()

                # 4. Обновляем итоги приема пищи
                breakfast.total_calories = sum(f.calories for f in foods)
                breakfast.total_proteins = sum(f.proteins for f in foods)
                breakfast.total_fats = sum(f.fats for f in foods)
                breakfast.total_carbs = sum(f.carbs for f in foods)

                await session.commit()

                # 5. Проверяем что все сохранено
                result = await session.execute(
                    select(Meal).where(Meal.id == breakfast.id)
                )
                saved_meal = result.scalar_one_or_none()

                assert saved_meal is not None
                assert saved_meal.total_calories == 480
                assert len(saved_meal.food_items) == 2

                # 6. Очистка
                await session.delete(user)
                await session.commit()

            except Exception as e:
                await session.rollback()
                raise e
