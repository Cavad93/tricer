"""
Модели для списка покупок
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class ShoppingList(Base):
    """Модель списка покупок"""
    __tablename__ = "shopping_lists"

    id = Column(Integer, primary_key=True, index=True)
    meal_plan_id = Column(Integer, ForeignKey("meal_plans.id"), nullable=False)

    # Стоимость
    total_cost = Column(Float, nullable=True)  # Общая стоимость
    currency = Column(String(10), default="RUB")  # Валюта

    # PDF файл
    pdf_filename = Column(String(255), nullable=True)  # Имя файла
    pdf_path = Column(String(500), nullable=True)  # Полный путь к файлу

    # Метаданные
    generated_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Отношения
    meal_plan = relationship("MealPlan", back_populates="shopping_lists")
    items = relationship("ShoppingItem", back_populates="shopping_list", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ShoppingList(id={self.id}, meal_plan_id={self.meal_plan_id}, total={self.total_cost})>"


class ShoppingItem(Base):
    """Модель элемента списка покупок"""
    __tablename__ = "shopping_items"

    id = Column(Integer, primary_key=True, index=True)
    shopping_list_id = Column(Integer, ForeignKey("shopping_lists.id"), nullable=False)

    # Категория продукта
    category = Column(String(100), nullable=True)  # Овощи, Фрукты, Мясо, Молочные, и т.д.

    # Продукт
    product_name = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False)  # Количество
    unit = Column(String(50), nullable=False)  # Единица измерения (г, кг, шт, л, мл)

    # Цена
    estimated_price = Column(Float, nullable=True)  # Примерная цена
    price_per_unit = Column(Float, nullable=True)  # Цена за единицу
    shop_name = Column(String(255), nullable=True)  # Название магазина
    shop_url = Column(Text, nullable=True)  # Ссылка на продукт

    # Примечания
    notes = Column(Text, nullable=True)  # Дополнительные заметки

    # Отношения
    shopping_list = relationship("ShoppingList", back_populates="items")

    def __repr__(self):
        return f"<ShoppingItem(id={self.id}, product={self.product_name}, qty={self.quantity}{self.unit})>"
