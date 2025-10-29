"""
Модель для отслеживания истории изменений веса
"""
from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.db.session import Base


class WeightHistory(Base):
    """История изменений веса пользователя"""
    __tablename__ = "weight_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Вес и дата измерения
    weight = Column(Float, nullable=False)  # Вес в кг
    measured_at = Column(DateTime, nullable=False, default=func.now(), index=True)

    # Опциональные заметки
    notes = Column(String(500), nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", backref="weight_history")

    def __repr__(self):
        return f"<WeightHistory(id={self.id}, user_id={self.user_id}, weight={self.weight}, measured_at={self.measured_at})>"

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "weight": self.weight,
            "measured_at": self.measured_at.isoformat() if self.measured_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def calculate_bmi(self, height_cm: int) -> float:
        """
        Вычисляет ИМТ (индекс массы тела) для данного веса
        ИМТ = вес(кг) / (рост(м))²
        """
        if not height_cm or height_cm <= 0:
            return 0.0

        height_m = height_cm / 100
        bmi = self.weight / (height_m ** 2)
        return round(bmi, 1)
