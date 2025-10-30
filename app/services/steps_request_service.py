"""
Сервис для запроса количества шагов у пользователей в конце дня
"""
from datetime import date, datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from app.models.user import User
from app.models.user_steps import UserSteps
from app.db.session import async_session_maker


class StepsRequestService:
    """Сервис для запроса количества шагов у пользователей"""

    @staticmethod
    async def request_daily_steps(bot: Bot, current_time: str):
        """
        Запрашивает у всех активных пользователей количество шагов за день

        Args:
            bot: Telegram bot instance
            current_time: Текущее время в формате HH:MM
        """
        try:
            # Устанавливаем время запроса (например, 22:00)
            REQUEST_TIME = "22:00"

            if current_time != REQUEST_TIME:
                return

            async with async_session_maker() as session:
                # Получаем всех активных пользователей, которые завершили онбординг
                result = await session.execute(
                    select(User).where(
                        User.onboarding_completed == True,
                        User.is_active == True,
                        User.is_blocked == False
                    )
                )
                users = result.scalars().all()

                logger.info(f"Requesting daily steps from {len(users)} users at {current_time}")

                today = date.today()

                for user in users:
                    try:
                        # Проверяем, ввел ли пользователь уже шаги за сегодня
                        steps_result = await session.execute(
                            select(UserSteps).where(
                                UserSteps.user_id == user.id,
                                UserSteps.date == today
                            )
                        )
                        existing_steps = steps_result.scalar_one_or_none()

                        # Если уже ввел - пропускаем
                        if existing_steps:
                            logger.debug(f"User {user.id} already logged steps for today")
                            continue

                        # Отправляем запрос
                        await StepsRequestService._send_steps_request(bot, user)

                    except Exception as e:
                        logger.error("Error requesting steps from user {user.id}: %s", str(e))

        except Exception as e:
            logger.error("Error in request_daily_steps: %s", str(e))

    @staticmethod
    async def _send_steps_request(bot: Bot, user: User):
        """
        Отправляет запрос на ввод шагов конкретному пользователю

        Args:
            bot: Telegram bot instance
            user: Объект пользователя
        """
        try:
            # Формируем персонализированное сообщение
            name = user.preferred_name or user.first_name or "Друг"

            text = f"""
👋 <b>{name}, день подходит к концу!</b>

📊 Сколько шагов ты сегодня прошел?

Это поможет мне точнее рассчитать твои потребности в калориях на завтра!
Чем больше активности - тем больше можно съесть 🍽️

Просто введи число (например: 8500) или выбери примерный диапазон:
"""

            keyboard = [
                [
                    InlineKeyboardButton("< 3000 шагов", callback_data="steps_range_1500"),
                    InlineKeyboardButton("3000-5000", callback_data="steps_range_4000")
                ],
                [
                    InlineKeyboardButton("5000-8000", callback_data="steps_range_6500"),
                    InlineKeyboardButton("8000-12000", callback_data="steps_range_10000")
                ],
                [
                    InlineKeyboardButton("12000+ шагов", callback_data="steps_range_15000")
                ],
                [
                    InlineKeyboardButton("⏭️ Пропустить", callback_data="steps_skip")
                ]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)

            await bot.send_message(
                chat_id=user.telegram_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            logger.info(f"Sent steps request to user {user.id}")

        except Exception as e:
            logger.error("Error sending steps request to user {user.id}: %s", str(e))

    @staticmethod
    def get_steps_from_range(range_value: str) -> int:
        """
        Получить среднее значение шагов из диапазона

        Args:
            range_value: Значение диапазона (например, "steps_range_4000")

        Returns:
            Среднее количество шагов
        """
        range_mapping = {
            "steps_range_1500": 1500,
            "steps_range_4000": 4000,
            "steps_range_6500": 6500,
            "steps_range_10000": 10000,
            "steps_range_15000": 15000
        }
        return range_mapping.get(range_value, 0)
