"""
Сервис для работы с планами питания
"""
import json
from datetime import date, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger

from app.models.user import User
from app.models.meal_plan import MealPlan, MealPlanDay, PlannedMeal, PlanPeriod
from app.services.claude_ai import ClaudeAIService


class MealPlanService:
    """Сервис для генерации и управления планами питания"""

    @staticmethod
    async def generate_meal_plan(
        session: AsyncSession,
        user_id: int,
        period_type: PlanPeriod,
        start_date: date = None
    ) -> MealPlan:
        """
        Генерация плана питания через AI

        Args:
            session: Сессия БД
            user_id: ID пользователя
            period_type: Период плана (day/week/month)
            start_date: Дата начала плана (по умолчанию - сегодня)

        Returns:
            MealPlan: Созданный план питания
        """
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Определяем даты
        if start_date is None:
            start_date = date.today()

        days_count = {
            PlanPeriod.DAY: 1,
            PlanPeriod.WEEK: 7,
            PlanPeriod.MONTH: 30,
        }[period_type]

        end_date = start_date + timedelta(days=days_count - 1)

        # Формируем промпт для AI
        prompt = MealPlanService._build_meal_plan_prompt(user, period_type, days_count)

        # Генерируем план через AI
        from app.config import settings
        ai_service = ClaudeAIService()
        try:
            ai_response = await ai_service.async_client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=16000,
                temperature=0.8,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            plan_data = ai_response.content[0].text
            logger.info(f"AI generated meal plan for user {user_id}")

        except Exception as e:
            logger.error(f"Error generating meal plan: {e}")
            raise

        # Парсим ответ AI
        parsed_plan = MealPlanService._parse_ai_meal_plan(plan_data)

        # Создаем план в БД
        meal_plan = MealPlan(
            user_id=user.telegram_id,
            period_type=period_type,
            start_date=start_date,
            end_date=end_date,
            daily_calories=user.target_calories,
            daily_proteins=user.target_proteins,
            daily_fats=user.target_fats,
            daily_carbs=user.target_carbs,
            budget_category=user.budget_category.value if user.budget_category else "normal",
            diet_preferences={
                "diet_type": user.diet_type.value if user.diet_type else "omnivore",
                "allergies": user.allergies or [],
            }
        )

        session.add(meal_plan)
        await session.flush()  # Чтобы получить ID плана

        # Создаем дни и приемы пищи
        for day_num, day_data in enumerate(parsed_plan["days"], 1):
            day_date = start_date + timedelta(days=day_num - 1)

            meal_plan_day = MealPlanDay(
                meal_plan_id=meal_plan.id,
                day_date=day_date,
                day_number=day_num,
                total_calories=day_data.get("total_calories", 0),
                total_proteins=day_data.get("total_proteins", 0),
                total_fats=day_data.get("total_fats", 0),
                total_carbs=day_data.get("total_carbs", 0),
            )

            session.add(meal_plan_day)
            await session.flush()

            # Создаем приемы пищи
            for meal_order, meal_data in enumerate(day_data.get("meals", []), 1):
                planned_meal = PlannedMeal(
                    meal_plan_day_id=meal_plan_day.id,
                    meal_type=meal_data.get("meal_type", "breakfast"),
                    meal_order=meal_order,
                    recipe_name=meal_data.get("recipe_name", ""),
                    ingredients=meal_data.get("ingredients", []),
                    calories=meal_data.get("calories", 0),
                    proteins=meal_data.get("proteins", 0),
                    fats=meal_data.get("fats", 0),
                    carbs=meal_data.get("carbs", 0),
                    cooking_instructions=meal_data.get("cooking_instructions", ""),
                    cooking_time_minutes=meal_data.get("cooking_time_minutes", 0),
                    serving_size=meal_data.get("serving_size", "1 порция"),
                )

                session.add(planned_meal)

        await session.commit()
        logger.info(f"Meal plan created for user {user_id}: {meal_plan.id}")

        return meal_plan

    @staticmethod
    def _build_meal_plan_prompt(user: User, period_type: PlanPeriod, days_count: int) -> str:
        """Формирование промпта для генерации плана питания"""

        # Маппинг бюджетных категорий
        budget_descriptions = {
            "economy": "Эконом (бюджетные продукты, простые рецепты, средняя цена продуктов: 100-150₽ на прием пищи)",
            "normal": "Норм (средний бюджет, разнообразные продукты, средняя цена: 200-300₽ на прием пищи)",
            "premium": "Премиум (высокий бюджет, качественные продукты, деликатесы, средняя цена: 400-600₽ на прием пищи)"
        }

        budget_desc = budget_descriptions.get(user.budget_category.value if user.budget_category else "normal", budget_descriptions["normal"])

        # Маппинг целей
        goal_descriptions = {
            "weight_loss": "Похудение (дефицит калорий)",
            "weight_gain": "Набор массы (профицит калорий)",
            "maintenance": "Поддержание веса",
            "health": "Здоровое питание"
        }

        goal_desc = goal_descriptions.get(user.goal.value if user.goal else "health", "Здоровое питание")

        # Маппинг типов диеты
        diet_descriptions = {
            "omnivore": "Всеядный (все продукты)",
            "vegetarian": "Вегетарианец (без мяса и рыбы)",
            "vegan": "Веган (только растительная пища)",
            "pescatarian": "Пескетарианец (рыба разрешена, мясо нет)"
        }

        diet_desc = diet_descriptions.get(user.diet_type.value if user.diet_type else "omnivore", "Всеядный")

        # Формируем информацию об аллергиях
        allergies_text = ""
        if user.allergies and len(user.allergies) > 0:
            allergies_text = f"\n❗ АЛЛЕРГИИ/ИСКЛЮЧЕНИЯ: {', '.join(user.allergies)}"

        period_text = {
            PlanPeriod.DAY: "на 1 день",
            PlanPeriod.WEEK: "на 7 дней (неделю)",
            PlanPeriod.MONTH: "на 30 дней (месяц)"
        }[period_type]

        prompt = f"""Ты профессиональный диетолог и нутрициолог. Создай детальный план питания {period_text} для пользователя.

📊 ПАРАМЕТРЫ ПОЛЬЗОВАТЕЛЯ:
- Имя: {user.preferred_name or "Пользователь"}
- Пол: {"Мужской" if user.gender.value == "male" else "Женский"}
- Возраст: {user.age} лет
- Рост: {user.height} см
- Текущий вес: {user.current_weight} кг
- Целевой вес: {user.target_weight} кг
- Цель: {goal_desc}
- Тип питания: {diet_desc}
- Бюджет: {budget_desc}{allergies_text}

🎯 ЦЕЛЕВЫЕ ПОКАЗАТЕЛИ НА ДЕНЬ:
- Калории: {user.target_calories} ккал
- Белки: {user.target_proteins}г
- Жиры: {user.target_fats}г
- Углеводы: {user.target_carbs}г

📋 ТРЕБОВАНИЯ К ПЛАНУ:

1. Создай план на {days_count} {"день" if days_count == 1 else "дней"}
2. Для каждого дня предусмотри 4 приема пищи: завтрак, обед, ужин, перекус
3. Каждый прием пищи должен содержать:
   - Название блюда
   - Список ингредиентов с количеством (в граммах)
   - Точные КБЖУ (калории, белки, жиры, углеводы)
   - Краткую инструкцию по приготовлению
   - Время приготовления (в минутах)
   - Размер порции

4. ВАЖНО:
   - Соблюдай бюджетную категорию "{user.budget_category.value if user.budget_category else "normal"}"
   - Строго соблюдай тип питания "{user.diet_type.value if user.diet_type else "omnivore"}"
   - Исключи все аллергены: {user.allergies if user.allergies else "нет"}
   - Суммарные КБЖУ за день должны быть близки к целевым показателям (±50 ккал)
   - Рецепты должны быть реалистичными и легко воспроизводимыми
   - Учитывай доступность продуктов в России

5. Разнообразие: каждый день должен быть уникальным, избегай повторений блюд

ФОРМАТ ОТВЕТА (СТРОГО JSON):
{{
  "days": [
    {{
      "day_number": 1,
      "total_calories": 2000,
      "total_proteins": 150,
      "total_fats": 65,
      "total_carbs": 200,
      "meals": [
        {{
          "meal_type": "breakfast",
          "recipe_name": "Овсяная каша с бананом и орехами",
          "calories": 450,
          "proteins": 15,
          "fats": 12,
          "carbs": 68,
          "serving_size": "1 порция (300г)",
          "cooking_time_minutes": 10,
          "ingredients": [
            {{"name": "Овсяные хлопья", "quantity": 80, "unit": "г"}},
            {{"name": "Молоко 2.5%", "quantity": 200, "unit": "мл"}},
            {{"name": "Банан", "quantity": 100, "unit": "г"}},
            {{"name": "Грецкие орехи", "quantity": 20, "unit": "г"}},
            {{"name": "Мёд", "quantity": 10, "unit": "г"}}
          ],
          "cooking_instructions": "1. Залить овсяные хлопья молоком и варить 5 минут. 2. Добавить нарезанный банан. 3. Посыпать измельченными орехами и полить медом."
        }},
        // ... остальные приемы пищи (lunch, dinner, snack)
      ]
    }}
    // ... остальные дни
  ]
}}

Верни ТОЛЬКО валидный JSON, без дополнительного текста или объяснений."""

        return prompt

    @staticmethod
    def _parse_ai_meal_plan(ai_response: str) -> Dict:
        """
        Парсинг ответа AI с планом питания

        Args:
            ai_response: Ответ от AI

        Returns:
            Dict: Структурированный план питания
        """
        try:
            # Пытаемся найти JSON в ответе
            start_idx = ai_response.find("{")
            end_idx = ai_response.rfind("}") + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("JSON not found in AI response")

            json_str = ai_response[start_idx:end_idx]
            plan_data = json.loads(json_str)

            return plan_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI meal plan response: {e}")
            logger.error(f"AI response: {ai_response[:500]}...")
            raise ValueError("Invalid JSON format in AI response")

    @staticmethod
    async def get_active_meal_plan(session: AsyncSession, user_id: int) -> Optional[MealPlan]:
        """Получить активный план питания пользователя"""
        result = await session.execute(
            select(MealPlan)
            .where(and_(
                MealPlan.user_id == user_id,
                MealPlan.is_active == 1,
                MealPlan.end_date >= date.today()
            ))
            .order_by(MealPlan.created_at.desc())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_meal_plan_by_id(session: AsyncSession, plan_id: int) -> Optional[MealPlan]:
        """Получить план питания по ID"""
        result = await session.execute(
            select(MealPlan).where(MealPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_meal_plan_days(
        session: AsyncSession,
        meal_plan_id: int
    ) -> List[MealPlanDay]:
        """Получить все дни плана питания"""
        result = await session.execute(
            select(MealPlanDay)
            .where(MealPlanDay.meal_plan_id == meal_plan_id)
            .order_by(MealPlanDay.day_number)
        )
        return result.scalars().all()

    @staticmethod
    async def get_day_meals(
        session: AsyncSession,
        day_id: int
    ) -> List[PlannedMeal]:
        """Получить все приемы пищи для дня"""
        result = await session.execute(
            select(PlannedMeal)
            .where(PlannedMeal.meal_plan_day_id == day_id)
            .order_by(PlannedMeal.meal_order)
        )
        return result.scalars().all()

    @staticmethod
    async def deactivate_old_plans(session: AsyncSession, user_id: int):
        """Деактивировать старые планы питания пользователя"""
        result = await session.execute(
            select(MealPlan).where(and_(
                MealPlan.user_id == user_id,
                MealPlan.is_active == 1
            ))
        )
        old_plans = result.scalars().all()

        for plan in old_plans:
            plan.is_active = 0

        await session.commit()
        logger.info(f"Deactivated {len(old_plans)} old meal plans for user {user_id}")
