"""
Модель для отслеживания самочувствия и корреляции с питанием
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.db.session import Base


class WellnessLog(Base):
    """Запись о самочувствии пользователя"""
    __tablename__ = "wellness_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id", ondelete="SET NULL"), nullable=True, index=True)

    # Время записи
    log_datetime = Column(DateTime, nullable=False, default=func.now(), index=True)

    # Сон (часов за предыдущую ночь)
    sleep_hours = Column(Float, nullable=True)  # Часы сна (может быть дробным, например 7.5)
    sleep_quality = Column(Integer, nullable=True)  # Качество сна 1-10

    # Показатели самочувствия (шкала 1-10)
    energy_level = Column(Integer, nullable=True)  # Уровень энергии
    mood = Column(Integer, nullable=True)  # Настроение
    digestive_comfort = Column(Integer, nullable=True)  # Комфорт пищеварения
    mental_clarity = Column(Integer, nullable=True)  # Ясность ума/концентрация
    hunger_level = Column(Integer, nullable=True)  # Уровень голода/сытости
    stress_level = Column(Integer, nullable=True)  # Уровень стресса

    # Физические симптомы (JSON массив)
    # Примеры: ["вздутие", "усталость", "головная боль", "тяжесть в желудке", "изжога"]
    physical_symptoms = Column(JSONB, default=list)

    # Заметки пользователя
    notes = Column(Text, nullable=True)

    # Контекст питания (если связано с приемом пищи)
    time_after_meal_minutes = Column(Integer, nullable=True)  # Сколько минут прошло после еды

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="wellness_logs")
    meal = relationship("Meal", backref="wellness_logs")

    def __repr__(self):
        return f"<WellnessLog(id={self.id}, user_id={self.user_id}, datetime={self.log_datetime})>"

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "meal_id": self.meal_id,
            "log_datetime": self.log_datetime.isoformat() if self.log_datetime else None,
            "sleep_hours": self.sleep_hours,
            "sleep_quality": self.sleep_quality,
            "energy_level": self.energy_level,
            "mood": self.mood,
            "digestive_comfort": self.digestive_comfort,
            "mental_clarity": self.mental_clarity,
            "hunger_level": self.hunger_level,
            "stress_level": self.stress_level,
            "physical_symptoms": self.physical_symptoms or [],
            "notes": self.notes,
            "time_after_meal_minutes": self.time_after_meal_minutes,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def get_wellness_score(self) -> float:
        """
        Вычисляет общий балл самочувствия (0-10)
        Усредняет все доступные показатели
        """
        scores = []

        # Положительные показатели (как есть)
        if self.energy_level is not None:
            scores.append(self.energy_level)
        if self.mood is not None:
            scores.append(self.mood)
        if self.digestive_comfort is not None:
            scores.append(self.digestive_comfort)
        if self.mental_clarity is not None:
            scores.append(self.mental_clarity)
        if self.sleep_quality is not None:
            scores.append(self.sleep_quality)

        # Отрицательные показатели (инвертируем)
        if self.stress_level is not None:
            scores.append(10 - self.stress_level)

        # Голод (оптимум - середина, 5-6 баллов)
        if self.hunger_level is not None:
            # Чем дальше от 5.5, тем хуже
            hunger_score = 10 - abs(self.hunger_level - 5.5) * 2
            scores.append(max(0, hunger_score))

        if not scores:
            return 0.0

        return round(sum(scores) / len(scores), 1)
