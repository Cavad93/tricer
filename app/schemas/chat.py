"""
Pydantic схемы для AI-чата
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.models.chat import MessageRole


class ChatMessageBase(BaseModel):
    """Базовая схема сообщения"""
    role: MessageRole
    content: str = Field(..., min_length=1, max_length=5000)


class ChatMessageCreate(ChatMessageBase):
    """Схема для создания сообщения"""
    user_id: int


class ChatMessageResponse(ChatMessageBase):
    """Схема для ответа"""
    id: int
    user_id: int
    tokens_used: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """Запрос к AI-чату"""
    message: str = Field(..., min_length=1, max_length=5000)
    include_history: bool = True


class ChatResponse(BaseModel):
    """Ответ от AI-чата"""
    message: str
    tokens_used: Optional[int] = None
    remaining_messages: Optional[int] = None  # Для Free пользователей


class ChatHistoryResponse(BaseModel):
    """История чата"""
    messages: List[ChatMessageResponse]
    total: int
    has_more: bool


class UsageStatsResponse(BaseModel):
    """Статистика использования за день"""
    date: datetime
    photo_recognitions: int
    chat_messages: int
    photo_limit: int
    chat_limit: int
    is_premium: bool
    can_use_photo: bool
    can_use_chat: bool
