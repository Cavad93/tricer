"""
Модель для отслеживания использования API
"""
from sqlalchemy import Column, Integer, Date, ForeignKey, DateTime
from sqlalchemy.sql import func
from app.db.session import Base


class DailyUsage(Base):
    """Модель для отслеживания дневного использования API"""
    __tablename__ = "daily_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Дата использования
    usage_date = Column(Date, nullable=False, index=True)

    # Счетчики использования
    photo_recognitions = Column(Integer, default=0)  # Количество распознаваний фото
    chat_messages = Column(Integer, default=0)  # Количество сообщений в AI-чат

    # Метаданные
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<DailyUsage(user_id={self.user_id}, date={self.usage_date})>"

    def can_use_photo_recognition(self, is_premium: bool, limit: int) -> bool:
        """Проверка возможности использования распознавания фото"""
        if is_premium:
            return True
        return self.photo_recognitions < limit

    def can_use_chat(self, is_premium: bool, limit: int) -> bool:
        """Проверка возможности использования чата"""
        if is_premium:
            return True
        return self.chat_messages < limit

    def increment_photo_recognition(self):
        """Увеличить счетчик распознаваний фото"""
        self.photo_recognitions += 1

    def increment_chat_message(self):
        """Увеличить счетчик сообщений чата"""
        self.chat_messages += 1
