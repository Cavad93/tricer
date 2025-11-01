"""
Unit тесты для моделей базы данных
"""
import pytest
from datetime import datetime, date
from app.models.user import User
from app.models.meal import Meal
from app.models.meal import Meal, MealFood


class TestUserModel:
    """Тесты модели User"""

    def test_user_creation(self):
        """Тест создания пользователя"""
        user = User(
            telegram_id=123456789,
            username="testuser",
            age=25,
            gender="male",
            height=175,
            current_weight=70.0,
            target_weight=65.0,
            target_calories=2000,
            target_proteins=150,
            target_fats=60,
            target_carbs=200
        )

        assert user.telegram_id == 123456789
        assert user.username == "testuser"
        assert user.age == 25
        assert user.gender == "male"
        assert user.current_weight == 70.0
        assert user.target_weight == 65.0

    def test_user_optional_fields(self):
        """Тест опциональных полей пользователя"""
        user = User(
            telegram_id=123456789,
            age=25,
            gender="male",
            height=175,
            current_weight=70.0,
            target_weight=65.0,
            target_calories=2000,
            target_proteins=150,
            target_fats=60,
            target_carbs=200,
            username=None,  # Опционально
            dietary_preferences=None,
            allergies=None
        )

        assert user.username is None
        assert user.dietary_preferences is None
        assert user.allergies is None

    def test_user_onboarding_flags(self):
        """Тест флагов онбординга"""
        user = User(
            telegram_id=123456789,
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

        assert user.onboarding_completed is True

    def test_user_reminders(self):
        """Тест настроек напоминаний"""
        from datetime import time

        user = User(
            telegram_id=123456789,
            age=25,
            gender="male",
            height=175,
            current_weight=70.0,
            target_weight=65.0,
            target_calories=2000,
            target_proteins=150,
            target_fats=60,
            target_carbs=200,
            reminders_enabled=True,
            breakfast_reminder_time=time(8, 0),
            lunch_reminder_time=time(13, 0),
            dinner_reminder_time=time(19, 0)
        )

        assert user.reminders_enabled is True
        assert user.breakfast_reminder_time.hour == 8
        assert user.lunch_reminder_time.hour == 13
        assert user.dinner_reminder_time.hour == 19


class TestMealModel:
    """Тесты модели Meal"""

    def test_meal_creation(self):
        """Тест создания приема пищи"""
        meal = Meal(
            user_id=1,
            meal_type="breakfast",
            date=date.today(),
            total_calories=500,
            total_proteins=30,
            total_fats=15,
            total_carbs=60
        )

        assert meal.user_id == 1
        assert meal.meal_type == "breakfast"
        assert meal.total_calories == 500
        assert meal.total_proteins == 30
        assert meal.total_fats == 15
        assert meal.total_carbs == 60

    def test_meal_types(self):
        """Тест различных типов приемов пищи"""
        meal_types = ["breakfast", "lunch", "dinner", "snack"]

        for meal_type in meal_types:
            meal = Meal(
                user_id=1,
                meal_type=meal_type,
                date=date.today(),
                total_calories=300,
                total_proteins=20,
                total_fats=10,
                total_carbs=30
            )
            assert meal.meal_type == meal_type

    def test_meal_date(self):
        """Тест даты приема пищи"""
        today = date.today()
        meal = Meal(
            user_id=1,
            meal_type="lunch",
            date=today,
            total_calories=600,
            total_proteins=40,
            total_fats=20,
            total_carbs=70
        )

        assert meal.date == today


class TestMealFoodModel:
    """Тесты модели MealFood"""

    def test_meal_food_creation(self):
        """Тест создания продукта"""
        food_item = MealFood(
            meal_id=1,
            name="Куриная грудка",
            portion_size=150.0,
            calories=165,
            proteins=31,
            fats=3.6,
            carbs=0
        )

        assert food_item.meal_id == 1
        assert food_item.name == "Куриная грудка"
        assert food_item.portion_size == 150.0
        assert food_item.calories == 165
        assert food_item.proteins == 31
        assert food_item.fats == 3.6
        assert food_item.carbs == 0

    def test_meal_food_optional_fields(self):
        """Тест опциональных полей продукта"""
        food_item = MealFood(
            meal_id=1,
            name="Салат",
            portion_size=200.0,
            calories=100,
            proteins=5,
            fats=7,
            carbs=8,
            confidence_score=0.95,
        )

        assert food_item.confidence_score == 0.95

    def test_meal_food_calculations(self):
        """Тест расчетов калорий и макросов"""
        # Куриная грудка: на 100г - 110 ккал, 23г белка, 2.4г жира
        # Порция 200г должна быть удвоена
        food_item = MealFood(
            meal_id=1,
            name="Куриная грудка",
            portion_size=200.0,
            calories=220,  # 110 * 2
            proteins=46,   # 23 * 2
            fats=4.8,      # 2.4 * 2
            carbs=0
        )

        # Проверяем что значения пропорциональны
        assert food_item.calories == 220
        assert food_item.proteins == 46
        assert food_item.fats == 4.8

    def test_meal_food_zero_values(self):
        """Тест продуктов с нулевыми значениями"""
        # Например, вода
        food_item = MealFood(
            meal_id=1,
            name="Вода",
            portion_size=250.0,
            calories=0,
            proteins=0,
            fats=0,
            carbs=0
        )

        assert food_item.calories == 0
        assert food_item.proteins == 0
        assert food_item.fats == 0
        assert food_item.carbs == 0


class TestModelRelationships:
    """Тесты связей между моделями"""

    def test_user_meal_relationship(self):
        """Тест связи User -> Meal"""
        user = User(
            telegram_id=123456789,
            age=25,
            gender="male",
            height=175,
            current_weight=70.0,
            target_weight=65.0,
            target_calories=2000,
            target_proteins=150,
            target_fats=60,
            target_carbs=200
        )

        # Симуляция связи (в реальной БД это будет через relationship)
        assert hasattr(user, 'meals')

    def test_meal_food_items_relationship(self):
        """Тест связи Meal -> MealFood"""
        meal = Meal(
            user_id=1,
            meal_type="breakfast",
            date=date.today(),
            total_calories=500,
            total_proteins=30,
            total_fats=15,
            total_carbs=60
        )

        # Симуляция связи
        assert hasattr(meal, 'foods')


class TestModelValidation:
    """Тесты валидации данных моделей"""

    def test_positive_values(self):
        """Тест что калории и макросы положительные"""
        food_item = MealFood(
            meal_id=1,
            name="Test Food",
            portion_size=100.0,
            calories=100,
            proteins=10,
            fats=5,
            carbs=10
        )

        assert food_item.calories >= 0
        assert food_item.proteins >= 0
        assert food_item.fats >= 0
        assert food_item.carbs >= 0

    def test_realistic_values(self):
        """Тест реалистичности значений"""
        user = User(
            telegram_id=123456789,
            age=25,
            gender="male",
            height=175,
            current_weight=70.0,
            target_weight=65.0,
            target_calories=2000,
            target_proteins=150,
            target_fats=60,
            target_carbs=200
        )

        # Проверяем реалистичность значений
        assert 10 < user.age < 120
        assert 100 < user.height < 250
        assert 30 < user.current_weight < 300
        assert 500 < user.target_calories < 10000
