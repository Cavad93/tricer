"""
Модель для хранения согласия пользователя с дисклеймером
"""
from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text
from app.db.session import Base


class UserConsent(Base):
    """Согласие пользователя с условиями использования и дисклеймером"""

    __tablename__ = "user_consents"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)

    # Согласие с основным дисклеймером
    medical_disclaimer_accepted = Column(Boolean, default=False, nullable=False)
    medical_disclaimer_accepted_at = Column(DateTime, nullable=True)
    medical_disclaimer_version = Column(String(20), default="1.0", nullable=False)

    # Согласие на обработку медицинских данных без хранения
    medical_privacy_consent = Column(Boolean, default=False, nullable=False)
    medical_privacy_consent_at = Column(DateTime, nullable=True)
    medical_privacy_version = Column(String(20), default="1.0", nullable=False)

    # IP адрес и метаданные для юридических целей
    ip_address = Column(String(45), nullable=True)  # IPv6 поддержка
    user_agent = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<UserConsent(telegram_id={self.telegram_id}, accepted={self.medical_disclaimer_accepted})>"
