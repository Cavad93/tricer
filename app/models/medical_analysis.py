"""
Модель для хранения медицинских анализов пользователя
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from app.db.session import Base


class MedicalAnalysis(Base):
    """Медицинские анализы пользователя"""
    __tablename__ = "medical_analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Тип анализа
    analysis_type = Column(String(100), nullable=True)  # Тип анализа (ОАК, биохимия и т.д.)
    analysis_date = Column(DateTime, nullable=True)  # Дата сдачи анализа

    # Данные
    raw_data = Column(JSON, nullable=False)  # Сырые данные анализа (все показатели)
    file_url = Column(String(500), nullable=True)  # URL загруженного файла (если был)

    # AI-анализ
    ai_analysis = Column(JSON, nullable=True)  # Результат анализа от Claude AI
    detected_deficiencies = Column(JSON, default=list)  # Выявленные дефициты (витамины, минералы и т.д.)
    recommendations = Column(Text, nullable=True)  # Рекомендации от AI (без диагнозов!)
    needs_doctor_consultation = Column(Boolean, default=False)  # Флаг: нужна консультация врача

    # Заметки пользователя
    user_notes = Column(Text, nullable=True)  # Заметки пользователя к анализу

    # Метаданные
    created_at = Column(DateTime, default=func.now(), index=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", backref="medical_analyses")

    def __repr__(self):
        return f"<MedicalAnalysis(user_id={self.user_id}, type={self.analysis_type}, date={self.analysis_date})>"

    def to_dict(self):
        """Преобразование в словарь"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "analysis_type": self.analysis_type,
            "analysis_date": self.analysis_date.isoformat() if self.analysis_date else None,
            "detected_deficiencies": self.detected_deficiencies,
            "needs_doctor_consultation": self.needs_doctor_consultation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
