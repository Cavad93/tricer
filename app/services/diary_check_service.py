"""
Сервис для проверки заполненности дневника питания
"""
from datetime import date, datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from telegram import Bot

from app.models.user import User
from app.models.meal import Meal
from app.services.claude_ai import ClaudeAIService
from app.db.session import async_session_maker
from loguru import logger


class DiaryCheckService:
    """Сервис для проверки и напоминаний о заполнении дневника"""

    @staticmethod
    async def check_and_notify_incomplete_diaries(bot: Bot, current_time: str):
        """
        Проверяет дневники всех пользователей и отправляет напоминания при необходимости

        Args:
            bot: Telegram bot instance
            current_time: Текущее время в формате HH:MM
        """
        try:
            async with async_session_maker() as session:
                # Получаем всех пользователей с включенной проверкой дневника на это время
                result = await session.execute(
                    select(User).where(
                        User.diary_check_enabled == True,
                        User.diary_check_time == current_time,
                        User.is_active == True,
                        User.is_blocked == False
                    )
                )
                users = result.scalars().all()

                logger.info(f"Checking diaries for {len(users)} users at {current_time}")

                for user in users:
                    try:
                        await DiaryCheckService._check_user_diary(bot, user, session)
                    except Exception as e:
                        logger.error("Error checking diary for user {user.id}: {}", repr(e))

        except Exception as e:
            logger.error("Error in check_and_notify_incomplete_diaries: {}", repr(e))

    @staticmethod
    async def _check_user_diary(bot: Bot, user: User, session: AsyncSession):
        """
        Проверяет дневник конкретного пользователя и отправляет уведомление при необходимости

        Args:
            bot: Telegram bot instance
            user: Объект пользователя
            session: Сессия БД
        """
        try:
            today = date.today()

            # Получаем все приемы пищи пользователя за сегодня
            result = await session.execute(
                select(Meal)
                .options(selectinload(Meal.foods))
                .where(Meal.user_id == user.id, Meal.meal_date == today)
            )
            meals = result.scalars().all()

            # Рассчитываем сумму калорий за день
            total_calories = sum(meal.calories for meal in meals if meal.calories)

            # Рассчитываем процент от целевых калорий
            if not user.target_calories or user.target_calories == 0:
                logger.warning(f"User {user.id} has no target calories set")
                return

            calorie_percent = (total_calories / user.target_calories) * 100
            calorie_deficit_percent = 100 - calorie_percent

            # Если дефицит больше 30% - отправляем уведомление
            if calorie_deficit_percent > 30:
                logger.info(
                    f"User {user.id} has {calorie_deficit_percent:.0f}% calorie deficit "
                    f"({total_calories}/{user.target_calories} kcal)"
                )

                # Генерируем персонализированное сообщение через AI
                message = await DiaryCheckService._generate_diary_reminder_message(
                    user=user,
                    total_calories=total_calories,
                    meals_count=len(meals),
                    session=session
                )

                # Отправляем сообщение
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message,
                    parse_mode='HTML'
                )

                logger.info(f"Sent diary reminder to user {user.id}")

        except Exception as e:
            logger.error("Error in _check_user_diary for user {user.id}: {}", repr(e))
            raise

    @staticmethod
    async def _generate_diary_reminder_message(
        user: User,
        total_calories: int,
        meals_count: int,
        session: AsyncSession
    ) -> str:
        """
        Генерирует персонализированное напоминание о заполнении дневника через AI

        Args:
            user: Объект пользователя
            total_calories: Сумма калорий за день
            meals_count: Количество приемов пищи
            session: Сессия БД

        Returns:
            Текст сообщения
        """
        try:
            calorie_deficit = user.target_calories - total_calories
            deficit_percent = (calorie_deficit / user.target_calories) * 100

            # Формируем промпт для AI
            prompt = f"""
Пользователь не полностью заполнил дневник питания. Сгенерируй мягкое напоминание (3-4 предложения).

КОНТЕКСТ:
- Имя: {user.preferred_name or user.first_name}
- Целевые калории: {user.target_calories} ккал/день
- Записано за сегодня: {total_calories} ккал
- Дефицит: {calorie_deficit} ккал ({deficit_percent:.0f}%)
- Количество приемов пищи: {meals_count}
- Цель: {user.goal.value if user.goal else 'не указана'}

ЗАДАЧА: Напомни о важности полного дневника!
- Используй дружелюбный тон и эмодзи (📝, 🍽️, 📊)
- Объясни почему важно записывать ВСЕ приемы пищи:
  * Точный подсчет калорий и КБЖУ
  * Понимание реального рациона
  * Выявление паттернов питания
  * Достижение целей по весу
  * AI-анализ работает лучше с полными данными
- Если цель - похудение, объясни что недоедание вредно
- НЕ критикуй, а мягко мотивируй
- Попроси добавить пропущенные приемы пищи

Формат: 3-4 предложения, начни с приветствия и эмодзи."""

            # Генерируем через AI
            ai_response = await ClaudeAIService.chat(
                user_id=user.id,
                message=prompt,
                session=session,
                system_override="Ты заботливый AI-нутрициолог, который мягко напоминает о важности ведения дневника питания."
            )

            return ai_response.strip()

        except Exception as e:
            logger.error("Error generating diary reminder message: {}", repr(e))
            # Fallback сообщение
            return (
                f"📝 <b>Привет, {user.preferred_name or user.first_name}!</b>\n\n"
                f"Похоже, ты записал только {total_calories} ккал из {user.target_calories} ккал сегодня. "
                f"Не забудь добавить все приемы пищи в дневник!\n\n"
                f"Это важно для:\n"
                f"• Точного подсчета калорий и БЖУ\n"
                f"• Анализа твоего рациона\n"
                f"• Достижения целей по весу\n\n"
                f"Добавь пропущенные приемы пищи через главное меню! 🍽️"
            )

    @staticmethod
    async def get_diary_completion_stats(user_id: int, session: AsyncSession) -> dict:
        """
        Получает статистику заполненности дневника пользователя

        Args:
            user_id: ID пользователя
            session: Сессия БД

        Returns:
            Словарь со статистикой
        """
        try:
            today = date.today()

            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return {"error": "User not found"}

            # Получаем приемы пищи за сегодня
            result = await session.execute(
                select(Meal)
                .where(Meal.user_id == user_id, Meal.meal_date == today)
            )
            meals = result.scalars().all()

            total_calories = sum(meal.calories for meal in meals if meal.calories)
            total_proteins = sum(meal.proteins for meal in meals if meal.proteins)
            total_fats = sum(meal.fats for meal in meals if meal.fats)
            total_carbs = sum(meal.carbs for meal in meals if meal.carbs)

            completion_percent = 0
            if user.target_calories and user.target_calories > 0:
                completion_percent = (total_calories / user.target_calories) * 100

            return {
                "meals_count": len(meals),
                "total_calories": total_calories,
                "target_calories": user.target_calories,
                "completion_percent": completion_percent,
                "deficit_percent": max(0, 100 - completion_percent),
                "total_proteins": total_proteins,
                "total_fats": total_fats,
                "total_carbs": total_carbs,
                "target_proteins": user.target_proteins,
                "target_fats": user.target_fats,
                "target_carbs": user.target_carbs
            }

        except Exception as e:
            logger.error("Error getting diary completion stats: {}", repr(e))
            return {"error": str(e)}
