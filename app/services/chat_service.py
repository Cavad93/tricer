"""
Сервис для работы с историей AI-чата
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Dict
from datetime import datetime

from app.models.chat import ChatMessage, MessageRole
from app.models.user import User


class ChatService:
    """Сервис для управления историей чата"""

    @staticmethod
    async def save_message(
        session: AsyncSession,
        user_id: int,
        role: MessageRole,
        content: str,
        tokens_used: int = None
    ) -> ChatMessage:
        """
        Сохранить сообщение в историю

        Args:
            session: Сессия БД
            user_id: ID пользователя
            role: Роль отправителя (user/assistant)
            content: Содержимое сообщения
            tokens_used: Использовано токенов

        Returns:
            Созданное сообщение
        """
        message = ChatMessage(
            user_id=user_id,
            role=role,
            content=content,
            tokens_used=tokens_used
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)

        return message

    @staticmethod
    async def get_chat_history(
        session: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[ChatMessage]:
        """
        Получить историю чата пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя
            limit: Количество последних сообщений

        Returns:
            Список сообщений (от старых к новым)
        """
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        messages = result.scalars().all()

        # Возвращаем в правильном порядке (от старых к новым)
        return list(reversed(messages))

    @staticmethod
    async def get_chat_context(
        session: AsyncSession,
        user_id: int,
        message_limit: int = 10
    ) -> List[Dict]:
        """
        Получить контекст для отправки в Claude API

        Args:
            session: Сессия БД
            user_id: ID пользователя
            message_limit: Количество последних сообщений для контекста

        Returns:
            Список словарей формата {"role": "...", "content": "..."}
        """
        messages = await ChatService.get_chat_history(session, user_id, message_limit)

        return [msg.to_dict() for msg in messages]

    @staticmethod
    async def get_user_context(
        session: AsyncSession,
        user_id: int
    ) -> Dict:
        """
        Получить контекст пользователя для персонализации ответов

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Словарь с данными пользователя
        """
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {}

        return {
            "preferred_name": user.preferred_name or user.first_name or "друг",
            "age": user.age,
            "gender": user.gender.value if user.gender else None,
            "current_weight": user.current_weight,
            "target_weight": user.target_weight,
            "goal": user.goal.value if user.goal else None,
            "activity_level": user.activity_level.value if user.activity_level else None,
            "target_calories": user.target_calories,
            "target_proteins": user.target_proteins,
            "target_fats": user.target_fats,
            "target_carbs": user.target_carbs,
            "diet_type": user.diet_type.value if user.diet_type else None,
            "allergies": user.allergies or [],
            # Дневная статистика (пока заглушка, будет из дневника питания)
            "today_calories": 0,
            "today_proteins": 0,
            "today_fats": 0,
            "today_carbs": 0
        }

    @staticmethod
    async def clear_chat_history(
        session: AsyncSession,
        user_id: int
    ) -> int:
        """
        Очистить историю чата пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Количество удаленных сообщений
        """
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.user_id == user_id)
        )
        messages = result.scalars().all()
        count = len(messages)

        for message in messages:
            await session.delete(message)

        await session.commit()

        return count

    @staticmethod
    async def get_total_messages_count(
        session: AsyncSession,
        user_id: int
    ) -> int:
        """
        Получить общее количество сообщений пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Количество сообщений
        """
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.user_id == user_id)
        )
        messages = result.scalars().all()

        return len(messages)
