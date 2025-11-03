"""
Состояния для FSM (Finite State Machine)
"""
from enum import IntEnum, auto


class OnboardingStates(IntEnum):
    """Состояния онбординга"""
    # Юридические согласия (152-ФЗ)
    MEDICAL_DISCLAIMER = auto()  # Показ дисклеймера о том, что бот не является медицинским сервисом
    PERSONAL_DATA_CONSENT = auto()  # Согласие на обработку персональных данных

    # Старый дисклеймер (для обратной совместимости)
    DISCLAIMER = auto()  # Показ дисклеймера

    # Базовая информация
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
    FOOD_EXCLUSIONS = auto()  # Продукты, которые категорически не хочет в рационе

    # Wellness информация (для подбора оптимального рациона)
    CHRONIC_CONDITIONS = auto()  # Хронические заболевания для учета в планировании питания
    REMOVED_ORGANS = auto()  # Удаленные органы для учета в планировании питания

    DIARY_CHECK_TIME = auto()  # Выбор времени проверки дневника
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
    WAITING_MANUAL_DISH_INPUT = auto()  # Ожидание ввода названия блюда вручную


class MealPlanStates(IntEnum):
    """Состояния создания плана питания"""
    WAITING_PERIOD = auto()  # Ожидание выбора периода (день/неделя/месяц)
    ASKING_START_TIMING = auto()  # Уточнение начала плана (сегодня/завтра)
    ASKING_BATCH_COOKING = auto()  # Вопрос о приготовлении с запасом (на 3-5 дней)
    ASKING_COOKING_TIME = auto()  # Уточнение времени на готовку
    ASKING_PREFERENCES = auto()  # Уточнение предпочтений перед созданием
    ASKING_PRICE_CALCULATION = auto()  # Вопрос о необходимости расчёта цены
    ASKING_SHOP_PREFERENCE = auto()  # Вопрос о предпочтениях по магазинам (один или несколько)
    GENERATING = auto()  # Генерация плана
    ASKING_FEEDBACK = auto()  # Запрос обратной связи после создания
    ASKING_CHANGES = auto()  # Сбор пожеланий по изменениям


class ProfileStates(IntEnum):
    """Состояния для управления профилем"""
    WAITING_NEW_WEIGHT = auto()  # Ожидание ввода нового веса


class PantryStates(IntEnum):
    """Состояния для управления продуктами дома"""
    WAITING_PRODUCTS_INPUT = auto()  # Ожидание ввода списка продуктов
    EDITING_PRODUCT_QUANTITY = auto()  # Редактирование количества продукта
    REVIEWING_FOR_PLAN = auto()  # Просмотр продуктов перед созданием плана


class ReminderSettingsStates(IntEnum):
    """Состояния для настройки напоминаний после создания плана"""
    WAITING_CUSTOM_TIME = auto()  # Ожидание ввода своего времени


class PrivacyStates(IntEnum):
    """Состояния для управления конфиденциальностью (152-ФЗ)"""
    CONFIRMING_DELETE = auto()  # Подтверждение удаления аккаунта
    EXPORTING_DATA = auto()  # Экспорт данных
    REVOKING_CONSENT = auto()  # Отзыв согласия
