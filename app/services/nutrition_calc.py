"""
Сервис для расчета целевых калорий и макронутриентов
"""
from app.models.user import Gender, Goal, ActivityLevel
from app.schemas.user import NutritionTargets


class NutritionCalculator:
    """Калькулятор для расчета целевых показателей питания"""

    # Коэффициенты активности для TDEE
    ACTIVITY_MULTIPLIERS = {
        ActivityLevel.MINIMAL: 1.2,
        ActivityLevel.LOW: 1.375,
        ActivityLevel.MEDIUM: 1.55,
        ActivityLevel.HIGH: 1.725,
        ActivityLevel.VERY_HIGH: 1.9,
    }

    # Дефицит/профицит калорий в зависимости от цели
    GOAL_ADJUSTMENTS = {
        Goal.WEIGHT_LOSS: -500,  # Дефицит 500 ккал/день = -0.5кг/неделя
        Goal.WEIGHT_GAIN: 300,  # Профицит 300 ккал/день = +0.3кг/неделя
        Goal.MAINTENANCE: 0,
        Goal.HEALTH: 0,
    }

    @staticmethod
    def calculate_bmr(
        gender: Gender, weight: float, height: int, age: int
    ) -> float:
        """
        Расчет базального метаболизма (BMR) по формуле Mifflin-St Jeor

        Args:
            gender: Пол
            weight: Вес в кг
            height: Рост в см
            age: Возраст в годах

        Returns:
            BMR в ккал/день
        """
        if gender == Gender.MALE:
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:  # Female
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

        return bmr

    @classmethod
    def calculate_tdee(
        cls,
        gender: Gender,
        weight: float,
        height: int,
        age: int,
        activity_level: ActivityLevel,
    ) -> float:
        """
        Расчет общих энергозатрат (TDEE)

        Args:
            gender: Пол
            weight: Вес в кг
            height: Рост в см
            age: Возраст в годах
            activity_level: Уровень активности

        Returns:
            TDEE в ккал/день
        """
        bmr = cls.calculate_bmr(gender, weight, height, age)
        multiplier = cls.ACTIVITY_MULTIPLIERS[activity_level]
        tdee = bmr * multiplier

        return tdee

    @classmethod
    def calculate_target_calories(
        cls,
        gender: Gender,
        weight: float,
        height: int,
        age: int,
        activity_level: ActivityLevel,
        goal: Goal,
    ) -> int:
        """
        Расчет целевых калорий с учетом цели

        Args:
            gender: Пол
            weight: Вес в кг
            height: Рост в см
            age: Возраст в годах
            activity_level: Уровень активности
            goal: Цель пользователя

        Returns:
            Целевые калории в ккал/день
        """
        tdee = cls.calculate_tdee(gender, weight, height, age, activity_level)
        adjustment = cls.GOAL_ADJUSTMENTS[goal]
        target = tdee + adjustment

        # Минимум 1200 ккал для женщин, 1500 для мужчин
        min_calories = 1500 if gender == Gender.MALE else 1200
        target = max(target, min_calories)

        return int(target)

    @classmethod
    async def calculate_target_calories_with_activity_bonus(
        cls,
        user_id: int,
        gender: Gender,
        weight: float,
        height: int,
        age: int,
        activity_level: ActivityLevel,
        goal: Goal,
        session
    ) -> tuple[int, int]:
        """
        Расчет целевых калорий с учетом бонусов от шагов вчерашнего дня

        Args:
            user_id: ID пользователя
            gender: Пол
            weight: Вес в кг
            height: Рост в см
            age: Возраст в годах
            activity_level: Уровень активности
            goal: Цель пользователя
            session: Сессия БД

        Returns:
            Кортеж (целевые_калории, бонусные_калории)
        """
        from datetime import date, timedelta
        from app.services.steps_tracking_service import StepsTrackingService

        # Базовые целевые калории
        base_calories = cls.calculate_target_calories(
            gender, weight, height, age, activity_level, goal
        )

        # Получаем бонусные калории от вчерашних шагов
        yesterday = date.today() - timedelta(days=1)
        bonus_calories = await StepsTrackingService.calculate_bonus_calories(
            user_id, session, yesterday
        )

        # Итоговые калории = базовые + бонус
        total_calories = base_calories + bonus_calories

        return int(total_calories), int(bonus_calories)

    @staticmethod
    def calculate_macros(
        target_calories: int, goal: Goal, weight: float
    ) -> tuple[int, int, int]:
        """
        Расчет макронутриентов (БЖУ)

        Args:
            target_calories: Целевые калории
            goal: Цель пользователя
            weight: Текущий вес (для расчета белка)

        Returns:
            Кортеж (белки_г, жиры_г, углеводы_г)
        """
        # Белок: 1.8-2.2 г на кг веса для похудения/набора
        # 1.2-1.5 г на кг для поддержания
        if goal in [Goal.WEIGHT_LOSS, Goal.WEIGHT_GAIN]:
            protein_per_kg = 2.0
        else:
            protein_per_kg = 1.5

        proteins = int(weight * protein_per_kg)

        # Жиры: 25-30% от калорий
        fat_percentage = 0.28
        fats = int((target_calories * fat_percentage) / 9)  # 9 ккал на 1г жира

        # Углеводы: остаток калорий
        protein_calories = proteins * 4  # 4 ккал на 1г белка
        fat_calories = fats * 9
        carb_calories = target_calories - protein_calories - fat_calories
        carbs = int(carb_calories / 4)  # 4 ккал на 1г углеводов

        return proteins, fats, carbs

    @classmethod
    def calculate_nutrition_targets(
        cls,
        gender: Gender,
        weight: float,
        height: int,
        age: int,
        activity_level: ActivityLevel,
        goal: Goal,
    ) -> NutritionTargets:
        """
        Полный расчет целевых показателей питания

        Args:
            gender: Пол
            weight: Вес в кг
            height: Рост в см
            age: Возраст в годах
            activity_level: Уровень активности
            goal: Цель пользователя

        Returns:
            NutritionTargets с целевыми показателями
        """
        target_calories = cls.calculate_target_calories(
            gender, weight, height, age, activity_level, goal
        )

        proteins, fats, carbs = cls.calculate_macros(target_calories, goal, weight)

        return NutritionTargets(
            calories=target_calories,
            proteins=proteins,
            fats=fats,
            carbs=carbs,
        )

    @staticmethod
    def calculate_bmi(weight: float, height: int) -> float:
        """
        Расчет индекса массы тела (ИМТ/BMI)

        Args:
            weight: Вес в кг
            height: Рост в см

        Returns:
            ИМТ (индекс массы тела)
        """
        if not height or height <= 0:
            return 0.0

        height_m = height / 100
        bmi = weight / (height_m ** 2)
        return round(bmi, 1)

    @staticmethod
    def get_healthy_weight_range(height: int) -> tuple[float, float]:
        """
        Расчет диапазона здорового веса на основе роста и ИМТ
        Используется диапазон ИМТ 18.5-24.9 (нормальный вес по ВОЗ)

        Args:
            height: Рост в см

        Returns:
            Кортеж (минимальный_вес, максимальный_вес) в кг
        """
        if not height or height <= 0:
            return (0.0, 0.0)

        height_m = height / 100

        # ИМТ 18.5 - нижняя граница нормы
        min_weight = 18.5 * (height_m ** 2)

        # ИМТ 24.9 - верхняя граница нормы
        max_weight = 24.9 * (height_m ** 2)

        return (round(min_weight, 1), round(max_weight, 1))

    @staticmethod
    def get_bmi_category(bmi: float) -> str:
        """
        Определение категории ИМТ

        Args:
            bmi: Индекс массы тела

        Returns:
            Название категории
        """
        if bmi < 16:
            return "Выраженный дефицит массы тела"
        elif bmi < 18.5:
            return "Недостаточная масса тела"
        elif bmi < 25:
            return "Норма"
        elif bmi < 30:
            return "Избыточная масса тела (предожирение)"
        elif bmi < 35:
            return "Ожирение I степени"
        elif bmi < 40:
            return "Ожирение II степени"
        else:
            return "Ожирение III степени"
