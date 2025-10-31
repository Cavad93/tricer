"""
Модели для хранения продуктов дома (кладовая/холодильник)
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.db.session import Base


class UserPantry(Base):
    """Модель для хранения продуктов дома у пользователя"""
    __tablename__ = "user_pantry"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    # Информация о продукте
    product_name = Column(String(255), nullable=False)  # Название продукта
    category = Column(String(100), nullable=True)  # Категория (овощи, мясо, крупы и т.д.)

    # Количество
    quantity = Column(Float, nullable=False)  # Количество
    unit = Column(String(50), nullable=False, default="г")  # Единица измерения (г, кг, шт, л, мл)

    # Оценочная калорийность и питательная ценность (на 100г)
    calories_per_100g = Column(Integer, nullable=True)
    proteins_per_100g = Column(Float, nullable=True)
    fats_per_100g = Column(Float, nullable=True)
    carbs_per_100g = Column(Float, nullable=True)

    # Отслеживание
    initial_quantity = Column(Float, nullable=True)  # Изначальное количество
    last_used_date = Column(DateTime, nullable=True)  # Когда последний раз использовался
    times_used = Column(Integer, default=0)  # Сколько раз использовался

    # Срок годности
    expiration_date = Column(DateTime, nullable=True)  # Срок годности (опционально)
    is_perishable = Column(Boolean, default=False)  # Скоропортящийся продукт

    # Метаданные
    added_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Источник добавления
    source = Column(String(50), nullable=True)  # manual, from_plan, from_shopping_list
    notes = Column(Text, nullable=True)  # Заметки пользователя

    def __repr__(self):
        return f"<UserPantry(user_id={self.user_id}, product={self.product_name}, qty={self.quantity}{self.unit})>"


class PantryUsageLog(Base):
    """Лог использования продуктов из кладовой"""
    __tablename__ = "pantry_usage_log"

    id = Column(Integer, primary_key=True, index=True)
    pantry_item_id = Column(Integer, ForeignKey("user_pantry.id"), nullable=False)

    # Связь с приемом пищи (если продукт был использован для блюда из рациона)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=True)
    planned_meal_id = Column(Integer, ForeignKey("planned_meals.id"), nullable=True)

    # Количество использованное
    quantity_used = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)

    # Тип использования
    usage_type = Column(String(50), nullable=False)  # from_plan, manual, estimated

    # Метаданные
    used_at = Column(DateTime, default=func.now())
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<PantryUsageLog(item_id={self.pantry_item_id}, qty={self.quantity_used}{self.unit})>"
