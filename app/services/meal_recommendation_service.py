"""
Сервис для генерации рекомендаций по питанию через AI
"""
from datetime import datetime, date, time
from typing import Optional, Dict, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from app.models.user import User
from app.models.meal import Meal, MealType
from app.models.meal_plan import MealPlan
from app.services.temporary_meal_plan_service import TemporaryMealPlanService
from app.services.nutrition_calc import NutritionCalculator


class MealRecommendationService:
    """Сервис для генерации AI-рекомендаций по питанию"""

    @staticmethod
    def detect_meal_type_from_time(current_time: time) -> str:
        """
        Определить тип приема пищи на основе текущего времени

        Args:
            current_time: Текущее время

        Returns:
            Название приема пищи (завтрак/обед/ужин/перекус)
        """
        hour = current_time.hour

        if 5 <= hour < 11:
            return "завтрак"
        elif 11 <= hour < 15:
            return "обед"
        elif 15 <= hour < 18:
            return "перекус"
        elif 18 <= hour < 23:
            return "ужин"
        else:
            return "поздний перекус"

    @staticmethod
    async def get_daily_nutrition_status(
        user_id: int,
        session: AsyncSession
    ) -> Dict:
        """
        Получить статус питания за сегодня

        Args:
            user_id: ID пользователя
            session: Сессия БД

        Returns:
            Словарь со статистикой
        """
        try:
            today = date.today()

            # Получаем все приемы пищи за сегодня
            result = await session.execute(
                select(Meal)
                .where(
                    Meal.user_id == user_id,
                    Meal.meal_date == today
                )
            )
            meals = result.scalars().all()

            # Рассчитываем суммарные показатели
            total_calories = sum(meal.calories or 0 for meal in meals)
            total_proteins = sum(meal.proteins or 0 for meal in meals)
            total_fats = sum(meal.fats or 0 for meal in meals)
            total_carbs = sum(meal.carbs or 0 for meal in meals)

            # Группируем по типам приемов пищи
            meals_by_type = {
                MealType.BREAKFAST: [],
                MealType.LUNCH: [],
                MealType.DINNER: [],
                MealType.SNACK: []
            }

            for meal in meals:
                if meal.meal_type in meals_by_type:
                    meals_by_type[meal.meal_type].append(meal)

            return {
                "total_calories": total_calories,
                "total_proteins": total_proteins,
                "total_fats": total_fats,
                "total_carbs": total_carbs,
                "meals_count": len(meals),
                "has_breakfast": len(meals_by_type[MealType.BREAKFAST]) > 0,
                "has_lunch": len(meals_by_type[MealType.LUNCH]) > 0,
                "has_dinner": len(meals_by_type[MealType.DINNER]) > 0,
                "meals_by_type": meals_by_type
            }

        except Exception as e:
            logger.error("Error getting daily nutrition status for user {user_id}: %s", str(e))
            return {
                "total_calories": 0,
                "total_proteins": 0,
                "total_fats": 0,
                "total_carbs": 0,
                "meals_count": 0,
                "has_breakfast": False,
                "has_lunch": False,
                "has_dinner": False,
                "meals_by_type": {}
            }

    @staticmethod
    async def calculate_remaining_nutrients(
        user: User,
        daily_status: Dict,
        session: AsyncSession
    ) -> Dict:
        """
        Рассчитать оставшиеся калории и макронутриенты

        Args:
            user: Объект пользователя
            daily_status: Статус питания за день
            session: Сессия БД

        Returns:
            Словарь с оставшимися показателями
        """
        try:
            # Получаем целевые показатели с учетом бонусов от шагов
            if user.gender and user.current_weight and user.height and user.birth_year:
                age = datetime.now().year - user.birth_year
                target_calories, bonus_calories = await NutritionCalculator.calculate_target_calories_with_activity_bonus(
                    user_id=user.id,
                    gender=user.gender,
                    weight=user.current_weight,
                    height=user.height,
                    age=age,
                    activity_level=user.activity_level,
                    goal=user.goal,
                    session=session
                )
            else:
                # Используем сохраненные целевые показатели
                target_calories = user.target_calories or 2000
                bonus_calories = 0

            # Рассчитываем остатки
            remaining_calories = target_calories - daily_status["total_calories"]
            remaining_proteins = (user.target_proteins or 100) - daily_status["total_proteins"]
            remaining_fats = (user.target_fats or 60) - daily_status["total_fats"]
            remaining_carbs = (user.target_carbs or 250) - daily_status["total_carbs"]

            return {
                "target_calories": target_calories,
                "bonus_calories": bonus_calories,
                "remaining_calories": max(0, remaining_calories),
                "remaining_proteins": max(0, remaining_proteins),
                "remaining_fats": max(0, remaining_fats),
                "remaining_carbs": max(0, remaining_carbs),
                "calories_percent": int((daily_status["total_calories"] / target_calories) * 100) if target_calories > 0 else 0
            }

        except Exception as e:
            logger.error("Error calculating remaining nutrients for user {user.id}: %s", str(e))
            return {
                "target_calories": 2000,
                "bonus_calories": 0,
                "remaining_calories": 0,
                "remaining_proteins": 0,
                "remaining_fats": 0,
                "remaining_carbs": 0,
                "calories_percent": 0
            }

    @staticmethod
    async def check_existing_plan(
        user_id: int,
        session: AsyncSession
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить наличие плана питания на сегодня

        Args:
            user_id: ID пользователя
            session: Сессия БД

        Returns:
            Кортеж (есть_план, тип_плана)
            тип_плана: "permanent" (постоянный план) или "temporary" (временный)
        """
        try:
            # Проверяем постоянный план
            has_permanent = await TemporaryMealPlanService.has_permanent_plan(
                user_id, session
            )

            if has_permanent:
                return True, "permanent"

            # Проверяем временный план
            temp_plan = await TemporaryMealPlanService.get_today_plan(
                user_id, session
            )

            if temp_plan:
                return True, "temporary"

            return False, None

        except Exception as e:
            logger.error("Error checking existing plan for user {user_id}: %s", str(e))
            return False, None

    @staticmethod
    async def generate_meal_recommendation_context(
        user: User,
        session: AsyncSession
    ) -> Dict:
        """
        Собрать контекст для генерации рекомендаций по питанию

        Args:
            user: Объект пользователя
            session: Сессия БД

        Returns:
            Словарь с контекстом
        """
        try:
            # Определяем текущий прием пищи
            current_time = datetime.now().time()
            meal_type = MealRecommendationService.detect_meal_type_from_time(current_time)

            # Получаем статус питания за день
            daily_status = await MealRecommendationService.get_daily_nutrition_status(
                user.id, session
            )

            # Рассчитываем оставшиеся показатели
            remaining = await MealRecommendationService.calculate_remaining_nutrients(
                user, daily_status, session
            )

            # Проверяем наличие плана
            has_plan, plan_type = await MealRecommendationService.check_existing_plan(
                user.id, session
            )

            return {
                "current_time": datetime.now().strftime("%H:%M"),
                "meal_type": meal_type,
                "daily_status": daily_status,
                "remaining": remaining,
                "has_plan": has_plan,
                "plan_type": plan_type,
                "user_preferences": {
                    "diet_type": user.diet_type.value if user.diet_type else "omnivore",
                    "allergies": user.allergies or [],
                    "dislikes": user.dislikes or [],
                    "budget": user.budget_category.value if user.budget_category else "normal",
                    "cooking_time": user.preferred_cooking_time_minutes
                },
                "medical_restrictions": user.medical_restrictions or {}
            }

        except Exception as e:
            logger.error("Error generating meal recommendation context for user {user.id}: %s", str(e))
            raise
