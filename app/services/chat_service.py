"""
Сервис для работы с историей AI-чата
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Dict
from datetime import datetime

from app.models.chat import ChatMessage, MessageRole
from app.models.user import User


class ChatService:
    """Сервис для управления историей чата"""

    @staticmethod
    async def save_message(
        session: AsyncSession,
        user_id: int,
        role: MessageRole,
        content: str,
        tokens_used: int = None
    ) -> ChatMessage:
        """
        Сохранить сообщение в историю

        Args:
            session: Сессия БД
            user_id: ID пользователя
            role: Роль отправителя (user/assistant)
            content: Содержимое сообщения
            tokens_used: Использовано токенов

        Returns:
            Созданное сообщение
        """
        message = ChatMessage(
            user_id=user_id,
            role=role,
            content=content,
            tokens_used=tokens_used
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)

        return message

    @staticmethod
    async def get_chat_history(
        session: AsyncSession,
        user_id: int,
        limit: int = 10
    ) -> List[ChatMessage]:
        """
        Получить историю чата пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя
            limit: Количество последних сообщений

        Returns:
            Список сообщений (от старых к новым)
        """
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        messages = result.scalars().all()

        # Возвращаем в правильном порядке (от старых к новым)
        return list(reversed(messages))

    @staticmethod
    async def get_chat_context(
        session: AsyncSession,
        user_id: int,
        message_limit: int = 10
    ) -> List[Dict]:
        """
        Получить контекст для отправки в Claude API

        Args:
            session: Сессия БД
            user_id: ID пользователя
            message_limit: Количество последних сообщений для контекста

        Returns:
            Список словарей формата {"role": "...", "content": "..."}
        """
        messages = await ChatService.get_chat_history(session, user_id, message_limit)

        return [msg.to_dict() for msg in messages]

    @staticmethod
    async def get_user_context(
        session: AsyncSession,
        user_id: int
    ) -> Dict:
        """
        Получить ПОЛНЫЙ контекст пользователя для персонализации ответов
        Включает реальные данные из дневника питания, медицинские данные,
        историю питания и самочувствия

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Словарь с данными пользователя
        """
        from datetime import date, timedelta
        from app.services.meal_service import MealService
        from app.models.meal_plan import MealPlan
        from app.models.meal import Meal, MealFood
        from app.models.wellness_log import WellnessLog
        from sqlalchemy import and_, desc
        from sqlalchemy.orm import selectinload

        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {}

        # Получаем реальные данные из дневника питания за сегодня
        today_totals = await MealService.get_daily_totals(session, user_id, date.today())

        # Получаем прогресс (включая remaining)
        progress = await MealService.get_nutrition_progress(session, user_id, date.today())

        # Получаем активный план питания
        result_plan = await session.execute(
            select(MealPlan).where(
                and_(
                    MealPlan.user_id == user_id,
                    MealPlan.is_active == True,
                    MealPlan.start_date <= date.today(),
                    MealPlan.end_date >= date.today()
                )
            ).limit(1)
        )
        active_plan = result_plan.scalar_one_or_none()

        # Получаем последние 5 приемов пищи с деталями
        result_meals = await session.execute(
            select(Meal)
            .options(selectinload(Meal.foods))
            .where(Meal.user_id == user_id)
            .order_by(desc(Meal.meal_time))
            .limit(5)
        )
        recent_meals = result_meals.scalars().all()

        # Формируем описание недавних приемов пищи
        recent_meals_text = []
        for meal in recent_meals:
            meal_type_names = {
                "breakfast": "Завтрак",
                "lunch": "Обед",
                "dinner": "Ужин",
                "snack": "Перекус"
            }
            meal_type = meal_type_names.get(meal.meal_type.value if meal.meal_type else "", "Прием пищи")
            meal_date = meal.meal_date.strftime("%d.%m")
            meal_time = meal.meal_time.strftime("%H:%M") if meal.meal_time else ""

            foods_list = []
            for food in meal.foods:
                foods_list.append(f"{food.name} ({food.calories} ккал)")

            if foods_list:
                foods_str = ", ".join(foods_list)
                recent_meals_text.append(f"{meal_date} {meal_time} {meal_type}: {foods_str}")

        # Получаем последние 3 wellness logs
        result_wellness = await session.execute(
            select(WellnessLog)
            .where(WellnessLog.user_id == user_id)
            .order_by(desc(WellnessLog.created_at))
            .limit(3)
        )
        wellness_logs = result_wellness.scalars().all()

        # Формируем описание самочувствия
        wellness_text = []
        for log in wellness_logs:
            log_date = log.created_at.strftime("%d.%m %H:%M")
            energy = log.energy_level or "?"
            mood = log.mood or "?"
            digestion = log.digestive_comfort or "?"
            symptoms = ", ".join(log.physical_symptoms) if log.physical_symptoms else "нет"
            wellness_text.append(
                f"{log_date}: энергия {energy}/5, настроение {mood}/5, пищеварение {digestion}/5, симптомы: {symptoms}"
            )

        context = {
            # Базовая информация
            "preferred_name": user.preferred_name or user.first_name or "друг",
            "age": user.age,
            "gender": user.gender.value if user.gender else None,
            "height": user.height,
            "current_weight": user.current_weight,
            "target_weight": user.target_weight,
            "goal": user.goal.value if user.goal else None,
            "activity_level": user.activity_level.value if user.activity_level else None,
            "country": user.country,
            "city": user.city,

            # Целевые значения
            "target_calories": user.target_calories,
            "target_proteins": user.target_proteins,
            "target_fats": user.target_fats,
            "target_carbs": user.target_carbs,

            # Предпочтения и ограничения
            "diet_type": user.diet_type.value if user.diet_type else None,
            "allergies": user.allergies or [],
            "dislikes": user.dislikes or [],
            "budget_category": user.budget_category.value if user.budget_category else None,
            "preferred_cooking_time_minutes": user.preferred_cooking_time_minutes,

            # Дневная статистика из РЕАЛЬНОГО дневника питания
            "today_calories": today_totals["calories"],
            "today_proteins": round(today_totals["proteins"], 1),
            "today_fats": round(today_totals["fats"], 1),
            "today_carbs": round(today_totals["carbs"], 1),

            # Оставшиеся калории и макросы
            "remaining_calories": progress["remaining"]["calories"],
            "remaining_proteins": round(progress["remaining"]["proteins"], 1),
            "remaining_fats": round(progress["remaining"]["fats"], 1),
            "remaining_carbs": round(progress["remaining"]["carbs"], 1),

            # Информация об активном плане
            "has_active_plan": active_plan is not None,
            "plan_period": active_plan.period if active_plan else None,

            # Недавние приемы пищи
            "recent_meals": recent_meals_text,

            # История самочувствия
            "recent_wellness": wellness_text
        }

        # Добавляем информацию о запланированных приемах пищи на сегодня
        if active_plan and active_plan.plan_data:
            try:
                plan_data = active_plan.plan_data
                today = date.today()

                # Получаем список приемов пищи на сегодня
                if active_plan.period == "day":
                    meals = plan_data.get("meals", [])
                else:
                    days = plan_data.get("days", [])
                    current_day = None
                    for day in days:
                        if day.get("date") == today.isoformat():
                            current_day = day
                            break
                    meals = current_day.get("meals", []) if current_day else []

                # Формируем краткое описание плана на сегодня
                if meals:
                    plan_summary = []
                    for meal in meals:
                        meal_type = meal.get("type", "")
                        dishes = meal.get("dishes", [])
                        dish_names = [d.get("name") for d in dishes if d.get("name")]
                        if dish_names:
                            plan_summary.append(f"{meal_type}: {', '.join(dish_names)}")

                    context["today_plan_summary"] = "; ".join(plan_summary)
            except Exception:
                pass

        # Добавляем интересные факты о питании и самочувствии
        try:
            from app.models.insight_fact import InsightFact

            result_insights = await session.execute(
                select(InsightFact).where(
                    and_(
                        InsightFact.user_id == user_id,
                        InsightFact.is_active == True
                    )
                ).order_by(desc(InsightFact.confidence_level)).limit(5)
            )
            insights = result_insights.scalars().all()

            if insights:
                insight_texts = []
                for insight in insights:
                    impact = "положительно влияет на" if insight.impact_direction == "positive" else "негативно влияет на"
                    metric_names = {
                        "energy_level": "энергию",
                        "mood": "настроение",
                        "digestive_comfort": "пищеварение",
                        "mental_clarity": "ясность ума",
                        "sleep_quality": "сон",
                        "stress_level": "стресс"
                    }
                    metric = metric_names.get(insight.wellness_metric, insight.wellness_metric)
                    confidence = int(insight.confidence_level * 100)

                    insight_text = f"{insight.food_name} {impact} {metric} (достоверность {confidence}%)"
                    if insight.scientific_explanation:
                        insight_text += f" - {insight.scientific_explanation[:100]}..."

                    insight_texts.append(insight_text)

                context["personal_insights"] = insight_texts
        except Exception as e:
            logger.warning(f"Failed to load personal insights: {repr(e)}")

        return context

    @staticmethod
    async def clear_chat_history(
        session: AsyncSession,
        user_id: int
    ) -> int:
        """
        Очистить историю чата пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Количество удаленных сообщений
        """
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.user_id == user_id)
        )
        messages = result.scalars().all()
        count = len(messages)

        for message in messages:
            await session.delete(message)

        await session.commit()

        return count

    @staticmethod
    async def get_total_messages_count(
        session: AsyncSession,
        user_id: int
    ) -> int:
        """
        Получить общее количество сообщений пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Количество сообщений
        """
        result = await session.execute(
            select(ChatMessage).where(ChatMessage.user_id == user_id)
        )
        messages = result.scalars().all()

        return len(messages)
