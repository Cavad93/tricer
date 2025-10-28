"""
Модель пользователя
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum as SQLEnum, JSON
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
    allergies = Column(JSON, default=list)  # Список аллергий
    dislikes = Column(JSON, default=list)  # Список нелюбимых продуктов
    budget_category = Column(SQLEnum(BudgetCategory), default=BudgetCategory.NORMAL)

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
