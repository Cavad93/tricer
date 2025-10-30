"""
Модели для планов питания
"""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
from app.db.session import Base


class PlanPeriod(str, enum.Enum):
    """Период плана питания"""
    DAY = "day"  # На день
    WEEK = "week"  # На неделю
    MONTH = "month"  # На месяц


class MealPlan(Base):
    """Модель плана питания"""
    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    # Период плана
    period_type = Column(SQLEnum(PlanPeriod), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    # Целевые показатели на день (усредненные)
    daily_calories = Column(Integer, nullable=True)
    daily_proteins = Column(Float, nullable=True)
    daily_fats = Column(Float, nullable=True)
    daily_carbs = Column(Float, nullable=True)

    # Параметры генерации
    budget_category = Column(String(20), nullable=True)  # economy/normal/premium
    diet_preferences = Column(JSONB, default=dict)  # Предпочтения при генерации

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)  # Активный план

    # Отношения
    days = relationship("MealPlanDay", back_populates="meal_plan", cascade="all, delete-orphan")
    shopping_lists = relationship("ShoppingList", back_populates="meal_plan", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MealPlan(id={self.id}, user_id={self.user_id}, period={self.period_type})>"


class MealPlanDay(Base):
    """Модель дня в плане питания"""
    __tablename__ = "meal_plan_days"

    id = Column(Integer, primary_key=True, index=True)
    meal_plan_id = Column(Integer, ForeignKey("meal_plans.id"), nullable=False)

    # День
    day_date = Column(Date, nullable=False)  # Конкретная дата
    day_number = Column(Integer, nullable=False)  # Порядковый номер дня в плане (1, 2, 3...)

    # Итоги дня
    total_calories = Column(Integer, nullable=True)
    total_proteins = Column(Float, nullable=True)
    total_fats = Column(Float, nullable=True)
    total_carbs = Column(Float, nullable=True)

    # Отношения
    meal_plan = relationship("MealPlan", back_populates="days")
    meals = relationship("PlannedMeal", back_populates="day", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MealPlanDay(id={self.id}, date={self.day_date}, day_num={self.day_number})>"


class PlannedMeal(Base):
    """Модель запланированного приема пищи"""
    __tablename__ = "planned_meals"

    id = Column(Integer, primary_key=True, index=True)
    meal_plan_day_id = Column(Integer, ForeignKey("meal_plan_days.id"), nullable=False)

    # Тип приема пищи
    meal_type = Column(String(20), nullable=False)  # breakfast/lunch/dinner/snack
    meal_order = Column(Integer, default=1)  # Порядок в дне

    # Название рецепта
    recipe_name = Column(String(255), nullable=False)

    # Ингредиенты
    ingredients = Column(JSONB, default=list)  # [{name, quantity, unit, calories, proteins, fats, carbs}]

    # КБЖУ блюда
    calories = Column(Integer, nullable=True)
    proteins = Column(Float, nullable=True)
    fats = Column(Float, nullable=True)
    carbs = Column(Float, nullable=True)

    # Инструкции
    cooking_instructions = Column(Text, nullable=True)  # Как готовить
    cooking_time_minutes = Column(Integer, nullable=True)  # Время приготовления

    # Порция
    serving_size = Column(String(100), nullable=True)  # Описание порции

    # Микронутриенты (JSON для гибкости)
    micronutrients = Column(JSONB, default=dict)  # Словарь с микронутриентами

    # Отношения
    day = relationship("MealPlanDay", back_populates="meals")

    def __repr__(self):
        return f"<PlannedMeal(id={self.id}, meal_type={self.meal_type}, recipe={self.recipe_name})>"
