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
        Получить контекст пользователя для персонализации ответов
        Включает реальные данные из дневника питания за сегодня и активный план

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Словарь с данными пользователя
        """
        from datetime import date
        from app.services.meal_service import MealService
        from app.models.meal_plan import MealPlan
        from sqlalchemy import and_

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

        context = {
            "preferred_name": user.preferred_name or user.first_name or "друг",
            "age": user.age,
            "gender": user.gender.value if user.gender else None,
            "current_weight": user.current_weight,
            "target_weight": user.target_weight,
            "goal": user.goal.value if user.goal else None,
            "activity_level": user.activity_level.value if user.activity_level else None,
            "target_calories": user.target_calories,
            "target_proteins": user.target_proteins,
            "target_fats": user.target_fats,
            "target_carbs": user.target_carbs,
            "diet_type": user.diet_type.value if user.diet_type else None,
            "allergies": user.allergies or [],
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
            "plan_period": active_plan.period if active_plan else None
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
