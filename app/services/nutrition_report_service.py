"""
Сервис для генерации отчетов о питании и микронутриентах
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from app.models.meal import Meal, MealFood
from app.models.meal_plan import MealPlan, MealPlanDay, PlannedMeal
from app.models.micronutrients import MicronutrientTargets
from app.models.user import User, Gender
from app.services.micronutrient_service import MicronutrientService


class NutritionReportService:
    """Сервис для генерации отчетов о питании"""

    @staticmethod
    async def get_daily_report(
        db: AsyncSession,
        user_id: int,
        target_date: date
    ) -> Dict:
        """
        Получить отчет за день

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            target_date: Дата отчета

        Returns:
            Словарь с данными отчета
        """
        try:
            # Получаем пользователя
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User {user_id} not found")

            # Получаем приемы пищи за день с eager loading foods
            result = await db.execute(
                select(Meal)
                .options(selectinload(Meal.foods))
                .where(
                    Meal.user_id == user_id,
                    Meal.meal_date == target_date
                )
                .order_by(Meal.meal_time)
            )
            meals = list(result.scalars().all())

            # Считаем общие макросы
            total_calories = sum(meal.total_calories for meal in meals)
            total_proteins = sum(meal.total_proteins for meal in meals)
            total_fats = sum(meal.total_fats for meal in meals)
            total_carbs = sum(meal.total_carbs for meal in meals)

            # Получаем микронутриенты
            daily_micros = await MicronutrientService.get_daily_micronutrients(
                db, user_id, target_date
            )

            # Получаем целевые значения
            micro_targets = await MicronutrientService.get_micronutrient_targets(
                db, user_id
            )

            # Формируем отчет
            report = {
                "date": target_date.isoformat(),
                "user": {
                    "name": user.preferred_name or user.first_name or "Пользователь",
                    "gender": user.gender.value if user.gender else "male"
                },
                "macros": {
                    "consumed": {
                        "calories": total_calories,
                        "proteins": round(total_proteins, 1),
                        "fats": round(total_fats, 1),
                        "carbs": round(total_carbs, 1)
                    },
                    "targets": {
                        "calories": user.target_calories,
                        "proteins": user.target_proteins,
                        "fats": user.target_fats,
                        "carbs": user.target_carbs
                    },
                    "percentages": {
                        "calories": round((total_calories / user.target_calories * 100) if user.target_calories else 0, 1),
                        "proteins": round((total_proteins / user.target_proteins * 100) if user.target_proteins else 0, 1),
                        "fats": round((total_fats / user.target_fats * 100) if user.target_fats else 0, 1),
                        "carbs": round((total_carbs / user.target_carbs * 100) if user.target_carbs else 0, 1)
                    }
                },
                "micronutrients": {},
                "meals": []
            }

            # Добавляем микронутриенты
            if daily_micros:
                micronutrient_data = {}
                for nutrient, target_info in micro_targets.items():
                    consumed = getattr(daily_micros, nutrient, 0) or 0
                    target = target_info["target"]
                    percentage = (consumed / target * 100) if target else 0

                    micronutrient_data[nutrient] = {
                        "name": target_info["name"],
                        "consumed": round(consumed, 2),
                        "target": target,
                        "unit": target_info["unit"],
                        "percentage": round(percentage, 1)
                    }

                report["micronutrients"] = micronutrient_data

            # Добавляем приемы пищи
            for meal in meals:
                meal_data = {
                    "type": meal.meal_type.value if meal.meal_type else "unknown",
                    "time": meal.meal_time.strftime("%H:%M") if meal.meal_time else "",
                    "calories": meal.total_calories,
                    "proteins": round(meal.total_proteins, 1),
                    "fats": round(meal.total_fats, 1),
                    "carbs": round(meal.total_carbs, 1),
                    "foods": []
                }

                for food in meal.foods:
                    meal_data["foods"].append({
                        "name": food.name,
                        "portion": food.portion_size,
                        "calories": food.calories,
                        "proteins": round(food.proteins, 1),
                        "fats": round(food.fats, 1),
                        "carbs": round(food.carbs, 1)
                    })

                report["meals"].append(meal_data)

            return report

        except Exception as e:
            logger.error("Error generating daily report: {}", repr(e))
            raise

    @staticmethod
    async def get_period_report(
        db: AsyncSession,
        user_id: int,
        start_date: date,
        end_date: date,
        period_type: str = "week"  # week, month
    ) -> Dict:
        """
        Получить отчет за период (неделя/месяц)

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            start_date: Начальная дата
            end_date: Конечная дата
            period_type: Тип периода (week, month)

        Returns:
            Словарь с данными отчета
        """
        try:
            # Получаем пользователя
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError(f"User {user_id} not found")

            # Получаем все приемы пищи за период с eager loading foods
            result = await db.execute(
                select(Meal)
                .options(selectinload(Meal.foods))
                .where(
                    Meal.user_id == user_id,
                    Meal.meal_date >= start_date,
                    Meal.meal_date <= end_date
                )
            )
            meals = list(result.scalars().all())

            # Группируем по дням
            days_data = {}
            for meal in meals:
                meal_date = meal.meal_date
                if meal_date not in days_data:
                    days_data[meal_date] = {
                        "calories": 0,
                        "proteins": 0,
                        "fats": 0,
                        "carbs": 0,
                        "meal_count": 0
                    }

                days_data[meal_date]["calories"] += meal.total_calories
                days_data[meal_date]["proteins"] += meal.total_proteins
                days_data[meal_date]["fats"] += meal.total_fats
                days_data[meal_date]["carbs"] += meal.total_carbs
                days_data[meal_date]["meal_count"] += 1

            # Считаем средние значения
            num_days = len(days_data) if days_data else 1
            total_calories = sum(day["calories"] for day in days_data.values())
            total_proteins = sum(day["proteins"] for day in days_data.values())
            total_fats = sum(day["fats"] for day in days_data.values())
            total_carbs = sum(day["carbs"] for day in days_data.values())

            avg_calories = total_calories / num_days
            avg_proteins = total_proteins / num_days
            avg_fats = total_fats / num_days
            avg_carbs = total_carbs / num_days

            # Получаем микронутриенты за период
            avg_micronutrients = await MicronutrientService.calculate_period_average(
                db, user_id, start_date, end_date
            )

            # Получаем целевые значения
            micro_targets = await MicronutrientService.get_micronutrient_targets(
                db, user_id
            )

            # Формируем отчет
            report = {
                "period": {
                    "type": period_type,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days_count": (end_date - start_date).days + 1,
                    "days_with_data": num_days
                },
                "user": {
                    "name": user.preferred_name or user.first_name or "Пользователь",
                    "gender": user.gender.value if user.gender else "male"
                },
                "macros": {
                    "average": {
                        "calories": round(avg_calories, 0),
                        "proteins": round(avg_proteins, 1),
                        "fats": round(avg_fats, 1),
                        "carbs": round(avg_carbs, 1)
                    },
                    "total": {
                        "calories": round(total_calories, 0),
                        "proteins": round(total_proteins, 1),
                        "fats": round(total_fats, 1),
                        "carbs": round(total_carbs, 1)
                    },
                    "targets": {
                        "calories": user.target_calories,
                        "proteins": user.target_proteins,
                        "fats": user.target_fats,
                        "carbs": user.target_carbs
                    },
                    "percentages": {
                        "calories": round((avg_calories / user.target_calories * 100) if user.target_calories else 0, 1),
                        "proteins": round((avg_proteins / user.target_proteins * 100) if user.target_proteins else 0, 1),
                        "fats": round((avg_fats / user.target_fats * 100) if user.target_fats else 0, 1),
                        "carbs": round((avg_carbs / user.target_carbs * 100) if user.target_carbs else 0, 1)
                    }
                },
                "micronutrients": {},
                "daily_breakdown": []
            }

            # Добавляем микронутриенты
            if avg_micronutrients:
                micronutrient_data = {}
                for nutrient, target_info in micro_targets.items():
                    consumed = avg_micronutrients.get(nutrient, 0)
                    target = target_info["target"]
                    percentage = (consumed / target * 100) if target else 0

                    micronutrient_data[nutrient] = {
                        "name": target_info["name"],
                        "average": round(consumed, 2),
                        "target": target,
                        "unit": target_info["unit"],
                        "percentage": round(percentage, 1)
                    }

                report["micronutrients"] = micronutrient_data

            # Добавляем разбивку по дням
            for day_date in sorted(days_data.keys()):
                day_info = days_data[day_date]
                report["daily_breakdown"].append({
                    "date": day_date.isoformat(),
                    "calories": round(day_info["calories"], 0),
                    "proteins": round(day_info["proteins"], 1),
                    "fats": round(day_info["fats"], 1),
                    "carbs": round(day_info["carbs"], 1),
                    "meal_count": day_info["meal_count"]
                })

            return report

        except Exception as e:
            logger.error("Error generating period report: {}", repr(e))
            raise

    @staticmethod
    async def get_plan_comparison(
        db: AsyncSession,
        user_id: int,
        target_date: date
    ) -> Dict:
        """
        Сравнить запланированное и фактическое питание за день

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            target_date: Дата

        Returns:
            Словарь с данными сравнения
        """
        try:
            # Получаем фактические приемы пищи
            result = await db.execute(
                select(Meal).where(
                    Meal.user_id == user_id,
                    Meal.meal_date == target_date
                )
            )
            actual_meals = list(result.scalars().all())

            # Считаем фактические макросы
            actual_calories = sum(meal.total_calories for meal in actual_meals)
            actual_proteins = sum(meal.total_proteins for meal in actual_meals)
            actual_fats = sum(meal.total_fats for meal in actual_meals)
            actual_carbs = sum(meal.total_carbs for meal in actual_meals)

            # Получаем активный план питания
            result = await db.execute(
                select(MealPlan).where(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True,
                    MealPlan.start_date <= target_date,
                    MealPlan.end_date >= target_date
                )
            )
            meal_plan = result.scalar_one_or_none()

            planned_calories = 0
            planned_proteins = 0
            planned_fats = 0
            planned_carbs = 0

            if meal_plan:
                # Получаем запланированный день
                result = await db.execute(
                    select(MealPlanDay).where(
                        MealPlanDay.meal_plan_id == meal_plan.id,
                        MealPlanDay.day_date == target_date
                    )
                )
                plan_day = result.scalar_one_or_none()

                if plan_day:
                    planned_calories = plan_day.total_calories or 0
                    planned_proteins = plan_day.total_proteins or 0
                    planned_fats = plan_day.total_fats or 0
                    planned_carbs = plan_day.total_carbs or 0

            # Формируем результат
            comparison = {
                "date": target_date.isoformat(),
                "has_plan": meal_plan is not None,
                "planned": {
                    "calories": planned_calories,
                    "proteins": round(planned_proteins, 1),
                    "fats": round(planned_fats, 1),
                    "carbs": round(planned_carbs, 1)
                },
                "actual": {
                    "calories": actual_calories,
                    "proteins": round(actual_proteins, 1),
                    "fats": round(actual_fats, 1),
                    "carbs": round(actual_carbs, 1)
                },
                "difference": {
                    "calories": actual_calories - planned_calories,
                    "proteins": round(actual_proteins - planned_proteins, 1),
                    "fats": round(actual_fats - planned_fats, 1),
                    "carbs": round(actual_carbs - planned_carbs, 1)
                },
                "percentages": {
                    "calories": round((actual_calories / planned_calories * 100) if planned_calories else 0, 1),
                    "proteins": round((actual_proteins / planned_proteins * 100) if planned_proteins else 0, 1),
                    "fats": round((actual_fats / planned_fats * 100) if planned_fats else 0, 1),
                    "carbs": round((actual_carbs / planned_carbs * 100) if planned_carbs else 0, 1)
                }
            }

            return comparison

        except Exception as e:
            logger.error("Error generating plan comparison: {}", repr(e))
            raise
