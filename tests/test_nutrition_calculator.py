"""
Unit тесты для калькулятора питания
"""
import pytest
from app.services.nutrition_calc import NutritionCalculator


class TestNutritionCalculator:
    """Тесты калькулятора питания"""

    def test_calculate_bmr_male(self):
        """Тест расчета BMR для мужчины"""
        bmr = NutritionCalculator.calculate_bmr(
            gender='male',
            age=30,
            weight=80,
            height=180,
            activity_level='moderate'
        )

        # BMR для активного мужчины 30 лет, 80кг, 180см должен быть ~2400-2800
        assert 2000 < bmr < 3500, f"BMR {bmr} вне ожидаемого диапазона"

    def test_calculate_bmr_female(self):
        """Тест расчета BMR для женщины"""
        bmr = NutritionCalculator.calculate_bmr(
            gender='female',
            age=25,
            weight=60,
            height=165,
            activity_level='sedentary'
        )

        # BMR для малоактивной женщины должен быть меньше
        assert 1200 < bmr < 2200, f"BMR {bmr} вне ожидаемого диапазона"

    def test_calculate_bmi_normal(self):
        """Тест расчета нормального BMI"""
        bmi = NutritionCalculator.calculate_bmi(weight=70, height=175)
        category = NutritionCalculator.get_bmi_category(bmi)

        assert 22 < bmi < 23, f"BMI {bmi} неверно рассчитан"
        assert category == "Нормальный вес", f"Категория {category} неверна"

    def test_calculate_bmi_underweight(self):
        """Тест расчета недостаточного веса"""
        bmi = NutritionCalculator.calculate_bmi(weight=50, height=175)
        category = NutritionCalculator.get_bmi_category(bmi)

        assert bmi < 18.5, f"BMI {bmi} должен быть < 18.5"
        assert "Недостаточный" in category

    def test_calculate_bmi_overweight(self):
        """Тест расчета избыточного веса"""
        bmi = NutritionCalculator.calculate_bmi(weight=90, height=170)
        category = NutritionCalculator.get_bmi_category(bmi)

        assert 25 < bmi < 30, f"BMI {bmi} должен быть в диапазоне избыточного веса"
        assert "Избыточный" in category or "Предожирение" in category

    def test_calculate_bmi_obese(self):
        """Тест расчета ожирения"""
        bmi = NutritionCalculator.calculate_bmi(weight=110, height=170)
        category = NutritionCalculator.get_bmi_category(bmi)

        assert bmi > 30, f"BMI {bmi} должен быть > 30"
        assert "Ожирение" in category

    def test_calculate_macros_maintain(self):
        """Тест расчета макросов для поддержания веса"""
        macros = NutritionCalculator.calculate_macros(
            target_calories=2000,
            goal='maintain',
            age=30,
            gender='male'
        )

        # Проверяем наличие всех макросов
        assert 'proteins' in macros
        assert 'fats' in macros
        assert 'carbs' in macros

        # Проверяем сумму калорий (белки*4 + жиры*9 + углеводы*4)
        total_calories = (
            macros['proteins'] * 4 +
            macros['fats'] * 9 +
            macros['carbs'] * 4
        )

        # Допускаем погрешность ±50 ккал
        assert abs(total_calories - 2000) < 50, \
            f"Сумма калорий {total_calories} не соответствует целевым 2000"

    def test_calculate_macros_lose_weight(self):
        """Тест расчета макросов для похудения"""
        macros = NutritionCalculator.calculate_macros(
            target_calories=1800,
            goal='lose_weight',
            age=30,
            gender='female'
        )

        # При похудении белок должен быть повышен (30-35%)
        protein_calories = macros['proteins'] * 4
        protein_percentage = (protein_calories / 1800) * 100

        assert 25 < protein_percentage < 40, \
            f"Процент белка {protein_percentage:.1f}% не оптимален для похудения"

    def test_calculate_macros_gain_weight(self):
        """Тест расчета макросов для набора массы"""
        macros = NutritionCalculator.calculate_macros(
            target_calories=3000,
            goal='gain_weight',
            age=25,
            gender='male'
        )

        # При наборе массы углеводы должны быть повышены
        carb_calories = macros['carbs'] * 4
        carb_percentage = (carb_calories / 3000) * 100

        assert 40 < carb_percentage < 60, \
            f"Процент углеводов {carb_percentage:.1f}% не оптимален для набора массы"

    def test_bmr_activity_levels(self):
        """Тест влияния уровня активности на BMR"""
        base_params = {
            'gender': 'male',
            'age': 30,
            'weight': 80,
            'height': 180
        }

        bmr_sedentary = NutritionCalculator.calculate_bmr(
            **base_params,
            activity_level='sedentary'
        )

        bmr_very_active = NutritionCalculator.calculate_bmr(
            **base_params,
            activity_level='very_active'
        )

        # BMR при высокой активности должен быть значительно выше
        assert bmr_very_active > bmr_sedentary * 1.3, \
            "Уровень активности недостаточно влияет на BMR"

    def test_invalid_inputs(self):
        """Тест обработки некорректных входных данных"""
        # Негативный вес
        with pytest.raises((ValueError, AssertionError)):
            NutritionCalculator.calculate_bmi(weight=-70, height=175)

        # Нулевой рост
        with pytest.raises((ValueError, ZeroDivisionError, AssertionError)):
            NutritionCalculator.calculate_bmi(weight=70, height=0)

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

        macros_lose = NutritionCalculator.calculate_macros(
            target_calories=calories,
            goal='lose_weight',
            age=30,
            gender='male'
        )

        macros_maintain = NutritionCalculator.calculate_macros(
            target_calories=calories,
            goal='maintain',
            age=30,
            gender='male'
        )

        macros_gain = NutritionCalculator.calculate_macros(
            target_calories=calories,
            goal='gain_weight',
            age=30,
            gender='male'
        )

        # При похудении белка должно быть больше, чем при наборе массы
        assert macros_lose['proteins'] >= macros_maintain['proteins']

        # При наборе массы углеводов должно быть больше
        assert macros_gain['carbs'] >= macros_maintain['carbs']
