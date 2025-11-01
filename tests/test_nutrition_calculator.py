"""
Unit тесты для калькулятора питания
"""
import pytest
from app.services.nutrition_calc import NutritionCalculator
from app.models.user import Gender, Goal, ActivityLevel


class TestNutritionCalculator:
    """Тесты калькулятора питания"""

    def test_calculate_bmr_male(self):
        """Тест расчета BMR для мужчины"""
        bmr = NutritionCalculator.calculate_bmr(
            gender=Gender.MALE,
            age=30,
            weight=80,
            height=180
        )

        # BMR для мужчины 30 лет, 80кг, 180см должен быть ~1700-1900
        assert 1600 < bmr < 2000, f"BMR {bmr} вне ожидаемого диапазона"

    def test_calculate_bmr_female(self):
        """Тест расчета BMR для женщины"""
        bmr = NutritionCalculator.calculate_bmr(
            gender=Gender.FEMALE,
            age=25,
            weight=60,
            height=165
        )

        # BMR для женщины должен быть меньше
        assert 1200 < bmr < 1600, f"BMR {bmr} вне ожидаемого диапазона"

    def test_calculate_bmi_normal(self):
        """Тест расчета нормального BMI"""
        bmi = NutritionCalculator.calculate_bmi(weight=70, height=175)
        category = NutritionCalculator.get_bmi_category(bmi)

        assert 22 < bmi < 23, f"BMI {bmi} неверно рассчитан"
        assert category == "Норма", f"Категория '{category}' неверна"

    def test_calculate_bmi_underweight(self):
        """Тест расчета недостаточного веса"""
        bmi = NutritionCalculator.calculate_bmi(weight=50, height=175)
        category = NutritionCalculator.get_bmi_category(bmi)

        assert bmi < 18.5, f"BMI {bmi} должен быть < 18.5"
        assert "Недостаточная масса тела" == category

    def test_calculate_bmi_overweight(self):
        """Тест расчета избыточного веса"""
        bmi = NutritionCalculator.calculate_bmi(weight=90, height=170)
        category = NutritionCalculator.get_bmi_category(bmi)

        assert 25 < bmi < 35, f"BMI {bmi} должен быть в диапазоне избыточного веса"
        assert "Избыточная масса тела" in category or "Ожирение" in category

    def test_calculate_bmi_obese(self):
        """Тест расчета ожирения"""
        bmi = NutritionCalculator.calculate_bmi(weight=110, height=170)
        category = NutritionCalculator.get_bmi_category(bmi)

        assert bmi > 30, f"BMI {bmi} должен быть > 30"
        assert "Ожирение" in category

    def test_calculate_macros_maintain(self):
        """Тест расчета макросов для поддержания веса"""
        proteins, fats, carbs = NutritionCalculator.calculate_macros(
            target_calories=2000,
            goal=Goal.MAINTENANCE,
            weight=70
        )

        # Проверяем что все значения положительные
        assert proteins > 0
        assert fats > 0
        assert carbs > 0

        # Проверяем сумму калорий (белки*4 + жиры*9 + углеводы*4)
        total_calories = proteins * 4 + fats * 9 + carbs * 4

        # Допускаем погрешность ±100 ккал
        assert abs(total_calories - 2000) < 100, \
            f"Сумма калорий {total_calories} не соответствует целевым 2000"

    def test_calculate_macros_lose_weight(self):
        """Тест расчета макросов для похудения"""
        proteins, fats, carbs = NutritionCalculator.calculate_macros(
            target_calories=1800,
            goal=Goal.WEIGHT_LOSS,
            weight=70
        )

        # При похудении белок должен быть повышен (около 2г на кг веса)
        assert proteins >= 100, f"Белка {proteins}г недостаточно для похудения"

        # Все макросы должны быть положительными
        assert fats > 0
        assert carbs > 0

    def test_calculate_macros_gain_weight(self):
        """Тест расчета макросов для набора массы"""
        proteins, fats, carbs = NutritionCalculator.calculate_macros(
            target_calories=3000,
            goal=Goal.WEIGHT_GAIN,
            weight=80
        )

        # При наборе массы белок также должен быть высоким
        assert proteins >= 120, f"Белка {proteins}г недостаточно для набора массы"

        # Углеводы должны составлять значительную часть
        assert carbs > 200, f"Углеводов {carbs}г недостаточно для набора массы"

    def test_bmr_activity_levels(self):
        """Тест влияния уровня активности на TDEE"""
        base_params = {
            'gender': Gender.MALE,
            'age': 30,
            'weight': 80,
            'height': 180
        }

        tdee_minimal = NutritionCalculator.calculate_tdee(
            **base_params,
            activity_level=ActivityLevel.MINIMAL
        )

        tdee_very_high = NutritionCalculator.calculate_tdee(
            **base_params,
            activity_level=ActivityLevel.VERY_HIGH
        )

        # TDEE при высокой активности должен быть значительно выше
        assert tdee_very_high > tdee_minimal * 1.3, \
            f"TDEE при высокой активности ({tdee_very_high}) должен быть выше чем при минимальной ({tdee_minimal})"

    def test_invalid_inputs(self):
        """Тест обработки некорректных входных данных"""
        # Нулевой рост
        bmi = NutritionCalculator.calculate_bmi(weight=70, height=0)
        assert bmi == 0.0, "BMI для нулевого роста должен быть 0"

        # Негативный рост
        bmi = NutritionCalculator.calculate_bmi(weight=70, height=-175)
        assert bmi == 0.0, "BMI для негативного роста должен быть 0"

    def test_edge_cases(self):
        """Тест граничных значений"""
        # Минимальные разумные значения
        bmi_min = NutritionCalculator.calculate_bmi(weight=40, height=150)
        assert 10 < bmi_min < 30

        # Максимальные разумные значения
        bmi_max = NutritionCalculator.calculate_bmi(weight=200, height=200)
        assert 30 < bmi_max < 70

    def test_macros_consistency(self):
        """Тест согласованности расчета макросов для разных целей"""
        calories = 2000
        weight = 70

        proteins_loss, fats_loss, carbs_loss = NutritionCalculator.calculate_macros(
            target_calories=calories,
            goal=Goal.WEIGHT_LOSS,
            weight=weight
        )

        proteins_maintain, fats_maintain, carbs_maintain = NutritionCalculator.calculate_macros(
            target_calories=calories,
            goal=Goal.MAINTENANCE,
            weight=weight
        )

        proteins_gain, fats_gain, carbs_gain = NutritionCalculator.calculate_macros(
            target_calories=calories,
            goal=Goal.WEIGHT_GAIN,
            weight=weight
        )

        # При похудении и наборе белка должно быть больше, чем при поддержании
        assert proteins_loss >= proteins_maintain
        assert proteins_gain >= proteins_maintain
