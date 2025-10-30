"""
Сервис для работы с временными рационами на день
"""
from datetime import date, datetime, timedelta
from typing import Optional, Dict
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.temporary_meal_plan import TemporaryMealPlan
from app.models.user import User


class TemporaryMealPlanService:
    """Сервис для управления временными рационами"""

    @staticmethod
    async def get_today_plan(
        user_id: int,
        session: AsyncSession
    ) -> Optional[TemporaryMealPlan]:
        """
        Получить временный рацион на сегодня

        Args:
            user_id: ID пользователя
            session: Сессия БД

        Returns:
            Временный рацион или None
        """
        try:
            today = date.today()

            result = await session.execute(
                select(TemporaryMealPlan).where(
                    TemporaryMealPlan.user_id == user_id,
                    TemporaryMealPlan.date == today,
                    TemporaryMealPlan.expires_at > datetime.now()
                )
            )
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("Error getting temporary meal plan for user {user_id}: {}", repr(e))
            return None

    @staticmethod
    async def create_or_update_plan(
        user_id: int,
        meal_plan_data: Dict,
        total_calories: int,
        session: AsyncSession
    ) -> TemporaryMealPlan:
        """
        Создать или обновить временный рацион на сегодня

        Args:
            user_id: ID пользователя
            meal_plan_data: Данные рациона (dict)
            total_calories: Общее количество калорий
            session: Сессия БД

        Returns:
            Созданный или обновленный временный рацион
        """
        try:
            today = date.today()
            # Истекает в 00:00 следующего дня
            expires_at = datetime.combine(
                today + timedelta(days=1),
                datetime.min.time()
            )

            # Проверяем существующий план
            result = await session.execute(
                select(TemporaryMealPlan).where(
                    TemporaryMealPlan.user_id == user_id,
                    TemporaryMealPlan.date == today
                )
            )
            existing_plan = result.scalar_one_or_none()

            if existing_plan:
                # Обновляем существующий
                existing_plan.set_meal_plan_data(meal_plan_data)
                existing_plan.total_calories = total_calories
                existing_plan.expires_at = expires_at
                await session.commit()
                await session.refresh(existing_plan)
                logger.info(f"Updated temporary meal plan for user {user_id}")
                return existing_plan
            else:
                # Создаем новый
                new_plan = TemporaryMealPlan(
                    user_id=user_id,
                    date=today,
                    meal_plan_data="",  # Пустая строка, установим через метод
                    total_calories=total_calories,
                    expires_at=expires_at
                )
                new_plan.set_meal_plan_data(meal_plan_data)

                session.add(new_plan)
                await session.commit()
                await session.refresh(new_plan)
                logger.info(f"Created temporary meal plan for user {user_id}")
                return new_plan

        except Exception as e:
            await session.rollback()
            logger.error("Error creating/updating temporary meal plan for user {user_id}: {}", repr(e))
            raise

    @staticmethod
    async def delete_expired_plans(session: AsyncSession) -> int:
        """
        Удалить истекшие временные рационы

        Args:
            session: Сессия БД

        Returns:
            Количество удаленных записей
        """
        try:
            result = await session.execute(
                delete(TemporaryMealPlan).where(
                    TemporaryMealPlan.expires_at <= datetime.now()
                )
            )
            await session.commit()
            deleted_count = result.rowcount
            logger.info(f"Deleted {deleted_count} expired temporary meal plans")
            return deleted_count

        except Exception as e:
            await session.rollback()
            logger.error("Error deleting expired temporary meal plans: {}", repr(e))
            return 0

    @staticmethod
    async def has_permanent_plan(
        user_id: int,
        session: AsyncSession
    ) -> bool:
        """
        Проверить наличие постоянного плана питания на сегодня

        Args:
            user_id: ID пользователя
            session: Сессия БД

        Returns:
            True если есть постоянный план
        """
        try:
            from app.models.meal_plan import MealPlan, MealPlanDay
            from sqlalchemy.orm import selectinload

            today = date.today()

            # Получаем активный план питания
            result = await session.execute(
                select(MealPlan)
                .options(selectinload(MealPlan.days))
                .where(
                    MealPlan.user_id == user_id,
                    MealPlan.start_date <= today,
                    MealPlan.end_date >= today
                )
                .order_by(MealPlan.created_at.desc())
            )
            meal_plan = result.scalar_one_or_none()

            if not meal_plan or not meal_plan.days:
                return False

            # Проверяем есть ли день для сегодня
            for day in meal_plan.days:
                if day.day_date == today:
                    return True

            return False

        except Exception as e:
            logger.error("Error checking permanent meal plan for user {user_id}: {}", repr(e))
            return False
