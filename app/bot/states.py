"""
Состояния для FSM (Finite State Machine)
"""
from enum import IntEnum, auto


class OnboardingStates(IntEnum):
    """Состояния онбординга"""
    DISCLAIMER = auto()  # Показ дисклеймера
    PREFERRED_NAME = auto()
    COUNTRY = auto()
    CITY = auto()
    GENDER = auto()
    BIRTH_YEAR = auto()
    HEIGHT = auto()
    CURRENT_WEIGHT = auto()
    TARGET_WEIGHT = auto()
    GOAL = auto()
    ACTIVITY_LEVEL = auto()
    DIET_TYPE = auto()
    BUDGET_CATEGORY = auto()
    ALLERGIES = auto()
    CALCULATING = auto()


class FoodAddStates(IntEnum):
    """Состояния добавления еды"""
    WAITING_MEAL_TYPE = auto()  # Ожидание выбора типа приема пищи


class MealPlanStates(IntEnum):
    """Состояния создания плана питания"""
    WAITING_PERIOD = auto()  # Ожидание выбора периода (день/неделя/месяц)
    ASKING_PREFERENCES = auto()  # Уточнение предпочтений перед созданием
    GENERATING = auto()  # Генерация плана
    ASKING_FEEDBACK = auto()  # Запрос обратной связи после создания
    ASKING_CHANGES = auto()  # Сбор пожеланий по изменениям
