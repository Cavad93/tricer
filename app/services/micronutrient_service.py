"""
Сервис для работы с микронутриентами (витамины и минералы)
"""
from datetime import date, datetime, timedelta
from typing import Dict, Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.micronutrients import DailyMicronutrients, MicronutrientTargets
from app.models.meal import Meal, MealFood
from app.models.user import User, Gender


class MicronutrientService:
    """Сервис для расчета и хранения микронутриентов"""

    @staticmethod
    async def update_daily_micronutrients(
        db: AsyncSession,
        user_id: int,
        meal_date: date,
        micronutrients_delta: Dict[str, float]
    ) -> DailyMicronutrients:
        """
        Обновить суточную статистику микронутриентов

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            meal_date: Дата приема пищи
            micronutrients_delta: Словарь с добавляемыми значениями микронутриентов

        Returns:
            Обновленная запись DailyMicronutrients
        """
        try:
            # Ищем существующую запись за этот день
            result = await db.execute(
                select(DailyMicronutrients).where(
                    DailyMicronutrients.user_id == user_id,
                    DailyMicronutrients.date == meal_date
                )
            )
            daily_record = result.scalar_one_or_none()

            # Если записи нет - создаем новую
            if not daily_record:
                daily_record = DailyMicronutrients(
                    user_id=user_id,
                    date=meal_date
                )
                db.add(daily_record)

            # Обновляем значения микронутриентов
            for nutrient_name, value in micronutrients_delta.items():
                if hasattr(daily_record, nutrient_name):
                    current_value = getattr(daily_record, nutrient_name) or 0
                    setattr(daily_record, nutrient_name, current_value + value)

            daily_record.updated_at = datetime.utcnow()

            await db.commit()
            await db.refresh(daily_record)

            logger.info(f"Updated daily micronutrients for user {user_id} on {meal_date}")
            return daily_record

        except Exception as e:
            logger.error("Error updating daily micronutrients: %s", str(e))
            await db.rollback()
            raise

    @staticmethod
    async def get_daily_micronutrients(
        db: AsyncSession,
        user_id: int,
        target_date: date
    ) -> Optional[DailyMicronutrients]:
        """
        Получить суточную статистику микронутриентов

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            target_date: Дата

        Returns:
            Запись DailyMicronutrients или None
        """
        try:
            result = await db.execute(
                select(DailyMicronutrients).where(
                    DailyMicronutrients.user_id == user_id,
                    DailyMicronutrients.date == target_date
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("Error getting daily micronutrients: %s", str(e))
            return None

    @staticmethod
    async def get_period_micronutrients(
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> List[DailyMicronutrients]:
        """
        Получить статистику микронутриентов за период

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            Список записей DailyMicronutrients
        """
        try:
            result = await db.execute(
                select(DailyMicronutrients)
                .where(
                    DailyMicronutrients.user_id == user_id,
                    DailyMicronutrients.date >= start_date,
                    DailyMicronutrients.date <= end_date
                )
                .order_by(DailyMicronutrients.date)
            )
            return list(result.scalars().all())

        except Exception as e:
            logger.error("Error getting period micronutrients: %s", str(e))
            return []

    @staticmethod
    async def calculate_period_average(
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, float]:
        """
        Рассчитать средние значения микронутриентов за период

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            start_date: Начальная дата
            end_date: Конечная дата

        Returns:
            Словарь со средними значениями
        """
        try:
            records = await MicronutrientService.get_period_micronutrients(
                db, user_id, start_date, end_date
            )

            if not records:
                return {}

            # Список полей микронутриентов
            nutrient_fields = [
                'vitamin_a', 'beta_carotene', 'vitamin_b1', 'vitamin_b2', 'vitamin_b3',
                'vitamin_b5', 'vitamin_b6', 'vitamin_b7', 'vitamin_b9', 'vitamin_b12',
                'vitamin_c', 'vitamin_d', 'vitamin_e', 'vitamin_k', 'choline',
                'calcium', 'phosphorus', 'magnesium', 'potassium', 'sodium',
                'chloride', 'iron', 'zinc', 'iodine', 'selenium',
                'copper', 'manganese', 'chromium', 'fluoride', 'cobalt', 'silicon'
            ]

            # Вычисляем средние
            averages = {}
            num_records = len(records)

            for field in nutrient_fields:
                total = sum(getattr(record, field, 0) or 0 for record in records)
                averages[field] = total / num_records if num_records > 0 else 0

            return averages

        except Exception as e:
            logger.error("Error calculating period average: %s", str(e))
            return {}

    @staticmethod
    async def get_micronutrient_targets(
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, Dict[str, any]]:
        """
        Получить целевые значения микронутриентов для пользователя

        Args:
            db: Сессия базы данных
            user_id: ID пользователя

        Returns:
            Словарь с целевыми значениями, единицами и названиями
        """
        try:
            # Получаем пользователя
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"User {user_id} not found")
                return MicronutrientTargets.get_all_targets("male")

            # Определяем пол для целевых значений
            gender = "female" if user.gender == Gender.FEMALE else "male"

            return MicronutrientTargets.get_all_targets(gender)

        except Exception as e:
            logger.error("Error getting micronutrient targets: %s", str(e))
            return MicronutrientTargets.get_all_targets("male")

    @staticmethod
    def calculate_nutrient_percentage(
        current_value: float,
        target_value: float
    ) -> float:
        """
        Рассчитать процент выполнения нормы

        Args:
            current_value: Текущее значение
            target_value: Целевое значение

        Returns:
            Процент выполнения (0-100+)
        """
        if target_value == 0:
            return 0

        return (current_value / target_value) * 100

    @staticmethod
    async def recalculate_daily_totals(
        db: AsyncSession,
        user_id: int,
        target_date: date
    ) -> DailyMicronutrients:
        """
        Пересчитать суточные итоги микронутриентов из всех приемов пищи за день
        Используется для синхронизации после удаления или редактирования

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            target_date: Дата для пересчета

        Returns:
            Обновленная запись DailyMicronutrients
        """
        try:
            # Получаем все приемы пищи за день
            result = await db.execute(
                select(Meal).where(
                    Meal.user_id == user_id,
                    Meal.meal_date == target_date
                )
            )
            meals = list(result.scalars().all())

            # Создаем или получаем запись для этого дня
            result = await db.execute(
                select(DailyMicronutrients).where(
                    DailyMicronutrients.user_id == user_id,
                    DailyMicronutrients.date == target_date
                )
            )
            daily_record = result.scalar_one_or_none()

            if not daily_record:
                daily_record = DailyMicronutrients(
                    user_id=user_id,
                    date=target_date
                )
                db.add(daily_record)

            # Обнуляем все значения
            nutrient_fields = [
                'vitamin_a', 'beta_carotene', 'vitamin_b1', 'vitamin_b2', 'vitamin_b3',
                'vitamin_b5', 'vitamin_b6', 'vitamin_b7', 'vitamin_b9', 'vitamin_b12',
                'vitamin_c', 'vitamin_d', 'vitamin_e', 'vitamin_k', 'choline',
                'calcium', 'phosphorus', 'magnesium', 'potassium', 'sodium',
                'chloride', 'iron', 'zinc', 'iodine', 'selenium',
                'copper', 'manganese', 'chromium', 'fluoride', 'cobalt', 'silicon'
            ]

            for field in nutrient_fields:
                setattr(daily_record, field, 0)

            # Суммируем микронутриенты из всех блюд
            for meal in meals:
                for food in meal.foods:
                    micronutrients = food.micronutrients or {}
                    for nutrient_name, value in micronutrients.items():
                        if hasattr(daily_record, nutrient_name):
                            current = getattr(daily_record, nutrient_name) or 0
                            setattr(daily_record, nutrient_name, current + value)

            daily_record.updated_at = datetime.utcnow()

            await db.commit()
            await db.refresh(daily_record)

            logger.info(f"Recalculated daily micronutrients for user {user_id} on {target_date}")
            return daily_record

        except Exception as e:
            logger.error("Error recalculating daily totals: %s", str(e))
            await db.rollback()
            raise
