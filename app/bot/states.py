"""
Состояния для FSM (Finite State Machine)
"""
from enum import IntEnum, auto


class OnboardingStates(IntEnum):
    """Состояния онбординга"""
    PREFERRED_NAME = auto()
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
