"""
Модель для хранения истории AI-чата
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from app.db.session import Base


class MessageRole(str, enum.Enum):
    """Роль отправителя сообщения"""
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(Base):
    """Модель сообщения в AI-чате"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Роль и содержимое
    role = Column(SQLEnum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)

    # Токены (для отслеживания использования API)
    tokens_used = Column(Integer, nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=func.now(), index=True)

    def __repr__(self):
        return f"<ChatMessage(user_id={self.user_id}, role={self.role.value})>"

    def to_dict(self):
        """Преобразование в словарь для Claude API"""
        return {
            "role": self.role.value,
            "content": self.content
        }
