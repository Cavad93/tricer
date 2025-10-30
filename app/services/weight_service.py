"""
Сервис для работы с историей изменений веса пользователя
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.weight_history import WeightHistory
from app.models.user import User
from loguru import logger


class WeightService:
    """Сервис для управления историей веса пользователя"""

    @staticmethod
    async def add_weight_entry(
        user_id: int,
        weight: float,
        session: AsyncSession,
        notes: Optional[str] = None,
        measured_at: Optional[datetime] = None
    ) -> WeightHistory:
        """
        Добавить запись о весе в историю

        Args:
            user_id: ID пользователя
            weight: Вес в кг
            session: Сессия БД
            notes: Опциональные заметки
            measured_at: Дата измерения (по умолчанию - текущее время)

        Returns:
            Созданная запись WeightHistory
        """
        try:
            weight_entry = WeightHistory(
                user_id=user_id,
                weight=weight,
                measured_at=measured_at or datetime.utcnow(),
                notes=notes
            )

            session.add(weight_entry)
            await session.commit()
            await session.refresh(weight_entry)

            logger.info(f"Weight entry added for user {user_id}: {weight} kg")
            return weight_entry

        except Exception as e:
            await session.rollback()
            logger.error("Error adding weight entry for user {user_id}: %s", str(e))
            raise

    @staticmethod
    async def update_user_current_weight(
        user: User,
        new_weight: float,
        session: AsyncSession
    ) -> User:
        """
        Обновить текущий вес пользователя в профиле

        Args:
            user: Объект пользователя
            new_weight: Новый вес в кг
            session: Сессия БД

        Returns:
            Обновленный объект пользователя
        """
        try:
            user.current_weight = new_weight
            user.updated_at = datetime.utcnow()

            await session.commit()
            await session.refresh(user)

            logger.info(f"User {user.id} weight updated to {new_weight} kg")
            return user

        except Exception as e:
            await session.rollback()
            logger.error("Error updating user {user.id} weight: %s", str(e))
            raise

    @staticmethod
    async def get_weight_history(
        user_id: int,
        session: AsyncSession,
        limit: int = 30
    ) -> List[WeightHistory]:
        """
        Получить историю изменений веса пользователя

        Args:
            user_id: ID пользователя
            session: Сессия БД
            limit: Максимальное количество записей (по умолчанию 30)

        Returns:
            Список записей WeightHistory, отсортированный по дате (новые первыми)
        """
        try:
            result = await session.execute(
                select(WeightHistory)
                .where(WeightHistory.user_id == user_id)
                .order_by(desc(WeightHistory.measured_at))
                .limit(limit)
            )

            weight_history = result.scalars().all()
            return list(weight_history)

        except Exception as e:
            logger.error("Error getting weight history for user {user_id}: %s", str(e))
            raise

    @staticmethod
    async def get_latest_weight_entry(
        user_id: int,
        session: AsyncSession
    ) -> Optional[WeightHistory]:
        """
        Получить последнюю запись о весе

        Args:
            user_id: ID пользователя
            session: Сессия БД

        Returns:
            Последняя запись WeightHistory или None
        """
        try:
            result = await session.execute(
                select(WeightHistory)
                .where(WeightHistory.user_id == user_id)
                .order_by(desc(WeightHistory.measured_at))
                .limit(1)
            )

            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("Error getting latest weight entry for user {user_id}: %s", str(e))
            raise

    @staticmethod
    def calculate_weight_change(
        history: List[WeightHistory]
    ) -> Optional[float]:
        """
        Рассчитать изменение веса между первой и последней записью

        Args:
            history: Список записей истории веса (должен быть отсортирован)

        Returns:
            Изменение веса в кг (положительное = набор, отрицательное = потеря) или None
        """
        if not history or len(history) < 2:
            return None

        # История отсортирована от новых к старым
        latest_weight = history[0].weight
        oldest_weight = history[-1].weight

        return round(latest_weight - oldest_weight, 1)
