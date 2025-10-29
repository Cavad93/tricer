"""
Сервис для работы с коррекциями распознавания еды
"""
import hashlib
from typing import Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from loguru import logger

from app.models.food_correction import FoodRecognitionCorrection


class FoodCorrectionService:
    """Сервис для управления коррекциями распознавания еды"""

    @staticmethod
    def calculate_photo_hash(image_bytes: bytes) -> str:
        """
        Вычислить хеш фото для идентификации

        Args:
            image_bytes: Байты изображения

        Returns:
            SHA256 хеш в виде строки
        """
        return hashlib.sha256(image_bytes).hexdigest()

    @staticmethod
    async def find_correction_by_hash(
        session: AsyncSession,
        user_id: int,
        photo_hash: str
    ) -> Optional[FoodRecognitionCorrection]:
        """
        Найти существующую коррекцию для данного фото

        Args:
            session: Сессия БД
            user_id: ID пользователя
            photo_hash: Хеш фото

        Returns:
            FoodRecognitionCorrection или None
        """
        result = await session.execute(
            select(FoodRecognitionCorrection).where(
                FoodRecognitionCorrection.user_id == user_id,
                FoodRecognitionCorrection.photo_hash == photo_hash
            ).order_by(desc(FoodRecognitionCorrection.created_at)).limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def save_correction(
        session: AsyncSession,
        user_id: int,
        photo_hash: str,
        original_recognition: Dict,
        corrected_data: Dict,
        user_clarification: Optional[str] = None
    ) -> FoodRecognitionCorrection:
        """
        Сохранить коррекцию распознавания

        Args:
            session: Сессия БД
            user_id: ID пользователя
            photo_hash: Хеш фото
            original_recognition: Оригинальное распознавание от AI
            corrected_data: Скорректированные данные
            user_clarification: Текстовое уточнение от пользователя

        Returns:
            Созданная коррекция
        """
        correction = FoodRecognitionCorrection(
            user_id=user_id,
            photo_hash=photo_hash,
            original_recognition=original_recognition,
            corrected_data=corrected_data,
            user_clarification=user_clarification,
            times_used=0
        )

        session.add(correction)
        await session.commit()
        await session.refresh(correction)

        logger.info(f"Saved food correction for user {user_id}, photo_hash: {photo_hash[:10]}...")

        return correction

    @staticmethod
    async def increment_usage(
        session: AsyncSession,
        correction_id: int
    ):
        """
        Увеличить счетчик использования коррекции

        Args:
            session: Сессия БД
            correction_id: ID коррекции
        """
        result = await session.execute(
            select(FoodRecognitionCorrection).where(
                FoodRecognitionCorrection.id == correction_id
            )
        )
        correction = result.scalar_one_or_none()

        if correction:
            correction.times_used += 1
            await session.commit()
            logger.debug(f"Incremented usage for correction {correction_id}, now: {correction.times_used}")

    @staticmethod
    async def get_user_corrections_count(
        session: AsyncSession,
        user_id: int
    ) -> int:
        """
        Получить количество сохраненных коррекций пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Количество коррекций
        """
        result = await session.execute(
            select(FoodRecognitionCorrection).where(
                FoodRecognitionCorrection.user_id == user_id
            )
        )
        corrections = result.scalars().all()
        return len(corrections)
