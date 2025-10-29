"""
Модель для хранения исправлений распознавания еды
"""
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.session import Base


class FoodRecognitionCorrection(Base):
    """История исправлений распознавания еды по фото"""
    __tablename__ = "food_recognition_corrections"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Hash фото для поиска похожих
    photo_hash = Column(String, nullable=False, index=True)

    # Оригинальное распознавание от AI
    original_recognition = Column(JSON, nullable=False)

    # Скорректированные данные от пользователя
    corrected_data = Column(JSON, nullable=False)

    # Текстовое уточнение от пользователя
    user_clarification = Column(String, nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    times_used = Column(Integer, default=0)  # Сколько раз использовалась эта коррекция

    # Relationship
    user = relationship("User", back_populates="food_corrections")

    # Индексы для быстрого поиска
    __table_args__ = (
        Index('idx_user_photo_hash', 'user_id', 'photo_hash'),
    )

    def __repr__(self):
        return f"<FoodRecognitionCorrection(user_id={self.user_id}, photo_hash={self.photo_hash[:10]}...)>"
