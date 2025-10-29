"""
Модель для учета шагов пользователя
"""
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base


class UserSteps(Base):
    """Модель для хранения количества шагов пользователя"""
    __tablename__ = "user_steps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    steps = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", backref="steps_history")

    def __repr__(self):
        return f"<UserSteps(user_id={self.user_id}, date={self.date}, steps={self.steps})>"

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "steps": self.steps,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def activity_level(self) -> str:
        """Определение уровня активности на основе шагов"""
        if self.steps < 3000:
            return "minimal"  # Минимальная активность
        elif self.steps < 5000:
            return "low"  # Низкая активность
        elif self.steps < 8000:
            return "medium"  # Средняя активность
        elif self.steps < 12000:
            return "high"  # Высокая активность
        else:
            return "very_high"  # Очень высокая активность

    @property
    def bonus_calories(self) -> int:
        """
        Расчет бонусных калорий за дополнительную активность
        За каждые 1000 шагов сверх базовых 5000 добавляем ~50 ккал
        """
        base_steps = 5000
        if self.steps <= base_steps:
            return 0

        extra_steps = self.steps - base_steps
        # Примерно 0.05 ккал на шаг
        return int((extra_steps / 1000) * 50)
