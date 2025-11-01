"""
Сервис для работы с кэшированными планами питания
"""
import hashlib
import json
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from loguru import logger

from app.models.user import User
from app.models.cached_meal_plan import UserCategory, CachedMealPlan, CachedMealPlanStatus
from app.models.meal_plan import PlanPeriod


class CachedMealPlanService:
    """Сервис для работы с кэшированными планами питания"""

    @staticmethod
    def generate_params_hash(
        calories: int,
        proteins: int,
        fats: int,
        carbs: int,
        diet_type: str,
        budget_category: str,
        allergies: List[str]
    ) -> str:
        """
        Генерирует хэш параметров пользователя для определения категории.

        Args:
            calories: Целевые калории
            proteins: Целевые белки
            fats: Целевые жиры
            carbs: Целевые углеводы
            diet_type: Тип диеты
            budget_category: Категория бюджета
            allergies: Список аллергий (будет отсортирован)

        Returns:
            str: SHA256 хэш параметров
        """
        # Округляем КБЖУ до диапазонов для группировки похожих пользователей
        # Например, 1950 и 2050 калорий попадут в один диапазон 2000
        calories_range = round(calories / 100) * 100
        proteins_range = round(proteins / 10) * 10
        fats_range = round(fats / 10) * 10
        carbs_range = round(carbs / 10) * 10

        # Сортируем аллергии для единообразия
        sorted_allergies = sorted(allergies) if allergies else []

        # Формируем строку параметров
        params_str = f"{calories_range}|{proteins_range}|{fats_range}|{carbs_range}|{diet_type}|{budget_category}|{','.join(sorted_allergies)}"

        # Генерируем хэш
        return hashlib.sha256(params_str.encode()).hexdigest()

    @staticmethod
    async def get_or_create_category(
        session: AsyncSession,
        user: User
    ) -> UserCategory:
        """
        Получает существующую категорию пользователя или создает новую.

        Args:
            session: Сессия БД
            user: Пользователь

        Returns:
            UserCategory: Категория пользователя
        """
        # Генерируем хэш параметров
        params_hash = CachedMealPlanService.generate_params_hash(
            calories=user.target_calories or 2000,
            proteins=user.target_proteins or 150,
            fats=user.target_fats or 65,
            carbs=user.target_carbs or 200,
            diet_type=user.diet_type.value if user.diet_type else "omnivore",
            budget_category=user.budget_category.value if user.budget_category else "normal",
            allergies=user.allergies or []
        )

        # Ищем существующую категорию
        result = await session.execute(
            select(UserCategory).where(UserCategory.params_hash == params_hash)
        )
        category = result.scalar_one_or_none()

        if category:
            # Обновляем счетчик пользователей и время использования
            category.users_count += 1
            category.last_used_at = datetime.now()
            await session.commit()
            logger.info(f"Found existing category {category.id} for user {user.telegram_id}")
            return category

        # Создаем новую категорию
        sorted_allergies = sorted(user.allergies) if user.allergies else []

        # Округляем КБЖУ до диапазонов
        calories_range = round((user.target_calories or 2000) / 100) * 100
        proteins_range = round((user.target_proteins or 150) / 10) * 10
        fats_range = round((user.target_fats or 65) / 10) * 10
        carbs_range = round((user.target_carbs or 200) / 10) * 10

        category = UserCategory(
            params_hash=params_hash,
            target_calories=calories_range,
            target_proteins=proteins_range,
            target_fats=fats_range,
            target_carbs=carbs_range,
            diet_type=user.diet_type.value if user.diet_type else "omnivore",
            budget_category=user.budget_category.value if user.budget_category else "normal",
            allergies=sorted_allergies,
            users_count=1
        )

        session.add(category)
        await session.commit()
        await session.refresh(category)

        logger.info(f"Created new category {category.id} for user {user.telegram_id}")
        return category

    @staticmethod
    async def get_cached_plan(
        session: AsyncSession,
        category: UserCategory,
        period_type: PlanPeriod
    ) -> Optional[Dict]:
        """
        Получает случайный активный кэшированный план для категории.

        Args:
            session: Сессия БД
            category: Категория пользователя
            period_type: Период плана (day/week/month)

        Returns:
            Optional[Dict]: Данные плана или None если планов нет
        """
        # Ищем активные планы для категории и периода
        result = await session.execute(
            select(CachedMealPlan).where(and_(
                CachedMealPlan.category_id == category.id,
                CachedMealPlan.period_type == period_type.value,
                CachedMealPlan.status == CachedMealPlanStatus.ACTIVE
            ))
        )
        cached_plans = result.scalars().all()

        if not cached_plans:
            logger.info(f"No cached plans found for category {category.id}, period {period_type.value}")
            return None

        # Выбираем случайный план (для разнообразия)
        # Приоритет планам с лучшим feedback_ratio
        # Сортируем по feedback_ratio и берем из топ-50%
        sorted_plans = sorted(cached_plans, key=lambda p: p.feedback_ratio, reverse=True)
        top_half = sorted_plans[:max(1, len(sorted_plans) // 2)]
        selected_plan = random.choice(top_half)

        # Обновляем статистику использования
        selected_plan.usage_count += 1
        selected_plan.last_used_at = datetime.now()
        await session.commit()

        logger.info(f"Selected cached plan {selected_plan.id} for category {category.id}, usage_count={selected_plan.usage_count}")

        return selected_plan.plan_data

    @staticmethod
    async def save_cached_plan(
        session: AsyncSession,
        category: UserCategory,
        period_type: PlanPeriod,
        plan_data: Dict
    ) -> CachedMealPlan:
        """
        Сохраняет новый кэшированный план.

        Args:
            session: Сессия БД
            category: Категория пользователя
            period_type: Период плана
            plan_data: Данные плана (в формате AI ответа)

        Returns:
            CachedMealPlan: Созданный кэшированный план
        """
        cached_plan = CachedMealPlan(
            category_id=category.id,
            period_type=period_type.value,
            plan_data=plan_data,
            status=CachedMealPlanStatus.ACTIVE
        )

        session.add(cached_plan)
        await session.commit()
        await session.refresh(cached_plan)

        logger.info(f"Saved new cached plan {cached_plan.id} for category {category.id}, period {period_type.value}")

        return cached_plan

    @staticmethod
    async def update_plan_feedback(
        session: AsyncSession,
        plan_data: Dict,
        category: UserCategory,
        period_type: PlanPeriod,
        is_positive: bool
    ):
        """
        Обновляет статистику обратной связи для плана.

        Args:
            session: Сессия БД
            plan_data: Данные плана
            category: Категория пользователя
            period_type: Период плана
            is_positive: True для положительного отзыва, False для отрицательного
        """
        # Ищем план по данным (сравниваем JSON)
        result = await session.execute(
            select(CachedMealPlan).where(and_(
                CachedMealPlan.category_id == category.id,
                CachedMealPlan.period_type == period_type.value,
                CachedMealPlan.status == CachedMealPlanStatus.ACTIVE
            ))
        )
        cached_plans = result.scalars().all()

        # Находим план с совпадающими данными
        for plan in cached_plans:
            # Сравниваем первый день для идентификации (упрощенно)
            if (plan.plan_data.get("days") and plan_data.get("days") and
                len(plan.plan_data["days"]) > 0 and len(plan_data["days"]) > 0):

                first_day_cached = plan.plan_data["days"][0]
                first_day_new = plan_data["days"][0]

                # Сравниваем первое блюдо первого дня
                if (first_day_cached.get("meals") and first_day_new.get("meals") and
                    len(first_day_cached["meals"]) > 0 and len(first_day_new["meals"]) > 0):

                    if first_day_cached["meals"][0].get("recipe_name") == first_day_new["meals"][0].get("recipe_name"):
                        # Это тот же план
                        if is_positive:
                            plan.positive_feedback_count += 1
                        else:
                            plan.negative_feedback_count += 1

                        await session.commit()
                        logger.info(f"Updated feedback for cached plan {plan.id}: positive={plan.positive_feedback_count}, negative={plan.negative_feedback_count}")
                        return

        logger.warning(f"Could not find matching cached plan for feedback update")

    @staticmethod
    async def get_category_stats(session: AsyncSession, category_id: int) -> Dict:
        """
        Получает статистику по категории.

        Args:
            session: Сессия БД
            category_id: ID категории

        Returns:
            Dict: Статистика категории
        """
        category = await session.get(UserCategory, category_id)
        if not category:
            return {}

        # Подсчитываем количество планов по типам
        result = await session.execute(
            select(
                CachedMealPlan.period_type,
                func.count(CachedMealPlan.id).label('count')
            ).where(and_(
                CachedMealPlan.category_id == category_id,
                CachedMealPlan.status == CachedMealPlanStatus.ACTIVE
            )).group_by(CachedMealPlan.period_type)
        )

        plans_by_type = {row.period_type: row.count for row in result}

        return {
            "category_id": category.id,
            "users_count": category.users_count,
            "target_calories": category.target_calories,
            "diet_type": category.diet_type,
            "budget_category": category.budget_category,
            "plans_by_type": plans_by_type,
            "total_plans": sum(plans_by_type.values())
        }

    @staticmethod
    async def mark_old_plans_outdated(session: AsyncSession, days_old: int = 7) -> int:
        """
        Помечает старые планы как устаревшие.

        Args:
            session: Сессия БД
            days_old: Количество дней после которых план считается устаревшим

        Returns:
            int: Количество помеченных планов
        """
        cutoff_date = datetime.now() - timedelta(days=days_old)

        result = await session.execute(
            select(CachedMealPlan).where(and_(
                CachedMealPlan.status == CachedMealPlanStatus.ACTIVE,
                CachedMealPlan.created_at < cutoff_date
            ))
        )
        old_plans = result.scalars().all()

        for plan in old_plans:
            plan.status = CachedMealPlanStatus.OUTDATED

        await session.commit()
        logger.info(f"Marked {len(old_plans)} plans as outdated")

        return len(old_plans)

    @staticmethod
    async def get_categories_needing_plans(
        session: AsyncSession,
        min_plans_per_period: int = 20
    ) -> List[Dict]:
        """
        Получает категории, которым нужно больше планов.

        Args:
            session: Сессия БД
            min_plans_per_period: Минимальное количество планов на период

        Returns:
            List[Dict]: Список категорий с недостаточным количеством планов
        """
        # Получаем все категории
        result = await session.execute(select(UserCategory))
        categories = result.scalars().all()

        categories_needing_plans = []

        for category in categories:
            # Подсчитываем количество активных планов по типам
            for period_type in ["day", "week", "month"]:
                count_result = await session.execute(
                    select(func.count(CachedMealPlan.id)).where(and_(
                        CachedMealPlan.category_id == category.id,
                        CachedMealPlan.period_type == period_type,
                        CachedMealPlan.status == CachedMealPlanStatus.ACTIVE
                    ))
                )
                count = count_result.scalar()

                if count < min_plans_per_period:
                    categories_needing_plans.append({
                        "category": category,
                        "period_type": period_type,
                        "current_count": count,
                        "needed_count": min_plans_per_period - count
                    })

        return categories_needing_plans
