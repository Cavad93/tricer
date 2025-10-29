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
    # Медицинская информация (Этап 4)
    CHRONIC_CONDITIONS = auto()  # Хронические заболевания
    REMOVED_ORGANS = auto()  # Удаленные органы
    CALCULATING = auto()


class FoodAddStates(IntEnum):
    """Состояния добавления еды"""
    ASKING_INTENTION = auto()  # Спрашиваем: будет есть или просто узнать
    ASKING_VERIFICATION = auto()  # Спрашиваем: распознано верно?
    ASKING_CLARIFICATION = auto()  # Запрашиваем текстовое уточнение
    WAITING_MEAL_TYPE = auto()  # Ожидание выбора типа приема пищи


class RestaurantStates(IntEnum):
    """Состояния для функции 'Ресторан'"""
    ASKING_MOOD = auto()  # Спрашиваем настроение/желание
    ASKING_MEAL_TIME = auto()  # Спрашиваем прием пищи
    ANALYZING_MENU = auto()  # Анализируем меню


class MealPlanStates(IntEnum):
    """Состояния создания плана питания"""
    WAITING_PERIOD = auto()  # Ожидание выбора периода (день/неделя/месяц)
    ASKING_COOKING_TIME = auto()  # Уточнение времени на готовку
    ASKING_PREFERENCES = auto()  # Уточнение предпочтений перед созданием
    GENERATING = auto()  # Генерация плана
    ASKING_FEEDBACK = auto()  # Запрос обратной связи после создания
    ASKING_CHANGES = auto()  # Сбор пожеланий по изменениям


class MedicalAnalysisStates(IntEnum):
    """Состояния для загрузки и анализа медицинских анализов (Этап 4)"""
    ASKING_TO_UPLOAD = auto()  # Предлагаем загрузить анализы
    WAITING_FILE = auto()  # Ожидание файла с анализами
    WAITING_TEXT_INPUT = auto()  # Ожидание текстового ввода показателей
    ANALYZING = auto()  # Анализ данных с помощью AI
    SHOWING_RESULTS = auto()  # Показ результатов анализа
