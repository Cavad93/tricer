"""
Модель для временных рационов на день
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base
import json


class TemporaryMealPlan(Base):
    """Модель для хранения временных рационов на день (до 00:00)"""
    __tablename__ = "temporary_meal_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    meal_plan_data = Column(Text, nullable=False)  # JSON с рекомендациями
    total_calories = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False, index=True)  # Истекает в 00:00

    # Relationships
    user = relationship("User", backref="temporary_meal_plans")

    def __repr__(self):
        return f"<TemporaryMealPlan(user_id={self.user_id}, date={self.date})>"

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "meal_plan_data": self.get_meal_plan_data(),
            "total_calories": self.total_calories,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    def get_meal_plan_data(self):
        """Получить данные плана питания как dict"""
        try:
            return json.loads(self.meal_plan_data) if self.meal_plan_data else {}
        except json.JSONDecodeError:
            return {}

    def set_meal_plan_data(self, data: dict):
        """Установить данные плана питания из dict"""
        self.meal_plan_data = json.dumps(data, ensure_ascii=False)
