"""
Сервис для работы с дневником питания
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
from loguru import logger

from app.models.meal import Meal, MealFood, MealType
from app.models.user import User


class MealService:
    """Сервис для управления дневником питания"""

    @staticmethod
    async def create_meal_with_foods(
        session: AsyncSession,
        user_id: int,
        meal_type: MealType,
        meal_date: date,
        meal_time: datetime,
        foods_data: List[Dict],
        notes: Optional[str] = None,
        photo_url: Optional[str] = None
    ) -> Meal:
        """
        Создать прием пищи с блюдами

        Args:
            session: Сессия БД
            user_id: ID пользователя
            meal_type: Тип приема пищи
            meal_date: Дата приема пищи
            meal_time: Время приема пищи
            foods_data: Список данных о блюдах [{"name": "...", "portion_size": 100, ...}, ...]
            notes: Заметки
            photo_url: URL фото

        Returns:
            Объект Meal с добавленными foods
        """
        try:
            # Создаем прием пищи
            meal = Meal(
                user_id=user_id,
                meal_type=meal_type,
                meal_date=meal_date,
                meal_time=meal_time,
                notes=notes,
                photo_url=photo_url,
                total_calories=0,
                total_proteins=0,
                total_fats=0,
                total_carbs=0
            )
            session.add(meal)
            await session.flush()  # Получаем ID meal

            # Добавляем блюда
            total_calories = 0
            total_proteins = 0.0
            total_fats = 0.0
            total_carbs = 0.0

            for food_data in foods_data:
                meal_food = MealFood(
                    meal_id=meal.id,
                    name=food_data["name"],
                    portion_size=food_data["portion_size"],
                    portion_description=food_data.get("portion_description"),
                    calories=food_data["calories"],
                    proteins=food_data["proteins"],
                    fats=food_data["fats"],
                    carbs=food_data["carbs"],
                    ingredients=food_data.get("ingredients", []),
                    confidence_score=food_data.get("confidence_score")
                )
                session.add(meal_food)

                # Суммируем пищевую ценность
                total_calories += food_data["calories"]
                total_proteins += food_data["proteins"]
                total_fats += food_data["fats"]
                total_carbs += food_data["carbs"]

            # Обновляем итоги приема пищи
            meal.total_calories = total_calories
            meal.total_proteins = total_proteins
            meal.total_fats = total_fats
            meal.total_carbs = total_carbs

            await session.commit()
            await session.refresh(meal)

            logger.info(f"Created meal {meal.id} for user {user_id} with {len(foods_data)} foods")

            return meal

        except Exception as e:
            await session.rollback()
            logger.error(f"Error creating meal: {e}")
            raise

    @staticmethod
    async def get_meals_by_date(
        session: AsyncSession,
        user_id: int,
        target_date: date
    ) -> List[Meal]:
        """
        Получить все приемы пищи за конкретный день

        Args:
            session: Сессия БД
            user_id: ID пользователя
            target_date: Дата

        Returns:
            Список приемов пищи
        """
        result = await session.execute(
            select(Meal)
            .where(and_(
                Meal.user_id == user_id,
                Meal.meal_date == target_date
            ))
            .order_by(Meal.meal_time)
        )
        meals = result.scalars().all()

        # Загружаем связанные foods для каждого meal
        for meal in meals:
            await session.refresh(meal, ["foods"])

        return list(meals)

    @staticmethod
    async def get_daily_totals(
        session: AsyncSession,
        user_id: int,
        target_date: date
    ) -> Dict:
        """
        Получить общую сумму калорий и БЖУ за день

        Args:
            session: Сессия БД
            user_id: ID пользователя
            target_date: Дата

        Returns:
            Словарь с суммарными показателями
        """
        result = await session.execute(
            select(
                func.coalesce(func.sum(Meal.total_calories), 0).label("calories"),
                func.coalesce(func.sum(Meal.total_proteins), 0).label("proteins"),
                func.coalesce(func.sum(Meal.total_fats), 0).label("fats"),
                func.coalesce(func.sum(Meal.total_carbs), 0).label("carbs")
            )
            .where(and_(
                Meal.user_id == user_id,
                Meal.meal_date == target_date
            ))
        )
        row = result.first()

        return {
            "calories": int(row.calories) if row else 0,
            "proteins": float(row.proteins) if row else 0.0,
            "fats": float(row.fats) if row else 0.0,
            "carbs": float(row.carbs) if row else 0.0
        }

    @staticmethod
    async def delete_meal(
        session: AsyncSession,
        meal_id: int,
        user_id: int
    ) -> bool:
        """
        Удалить прием пищи

        Args:
            session: Сессия БД
            meal_id: ID приема пищи
            user_id: ID пользователя (для проверки прав)

        Returns:
            True если удалено успешно, False если не найдено
        """
        result = await session.execute(
            select(Meal).where(and_(
                Meal.id == meal_id,
                Meal.user_id == user_id
            ))
        )
        meal = result.scalar_one_or_none()

        if not meal:
            return False

        await session.delete(meal)
        await session.commit()

        logger.info(f"Deleted meal {meal_id} for user {user_id}")
        return True

    @staticmethod
    async def get_meal_by_id(
        session: AsyncSession,
        meal_id: int,
        user_id: int
    ) -> Optional[Meal]:
        """
        Получить прием пищи по ID

        Args:
            session: Сессия БД
            meal_id: ID приема пищи
            user_id: ID пользователя (для проверки прав)

        Returns:
            Объект Meal или None
        """
        result = await session.execute(
            select(Meal).where(and_(
                Meal.id == meal_id,
                Meal.user_id == user_id
            ))
        )
        meal = result.scalar_one_or_none()

        if meal:
            await session.refresh(meal, ["foods"])

        return meal

    @staticmethod
    async def get_nutrition_progress(
        session: AsyncSession,
        user_id: int,
        target_date: date
    ) -> Dict:
        """
        Получить прогресс по калориям и БЖУ относительно целевых значений

        Args:
            session: Сессия БД
            user_id: ID пользователя
            target_date: Дата

        Returns:
            Словарь с текущими значениями, целями и процентами
        """
        # Получаем целевые значения пользователя
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {}

        # Получаем текущие значения за день
        daily_totals = await MealService.get_daily_totals(session, user_id, target_date)

        # Вычисляем проценты
        def calc_percent(current, target):
            return round((current / target * 100) if target > 0 else 0, 1)

        return {
            "current": daily_totals,
            "target": {
                "calories": user.target_calories or 0,
                "proteins": user.target_proteins or 0,
                "fats": user.target_fats or 0,
                "carbs": user.target_carbs or 0
            },
            "percent": {
                "calories": calc_percent(daily_totals["calories"], user.target_calories or 0),
                "proteins": calc_percent(daily_totals["proteins"], user.target_proteins or 0),
                "fats": calc_percent(daily_totals["fats"], user.target_fats or 0),
                "carbs": calc_percent(daily_totals["carbs"], user.target_carbs or 0)
            },
            "remaining": {
                "calories": max(0, (user.target_calories or 0) - daily_totals["calories"]),
                "proteins": max(0, (user.target_proteins or 0) - daily_totals["proteins"]),
                "fats": max(0, (user.target_fats or 0) - daily_totals["fats"]),
                "carbs": max(0, (user.target_carbs or 0) - daily_totals["carbs"])
            }
        }
