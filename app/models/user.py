"""
Модель пользователя
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum as SQLEnum, LargeBinary
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from datetime import datetime
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
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    language_code = Column(String(10), default="ru")
    preferred_name = Column(String(50), nullable=True)  # Имя для обращения

    # Локация (для подбора цен)
    country = Column(String(100), nullable=True)  # Страна
    city = Column(String(100), nullable=True)  # Город

    # Профиль
    gender = Column(SQLEnum(Gender), nullable=True)
    birth_year = Column(Integer, nullable=True)  # Год рождения
    height = Column(Integer, nullable=True)  # Рост в см
    current_weight = Column(Float, nullable=True)  # Текущий вес в кг
    target_weight = Column(Float, nullable=True)  # Целевой вес в кг
    goal = Column(SQLEnum(Goal), nullable=True)
    activity_level = Column(SQLEnum(ActivityLevel), nullable=True)

    # Целевые показатели (рассчитанные)
    target_calories = Column(Integer, nullable=True)
    target_proteins = Column(Integer, nullable=True)
    target_fats = Column(Integer, nullable=True)
    target_carbs = Column(Integer, nullable=True)

    # Предпочтения
    diet_type = Column(SQLEnum(DietType), default=DietType.OMNIVORE)
    allergies = Column(JSONB, default=list)  # Список аллергий
    dislikes = Column(JSONB, default=list)  # Список нелюбимых продуктов
    budget_category = Column(SQLEnum(BudgetCategory), default=BudgetCategory.NORMAL)
    preferred_cooking_time_minutes = Column(Integer, nullable=True)  # Предпочитаемое время на готовку в минутах

    # Медицинская информация (Этап 4)
    # ВАЖНО: Эти поля оставлены для обратной совместимости и миграции
    # Используйте зашифрованные версии ниже для новых данных
    chronic_conditions = Column(JSONB, default=list)  # Список хронических заболеваний
    removed_organs = Column(JSONB, default=list)  # Список удаленных органов
    medical_restrictions = Column(JSONB, default=dict)  # Медицинские ограничения по питанию (генерируется AI)
    medical_notes = Column(String(1000), nullable=True)  # Дополнительные медицинские заметки

    # Зашифрованные медицинские поля (152-ФЗ) - добавлены для защиты данных
    _chronic_conditions_encrypted = Column(LargeBinary, nullable=True)
    _removed_organs_encrypted = Column(LargeBinary, nullable=True)
    _medical_restrictions_encrypted = Column(LargeBinary, nullable=True)

    # Hybrid properties для работы с шифрованными данными
    @hybrid_property
    def chronic_conditions_encrypted(self):
        """Получает расшифрованный список хронических заболеваний"""
        if self._chronic_conditions_encrypted:
            from app.services.encryption_service import get_encryption_service
            encryption = get_encryption_service()
            return encryption.decrypt_list(self._chronic_conditions_encrypted)
        # Для обратной совместимости возвращаем незашифрованное поле
        return self.chronic_conditions

    @chronic_conditions_encrypted.setter
    def chronic_conditions_encrypted(self, value):
        """Шифрует и сохраняет список хронических заболеваний"""
        if value is None:
            self._chronic_conditions_encrypted = None
        else:
            from app.services.encryption_service import get_encryption_service
            encryption = get_encryption_service()
            self._chronic_conditions_encrypted = encryption.encrypt_list(value)

    @hybrid_property
    def removed_organs_encrypted(self):
        """Получает расшифрованный список удаленных органов"""
        if self._removed_organs_encrypted:
            from app.services.encryption_service import get_encryption_service
            encryption = get_encryption_service()
            return encryption.decrypt_list(self._removed_organs_encrypted)
        # Для обратной совместимости
        return self.removed_organs

    @removed_organs_encrypted.setter
    def removed_organs_encrypted(self, value):
        """Шифрует и сохраняет список удаленных органов"""
        if value is None:
            self._removed_organs_encrypted = None
        else:
            from app.services.encryption_service import get_encryption_service
            encryption = get_encryption_service()
            self._removed_organs_encrypted = encryption.encrypt_list(value)

    @hybrid_property
    def medical_restrictions_encrypted(self):
        """Получает расшифрованные медицинские ограничения"""
        if self._medical_restrictions_encrypted:
            from app.services.encryption_service import get_encryption_service
            encryption = get_encryption_service()
            return encryption.decrypt_dict(self._medical_restrictions_encrypted)
        # Для обратной совместимости
        return self.medical_restrictions

    @medical_restrictions_encrypted.setter
    def medical_restrictions_encrypted(self, value):
        """Шифрует и сохраняет медицинские ограничения"""
        if value is None:
            self._medical_restrictions_encrypted = None
        else:
            from app.services.encryption_service import get_encryption_service
            encryption = get_encryption_service()
            self._medical_restrictions_encrypted = encryption.encrypt_dict(value)

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
