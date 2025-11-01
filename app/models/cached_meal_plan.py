"""
Модели для кэширования планов питания
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.db.session import Base


class CachedMealPlanStatus(str, enum.Enum):
    """Статус кэшированного плана"""
    ACTIVE = "active"  # Активный, используется
    OUTDATED = "outdated"  # Устарел, требует обновления
    ARCHIVED = "archived"  # Архивирован


class UserCategory(Base):
    """
    Категория пользователей по параметрам для кэширования планов питания.

    Пользователи с одинаковыми параметрами относятся к одной категории
    и могут использовать одни и те же шаблоны планов питания.
    """
    __tablename__ = "user_categories"

    id = Column(Integer, primary_key=True, index=True)

    # Хэш параметров для быстрого поиска категории
    # Формируется из: calories, proteins, fats, carbs, diet_type, budget_category, allergies (сортированный список)
    params_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Параметры категории (для сопоставления)
    target_calories = Column(Integer, nullable=False)
    target_proteins = Column(Integer, nullable=False)
    target_fats = Column(Integer, nullable=False)
    target_carbs = Column(Integer, nullable=False)

    diet_type = Column(String(20), nullable=False)  # omnivore/vegetarian/vegan/pescatarian
    budget_category = Column(String(20), nullable=False)  # economy/normal/premium

    # Аллергии (сортированный список для единообразия)
    allergies = Column(JSONB, default=list)

    # Статистика использования
    users_count = Column(Integer, default=0)  # Количество пользователей в категории
    last_used_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Отношения
    cached_plans = relationship("CachedMealPlan", back_populates="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserCategory(id={self.id}, hash={self.params_hash[:8]}..., users={self.users_count})>"


class CachedMealPlan(Base):
    """
    Кэшированный план питания для категории пользователей.

    Хранит готовые планы питания, которые генерируются заранее
    и могут использоваться пользователями из одной категории
    для экономии токенов AI.
    """
    __tablename__ = "cached_meal_plans"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("user_categories.id"), nullable=False, index=True)

    # Период плана
    period_type = Column(String(20), nullable=False)  # day/week/month

    # Данные плана (в формате JSON для гибкости)
    # Структура совпадает с форматом, который возвращает AI
    plan_data = Column(JSONB, nullable=False)

    # Статус плана
    status = Column(SQLEnum(CachedMealPlanStatus), default=CachedMealPlanStatus.ACTIVE, index=True)

    # Метаданные использования
    usage_count = Column(Integer, default=0)  # Сколько раз был использован
    last_used_at = Column(DateTime, nullable=True)  # Когда последний раз использовался

    # Оценка качества от пользователей
    positive_feedback_count = Column(Integer, default=0)
    negative_feedback_count = Column(Integer, default=0)

    # Временные метки
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Отношения
    category = relationship("UserCategory", back_populates="cached_plans")

    def __repr__(self):
        return f"<CachedMealPlan(id={self.id}, period={self.period_type}, usage={self.usage_count}, status={self.status.value})>"

    @property
    def feedback_ratio(self) -> float:
        """Отношение положительных отзывов к общему количеству"""
        total = self.positive_feedback_count + self.negative_feedback_count
        if total == 0:
            return 0.5  # Нейтральное значение если нет отзывов
        return self.positive_feedback_count / total


# Индексы для оптимизации запросов
Index('idx_cached_plans_category_period_status',
      CachedMealPlan.category_id,
      CachedMealPlan.period_type,
      CachedMealPlan.status)
