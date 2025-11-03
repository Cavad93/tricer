"""
Модель пользователя
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
import enum
from app.db.session import Base


class Gender(str, enum.Enum):
    """Пол пользователя"""
    MALE = "male"
    FEMALE = "female"


class Goal(str, enum.Enum):
    """Цель пользователя"""
    WEIGHT_LOSS = "weight_loss"
    WEIGHT_GAIN = "weight_gain"
    MAINTENANCE = "maintenance"
    HEALTH = "health"


class ActivityLevel(str, enum.Enum):
    """Уровень активности"""
    MINIMAL = "minimal"  # Минимальная активность
    LOW = "low"  # Низкая (1-3 тренировки в неделю)
    MEDIUM = "medium"  # Средняя (3-5 тренировок)
    HIGH = "high"  # Высокая (5-7 тренировок)
    VERY_HIGH = "very_high"  # Очень высокая (2+ тренировки в день)


class DietType(str, enum.Enum):
    """Тип диеты"""
    OMNIVORE = "omnivore"  # Всеядный
    VEGETARIAN = "vegetarian"  # Вегетарианец
    VEGAN = "vegan"  # Веган
    PESCATARIAN = "pescatarian"  # Пескетарианец


class BudgetCategory(str, enum.Enum):
    """Бюджетная категория"""
    ECONOMY = "economy"  # Эконом
    NORMAL = "normal"  # Норм
    PREMIUM = "premium"  # Премиум


class SubscriptionType(str, enum.Enum):
    """Тип подписки"""
    FREE = "free"
    PREMIUM = "premium"


class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"

    # ID
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    language_code = Column(String(10), default="ru")

    # Зашифрованные персональные данные (152-ФЗ)
    username_encrypted = Column(String, nullable=True)  # Зашифрованный username
    first_name_encrypted = Column(String, nullable=True)  # Зашифрованное имя
    last_name_encrypted = Column(String, nullable=True)  # Зашифрованная фамилия
    preferred_name_encrypted = Column(String, nullable=True)  # Зашифрованное имя для обращения

    # Зашифрованная локация
    country_encrypted = Column(String, nullable=True)  # Зашифрованная страна
    city_encrypted = Column(String, nullable=True)  # Зашифрованный город

    # Профиль
    gender = Column(SQLEnum(Gender), nullable=True)

    # Зашифрованные данные профиля
    birth_year_encrypted = Column(String, nullable=True)  # Зашифрованный год рождения
    height_encrypted = Column(String, nullable=True)  # Зашифрованный рост
    current_weight_encrypted = Column(String, nullable=True)  # Зашифрованный текущий вес
    target_weight_encrypted = Column(String, nullable=True)  # Зашифрованный целевой вес
    goal = Column(SQLEnum(Goal), nullable=True)
    activity_level = Column(SQLEnum(ActivityLevel), nullable=True)

    # Целевые показатели (рассчитанные)
    target_calories = Column(Integer, nullable=True)
    target_proteins = Column(Integer, nullable=True)
    target_fats = Column(Integer, nullable=True)
    target_carbs = Column(Integer, nullable=True)

    # Предпочтения
    diet_type = Column(SQLEnum(DietType), default=DietType.OMNIVORE)
    dislikes = Column(JSONB, default=list)  # Список нелюбимых продуктов (просто не нравится)
    budget_category = Column(SQLEnum(BudgetCategory), default=BudgetCategory.NORMAL)
    preferred_cooking_time_minutes = Column(Integer, nullable=True)  # Предпочитаемое время на готовку в минутах

    # Зашифрованные персональные предпочтения
    food_exclusions_encrypted = Column(String, nullable=True)  # Зашифрованные исключения из рациона

    # Зашифрованные wellness данные (для подбора оптимального рациона, НЕ для диагностики)
    chronic_conditions_encrypted = Column(String, nullable=True)  # Зашифрованный список хронических заболеваний
    removed_organs_encrypted = Column(String, nullable=True)  # Зашифрованный список удаленных органов

    # Напоминания о приемах пищи
    reminders_enabled = Column(Boolean, default=True)  # Включены ли напоминания
    breakfast_reminder_time = Column(String, nullable=True)  # Время напоминания о завтраке (HH:MM)
    lunch_reminder_time = Column(String, nullable=True)  # Время напоминания об обеде (HH:MM)
    dinner_reminder_time = Column(String, nullable=True)  # Время напоминания об ужине (HH:MM)
    snack_reminder_time = Column(String, nullable=True)  # Время напоминания о перекусе (HH:MM, опционально)
    reminder_timezone = Column(String, default='UTC')  # Часовой пояс пользователя

    # Проверка дневника питания
    diary_check_enabled = Column(Boolean, default=True)  # Включена ли проверка дневника
    diary_check_time = Column(String, nullable=True)  # Время проверки дневника (HH:MM)

    # Подписка
    subscription_type = Column(SQLEnum(SubscriptionType), default=SubscriptionType.FREE)
    subscription_expires_at = Column(DateTime, nullable=True)
    trial_used = Column(Boolean, default=False)

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_active_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)

    # Онбординг
    onboarding_completed = Column(Boolean, default=False)

    # Relationships
    food_corrections = relationship("FoodRecognitionCorrection", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"

    # Свойства для автоматического шифрования/расшифрования персональных данных
    @property
    def username(self) -> Optional[str]:
        """Получить расшифрованный username"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_string(self.username_encrypted)

    @username.setter
    def username(self, value: Optional[str]):
        """Установить username (будет зашифрован)"""
        from app.services.encryption_service import EncryptionService
        self.username_encrypted = EncryptionService.encrypt_string(value)

    @property
    def first_name(self) -> Optional[str]:
        """Получить расшифрованное имя"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_string(self.first_name_encrypted)

    @first_name.setter
    def first_name(self, value: Optional[str]):
        """Установить имя (будет зашифровано)"""
        from app.services.encryption_service import EncryptionService
        self.first_name_encrypted = EncryptionService.encrypt_string(value)

    @property
    def last_name(self) -> Optional[str]:
        """Получить расшифрованную фамилию"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_string(self.last_name_encrypted)

    @last_name.setter
    def last_name(self, value: Optional[str]):
        """Установить фамилию (будет зашифрована)"""
        from app.services.encryption_service import EncryptionService
        self.last_name_encrypted = EncryptionService.encrypt_string(value)

    @property
    def preferred_name(self) -> Optional[str]:
        """Получить расшифрованное имя для обращения"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_string(self.preferred_name_encrypted)

    @preferred_name.setter
    def preferred_name(self, value: Optional[str]):
        """Установить имя для обращения (будет зашифровано)"""
        from app.services.encryption_service import EncryptionService
        self.preferred_name_encrypted = EncryptionService.encrypt_string(value)

    @property
    def country(self) -> Optional[str]:
        """Получить расшифрованную страну"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_string(self.country_encrypted)

    @country.setter
    def country(self, value: Optional[str]):
        """Установить страну (будет зашифрована)"""
        from app.services.encryption_service import EncryptionService
        self.country_encrypted = EncryptionService.encrypt_string(value)

    @property
    def city(self) -> Optional[str]:
        """Получить расшифрованный город"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_string(self.city_encrypted)

    @city.setter
    def city(self, value: Optional[str]):
        """Установить город (будет зашифрован)"""
        from app.services.encryption_service import EncryptionService
        self.city_encrypted = EncryptionService.encrypt_string(value)

    @property
    def birth_year(self) -> Optional[int]:
        """Получить расшифрованный год рождения"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_int(self.birth_year_encrypted)

    @birth_year.setter
    def birth_year(self, value: Optional[int]):
        """Установить год рождения (будет зашифрован)"""
        from app.services.encryption_service import EncryptionService
        self.birth_year_encrypted = EncryptionService.encrypt_int(value)

    @property
    def height(self) -> Optional[int]:
        """Получить расшифрованный рост"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_int(self.height_encrypted)

    @height.setter
    def height(self, value: Optional[int]):
        """Установить рост (будет зашифрован)"""
        from app.services.encryption_service import EncryptionService
        self.height_encrypted = EncryptionService.encrypt_int(value)

    @property
    def current_weight(self) -> Optional[float]:
        """Получить расшифрованный текущий вес"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_float(self.current_weight_encrypted)

    @current_weight.setter
    def current_weight(self, value: Optional[float]):
        """Установить текущий вес (будет зашифрован)"""
        from app.services.encryption_service import EncryptionService
        self.current_weight_encrypted = EncryptionService.encrypt_float(value)

    @property
    def target_weight(self) -> Optional[float]:
        """Получить расшифрованный целевой вес"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_float(self.target_weight_encrypted)

    @target_weight.setter
    def target_weight(self, value: Optional[float]):
        """Установить целевой вес (будет зашифрован)"""
        from app.services.encryption_service import EncryptionService
        self.target_weight_encrypted = EncryptionService.encrypt_float(value)

    @property
    def food_exclusions(self) -> Optional[list]:
        """Получить расшифрованные исключения из рациона"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_list(self.food_exclusions_encrypted) or []

    @food_exclusions.setter
    def food_exclusions(self, value: Optional[list]):
        """Установить исключения из рациона (будут зашифрованы)"""
        from app.services.encryption_service import EncryptionService
        self.food_exclusions_encrypted = EncryptionService.encrypt_list(value) if value else None

    @property
    def chronic_conditions(self) -> Optional[list]:
        """Получить расшифрованные хронические заболевания"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_list(self.chronic_conditions_encrypted) or []

    @chronic_conditions.setter
    def chronic_conditions(self, value: Optional[list]):
        """Установить хронические заболевания (будут зашифрованы)"""
        from app.services.encryption_service import EncryptionService
        self.chronic_conditions_encrypted = EncryptionService.encrypt_list(value) if value else None

    @property
    def removed_organs(self) -> Optional[list]:
        """Получить расшифрованные удаленные органы"""
        from app.services.encryption_service import EncryptionService
        return EncryptionService.decrypt_list(self.removed_organs_encrypted) or []

    @removed_organs.setter
    def removed_organs(self, value: Optional[list]):
        """Установить удаленные органы (будут зашифрованы)"""
        from app.services.encryption_service import EncryptionService
        self.removed_organs_encrypted = EncryptionService.encrypt_list(value) if value else None

    @property
    def age(self) -> int:
        """Возраст пользователя"""
        if self.birth_year:
            return datetime.now().year - self.birth_year
        return None

    @property
    def is_premium(self) -> bool:
        """Проверка premium подписки"""
        if self.subscription_type == SubscriptionType.PREMIUM:
            if self.subscription_expires_at:
                return self.subscription_expires_at > datetime.now()
        return False

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "country": self.country,
            "city": self.city,
            "gender": self.gender.value if self.gender else None,
            "age": self.age,
            "height": self.height,
            "current_weight": self.current_weight,
            "target_weight": self.target_weight,
            "goal": self.goal.value if self.goal else None,
            "activity_level": self.activity_level.value if self.activity_level else None,
            "target_calories": self.target_calories,
            "target_proteins": self.target_proteins,
            "target_fats": self.target_fats,
            "target_carbs": self.target_carbs,
            "diet_type": self.diet_type.value if self.diet_type else None,
            "budget_category": self.budget_category.value if self.budget_category else None,
            "subscription_type": self.subscription_type.value,
            "is_premium": self.is_premium,
            "onboarding_completed": self.onboarding_completed,
        }
