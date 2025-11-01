"""
Модель для хранения интересных фактов о корреляциях между едой и самочувствием
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.db.session import Base


class InsightFact(Base):
    """Интересный факт о корреляции между питанием и самочувствием"""
    __tablename__ = "insight_facts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Тип факта
    fact_type = Column(String(50), nullable=False, index=True)  # "food_wellness", "nutrient_wellness", etc.

    # Информация о продукте/блюде
    food_name = Column(String(200), nullable=True)  # Название продукта или категория
    food_category = Column(String(100), nullable=True)  # Категория еды

    # Метрика самочувствия
    wellness_metric = Column(String(100), nullable=False)  # energy_level, mood, digestive_comfort, etc.

    # Статистика корреляции
    correlation_coefficient = Column(Float, nullable=False)  # Коэффициент корреляции (-1 to 1)
    confidence_level = Column(Float, nullable=False)  # Уровень уверенности (0-1), например 0.95
    sample_size = Column(Integer, nullable=False)  # Количество наблюдений

    # Направление влияния
    impact_direction = Column(String(20), nullable=False)  # positive, negative, neutral
    average_impact = Column(Float, nullable=True)  # Средний эффект на метрику

    # Научное объяснение от AI
    scientific_explanation = Column(Text, nullable=True)  # Объяснение найденное AI
    explanation_sources = Column(JSONB, nullable=True)  # Источники из интернета

    # Детали корреляции
    details = Column(JSONB, nullable=True)  # Доп. информация: {
    #   "typical_portion": "100g",
    #   "typical_timing": "breakfast",
    #   "affected_symptoms": ["bloating", "fatigue"],
    #   "micronutrient_links": ["iron_deficiency", "vitamin_d"]
    # }

    # Статус проверки
    is_verified = Column(Boolean, default=False)  # Проверен ли AI
    is_active = Column(Boolean, default=True)  # Активен ли факт (можно деактивировать если стал неактуален)

    # Даты
    first_observed = Column(DateTime, nullable=False)  # Дата первого наблюдения паттерна
    first_detected = Column(DateTime, nullable=True)  # Alias для first_observed
    last_updated = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    last_validated = Column(DateTime, nullable=True)  # Когда факт был последний раз проверен на актуальность
    verified_at = Column(DateTime, nullable=True)  # Когда был проверен AI

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())  # Для совместимости

    # Relationships
    user = relationship("User", backref="insight_facts")

    def __repr__(self):
        return f"<InsightFact(id={self.id}, user_id={self.user_id}, food='{self.food_name}', metric='{self.wellness_metric}')>"

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "fact_type": self.fact_type,
            "food_name": self.food_name,
            "food_category": self.food_category,
            "wellness_metric": self.wellness_metric,
            "correlation_coefficient": self.correlation_coefficient,
            "confidence_level": self.confidence_level,
            "sample_size": self.sample_size,
            "impact_direction": self.impact_direction,
            "average_impact": self.average_impact,
            "scientific_explanation": self.scientific_explanation,
            "explanation_sources": self.explanation_sources,
            "details": self.details,
            "is_verified": self.is_verified,
            "is_active": self.is_active,
            "first_observed": self.first_observed.isoformat() if self.first_observed else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def get_user_friendly_text(self) -> str:
        """
        Возвращает текст факта в понятном для пользователя виде
        """
        # Названия метрик на русском
        metric_names = {
            "energy_level": "энергия",
            "mood": "настроение",
            "digestive_comfort": "комфорт пищеварения",
            "mental_clarity": "ясность ума",
            "sleep_quality": "качество сна",
            "stress_level": "уровень стресса"
        }

        metric_display = metric_names.get(self.wellness_metric, self.wellness_metric)

        # Формируем заголовок
        if self.impact_direction == "positive":
            emoji = "✅"
            effect = "улучшает"
        elif self.impact_direction == "negative":
            emoji = "⚠️"
            effect = "ухудшает"
        else:
            emoji = "ℹ️"
            effect = "влияет на"

        text = f"{emoji} <b>{self.food_name}</b> {effect} {metric_display}\n\n"

        # Добавляем статистику
        confidence_percent = int(self.confidence_level * 100)
        text += f"📊 Обнаружено: {self.sample_size} случаев употребления\n"
        text += f"🎯 Достоверность: {confidence_percent}%\n"

        if self.average_impact:
            impact_str = f"+{self.average_impact:.1f}" if self.average_impact > 0 else f"{self.average_impact:.1f}"
            text += f"📈 Средний эффект: {impact_str} баллов\n"

        # Добавляем научное объяснение
        if self.scientific_explanation:
            text += f"\n💡 <b>Научное объяснение:</b>\n{self.scientific_explanation}\n"

        return text
