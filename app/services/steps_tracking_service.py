"""
Сервис для работы с учетом шагов пользователя
"""
from datetime import datetime, date, timedelta
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.user_steps import UserSteps
from app.models.user import User


class StepsTrackingService:
    """Сервис для управления учетом шагов пользователя"""

    @staticmethod
    async def save_steps(
        user_id: int,
        steps: int,
        session: AsyncSession,
        steps_date: Optional[date] = None
    ) -> UserSteps:
        """
        Сохранить количество шагов пользователя за день

        Args:
            user_id: ID пользователя
            steps: Количество шагов
            session: Сессия БД
            steps_date: Дата записи (по умолчанию - сегодня)

        Returns:
            Созданная или обновленная запись UserSteps
        """
        try:
            steps_date = steps_date or date.today()

            # Проверяем, есть ли уже запись за эту дату
            result = await session.execute(
                select(UserSteps).where(
                    UserSteps.user_id == user_id,
                    UserSteps.date == steps_date
                )
            )
            existing_entry = result.scalar_one_or_none()

            if existing_entry:
                # Обновляем существующую запись
                existing_entry.steps = steps
                await session.commit()
                await session.refresh(existing_entry)
                logger.info(f"Updated steps for user {user_id} on {steps_date}: {steps} steps")
                return existing_entry
            else:
                # Создаем новую запись
                steps_entry = UserSteps(
                    user_id=user_id,
                    date=steps_date,
                    steps=steps
                )
                session.add(steps_entry)
                await session.commit()
                await session.refresh(steps_entry)
                logger.info(f"Saved steps for user {user_id} on {steps_date}: {steps} steps")
                return steps_entry

        except Exception as e:
            await session.rollback()
            logger.error("Error saving steps for user {user_id}: {}", repr(e))
            raise

    @staticmethod
    async def get_steps_for_date(
        user_id: int,
        session: AsyncSession,
        steps_date: Optional[date] = None
    ) -> Optional[UserSteps]:
        """
        Получить запись о шагах за конкретную дату

        Args:
            user_id: ID пользователя
            session: Сессия БД
            steps_date: Дата (по умолчанию - сегодня)

        Returns:
            Запись UserSteps или None
        """
        try:
            steps_date = steps_date or date.today()

            result = await session.execute(
                select(UserSteps).where(
                    UserSteps.user_id == user_id,
                    UserSteps.date == steps_date
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("Error getting steps for user {user_id} on {steps_date}: {}", repr(e))
            return None

    @staticmethod
    async def get_steps_history(
        user_id: int,
        session: AsyncSession,
        days: int = 7
    ) -> List[UserSteps]:
        """
        Получить историю шагов за последние N дней

        Args:
            user_id: ID пользователя
            session: Сессия БД
            days: Количество дней для выборки (по умолчанию 7)

        Returns:
            Список записей UserSteps
        """
        try:
            start_date = date.today() - timedelta(days=days)

            result = await session.execute(
                select(UserSteps)
                .where(
                    UserSteps.user_id == user_id,
                    UserSteps.date >= start_date
                )
                .order_by(desc(UserSteps.date))
            )
            return result.scalars().all()

        except Exception as e:
            logger.error("Error getting steps history for user {user_id}: {}", repr(e))
            return []

    @staticmethod
    async def get_average_steps(
        user_id: int,
        session: AsyncSession,
        days: int = 7
    ) -> int:
        """
        Получить среднее количество шагов за последние N дней

        Args:
            user_id: ID пользователя
            session: Сессия БД
            days: Количество дней для расчета (по умолчанию 7)

        Returns:
            Среднее количество шагов
        """
        try:
            history = await StepsTrackingService.get_steps_history(user_id, session, days)

            if not history:
                return 0

            total_steps = sum(entry.steps for entry in history)
            return int(total_steps / len(history))

        except Exception as e:
            logger.error("Error calculating average steps for user {user_id}: {}", repr(e))
            return 0

    @staticmethod
    async def calculate_bonus_calories(
        user_id: int,
        session: AsyncSession,
        steps_date: Optional[date] = None
    ) -> int:
        """
        Рассчитать бонусные калории на основе шагов за день

        Args:
            user_id: ID пользователя
            session: Сессия БД
            steps_date: Дата (по умолчанию - вчерашний день)

        Returns:
            Количество бонусных калорий
        """
        try:
            # По умолчанию берем вчерашний день (так как спрашиваем вечером)
            steps_date = steps_date or (date.today() - timedelta(days=1))

            steps_entry = await StepsTrackingService.get_steps_for_date(
                user_id, session, steps_date
            )

            if not steps_entry:
                return 0

            return steps_entry.bonus_calories

        except Exception as e:
            logger.error("Error calculating bonus calories for user {user_id}: {}", repr(e))
            return 0

    @staticmethod
    def get_activity_message(steps: int) -> str:
        """
        Получить сообщение об уровне активности на основе шагов

        Args:
            steps: Количество шагов

        Returns:
            Текстовое сообщение об активности
        """
        if steps < 3000:
            return "🔴 Низкая активность. Постарайся больше двигаться!"
        elif steps < 5000:
            return "🟡 Минимальная активность. Хороший старт!"
        elif steps < 8000:
            return "🟢 Средняя активность. Отличная работа!"
        elif steps < 12000:
            return "🔵 Высокая активность. Ты молодец!"
        else:
            return "🌟 Очень высокая активность! Превосходный результат!"
