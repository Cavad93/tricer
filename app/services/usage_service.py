"""
Сервис для управления использованием API и rate limiting
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date
from typing import Optional

from app.models.usage import DailyUsage
from app.models.user import User
from app.config import settings


class UsageService:
    """Сервис для отслеживания использования API"""

    @staticmethod
    async def get_or_create_daily_usage(
        session: AsyncSession,
        user_id: int,
        usage_date: date = None
    ) -> DailyUsage:
        """
        Получить или создать запись использования за день

        Args:
            session: Сессия БД
            user_id: ID пользователя
            usage_date: Дата использования (по умолчанию сегодня)

        Returns:
            DailyUsage объект
        """
        if usage_date is None:
            usage_date = date.today()

        # Ищем существующую запись
        result = await session.execute(
            select(DailyUsage).where(
                DailyUsage.user_id == user_id,
                DailyUsage.usage_date == usage_date
            )
        )
        daily_usage = result.scalar_one_or_none()

        # Если не найдена, создаем новую
        if not daily_usage:
            daily_usage = DailyUsage(
                user_id=user_id,
                usage_date=usage_date,
                photo_recognitions=0,
                chat_messages=0
            )
            session.add(daily_usage)
            await session.commit()
            await session.refresh(daily_usage)

        return daily_usage

    @staticmethod
    async def can_use_photo_recognition(
        session: AsyncSession,
        user_id: int
    ) -> tuple[bool, Optional[int]]:
        """
        Проверить возможность использования распознавания фото

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            (можно ли использовать, сколько осталось попыток или None для Premium)
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return False, 0

        # Premium пользователи имеют безлимит
        if user.is_premium:
            return True, None

        # Получаем дневную статистику
        daily_usage = await UsageService.get_or_create_daily_usage(session, user_id)

        limit = settings.FREE_PHOTO_LIMIT_PER_DAY
        remaining = limit - daily_usage.photo_recognitions

        return daily_usage.can_use_photo_recognition(False, limit), remaining

    @staticmethod
    async def can_use_chat(
        session: AsyncSession,
        user_id: int
    ) -> tuple[bool, Optional[int]]:
        """
        Проверить возможность использования AI-чата

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            (можно ли использовать, сколько осталось сообщений или None для Premium)
        """
        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return False, 0

        # Premium пользователи имеют безлимит
        if user.is_premium:
            return True, None

        # Получаем дневную статистику
        daily_usage = await UsageService.get_or_create_daily_usage(session, user_id)

        limit = settings.FREE_CHAT_LIMIT_PER_DAY
        remaining = limit - daily_usage.chat_messages

        return daily_usage.can_use_chat(False, limit), remaining

    @staticmethod
    async def increment_photo_usage(
        session: AsyncSession,
        user_id: int
    ) -> None:
        """
        Увеличить счетчик использования распознавания фото

        Args:
            session: Сессия БД
            user_id: ID пользователя
        """
        daily_usage = await UsageService.get_or_create_daily_usage(session, user_id)
        daily_usage.increment_photo_recognition()
        await session.commit()

    @staticmethod
    async def increment_chat_usage(
        session: AsyncSession,
        user_id: int
    ) -> None:
        """
        Увеличить счетчик использования AI-чата

        Args:
            session: Сессия БД
            user_id: ID пользователя
        """
        daily_usage = await UsageService.get_or_create_daily_usage(session, user_id)
        daily_usage.increment_chat_message()
        await session.commit()

    @staticmethod
    async def get_usage_stats(
        session: AsyncSession,
        user_id: int,
        usage_date: date = None
    ) -> dict:
        """
        Получить статистику использования

        Args:
            session: Сессия БД
            user_id: ID пользователя
            usage_date: Дата (по умолчанию сегодня)

        Returns:
            Словарь со статистикой
        """
        if usage_date is None:
            usage_date = date.today()

        # Получаем пользователя
        user_result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return None

        # Получаем дневную статистику
        daily_usage = await UsageService.get_or_create_daily_usage(session, user_id, usage_date)

        photo_limit = settings.FREE_PHOTO_LIMIT_PER_DAY
        chat_limit = settings.FREE_CHAT_LIMIT_PER_DAY

        return {
            "date": usage_date,
            "photo_recognitions": daily_usage.photo_recognitions,
            "chat_messages": daily_usage.chat_messages,
            "photo_limit": photo_limit if not user.is_premium else None,
            "chat_limit": chat_limit if not user.is_premium else None,
            "is_premium": user.is_premium,
            "can_use_photo": daily_usage.can_use_photo_recognition(user.is_premium, photo_limit),
            "can_use_chat": daily_usage.can_use_chat(user.is_premium, chat_limit)
        }
