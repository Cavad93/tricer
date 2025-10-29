"""
Модели для дневника питания
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, date
import enum
from app.db.session import Base


class MealType(str, enum.Enum):
    """Тип приема пищи"""
    BREAKFAST = "breakfast"  # Завтрак
    LUNCH = "lunch"  # Обед
    DINNER = "dinner"  # Ужин
    SNACK = "snack"  # Перекус


class Meal(Base):
    """Прием пищи"""
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    meal_date = Column(Date, nullable=False, index=True)  # Дата приема пищи
    meal_type = Column(SQLEnum(MealType), nullable=False)  # Тип приема пищи
    meal_time = Column(DateTime, nullable=False)  # Время приема пищи

    # Общие показатели приема пищи (сумма всех блюд)
    total_calories = Column(Integer, default=0)
    total_proteins = Column(Float, default=0)
    total_fats = Column(Float, default=0)
    total_carbs = Column(Float, default=0)

    # Метаданные
    notes = Column(String(500), nullable=True)  # Заметки пользователя
    photo_url = Column(String(500), nullable=True)  # URL фото (если есть)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    foods = relationship("MealFood", back_populates="meal", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Meal(id={self.id}, user_id={self.user_id}, type={self.meal_type}, date={self.meal_date})>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "meal_date": self.meal_date.isoformat() if self.meal_date else None,
            "meal_type": self.meal_type.value if self.meal_type else None,
            "meal_time": self.meal_time.isoformat() if self.meal_time else None,
            "total_calories": self.total_calories,
            "total_proteins": self.total_proteins,
            "total_fats": self.total_fats,
            "total_carbs": self.total_carbs,
            "notes": self.notes,
            "photo_url": self.photo_url,
            "foods": [food.to_dict() for food in self.foods] if self.foods else []
        }


class MealFood(Base):
    """Блюдо в приеме пищи"""
    __tablename__ = "meal_foods"

    id = Column(Integer, primary_key=True, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id", ondelete="CASCADE"), nullable=False, index=True)

    # Информация о блюде
    name = Column(String(200), nullable=False)  # Название блюда
    portion_size = Column(Float, nullable=False)  # Размер порции в граммах
    portion_description = Column(String(200), nullable=True)  # Описание порции (например, "1 средняя тарелка")

    # Пищевая ценность
    calories = Column(Integer, nullable=False)
    proteins = Column(Float, nullable=False)
    fats = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)

    # Дополнительные данные
    ingredients = Column(JSON, default=list)  # Список ингредиентов
    confidence_score = Column(Float, nullable=True)  # Уверенность AI в распознавании (0-1)

    # Микронутриенты (JSON для гибкости, содержит все витамины и минералы)
    micronutrients = Column(JSON, default=dict)  # Словарь с микронутриентами

    created_at = Column(DateTime, default=func.now())

    # Relationships
    meal = relationship("Meal", back_populates="foods")

    def __repr__(self):
        return f"<MealFood(id={self.id}, name={self.name}, portion={self.portion_size}g, calories={self.calories})>"

    def to_dict(self):
        return {
            "id": self.id,
            "meal_id": self.meal_id,
            "name": self.name,
            "portion_size": self.portion_size,
            "portion_description": self.portion_description,
            "calories": self.calories,
            "proteins": self.proteins,
            "fats": self.fats,
            "carbs": self.carbs,
            "ingredients": self.ingredients or [],
            "confidence_score": self.confidence_score,
            "micronutrients": self.micronutrients or {}
        }
