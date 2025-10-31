"""
Сервис для отправки напоминаний о приемах пищи
"""
from datetime import datetime, time
from typing import Optional, List, Tuple, Dict
from loguru import logger
from sqlalchemy import select, or_
from telegram import Bot
from telegram.error import TelegramError

from app.models.user import User
from app.models.meal import MealType
from app.models.meal_plan import MealPlan, MealPlanDay, PlannedMeal
from app.db.session import async_session_maker
from app.bot.texts import FriendlyPhrases
from app.services.diary_check_service import DiaryCheckService
from app.bot.keyboards import main_menu_keyboard


class ReminderService:
    """Сервис для работы с напоминаниями о приемах пищи"""

    @staticmethod
    async def send_all_reminders_for_time(bot: Bot, target_time: str):
        """
        ОПТИМИЗИРОВАННЫЙ метод: отправляет ВСЕ типы напоминаний за ОДИН запрос к БД

        Делает один запрос для получения всех пользователей, у которых:
        - Напоминания о еде (breakfast/lunch/dinner/snack) на это время
        - Проверка дневника на это время

        Вместо 6 запросов к БД делает 1 запрос.

        Args:
            bot: Telegram bot instance
            target_time: Время в формате HH:MM
        """
        try:
            async with async_session_maker() as session:
                # ОПТИМИЗАЦИЯ: Один запрос для всех типов напоминаний + diary check
                result = await session.execute(
                    select(User).where(
                        or_(
                            # Meal reminders
                            (User.reminders_enabled == True) & (User.breakfast_reminder_time == target_time),
                            (User.reminders_enabled == True) & (User.lunch_reminder_time == target_time),
                            (User.reminders_enabled == True) & (User.dinner_reminder_time == target_time),
                            (User.reminders_enabled == True) & (User.snack_reminder_time == target_time),
                            # Diary check
                            (User.diary_check_enabled == True) & (User.diary_check_time == target_time)
                        ),
                        User.is_active == True,
                        User.is_blocked == False
                    )
                )
                users = result.scalars().all()

                if not users:
                    # Нет пользователей с напоминаниями на это время - не логируем (спам в логах)
                    return

                logger.info(f"Found {len(users)} users with reminders/checks at {target_time}")

                # Группируем пользователей по типу напоминания
                breakfast_users = []
                lunch_users = []
                dinner_users = []
                snack_users = []
                diary_check_users = []

                for user in users:
                    # Meal reminders
                    if user.reminders_enabled:
                        if user.breakfast_reminder_time == target_time:
                            breakfast_users.append(user)
                        if user.lunch_reminder_time == target_time:
                            lunch_users.append(user)
                        if user.dinner_reminder_time == target_time:
                            dinner_users.append(user)
                        if user.snack_reminder_time == target_time:
                            snack_users.append(user)

                    # Diary check
                    if user.diary_check_enabled and user.diary_check_time == target_time:
                        diary_check_users.append(user)

                # Отправляем напоминания по типам
                if breakfast_users:
                    logger.info(f"Sending breakfast reminders to {len(breakfast_users)} users")
                    for user in breakfast_users:
                        await ReminderService.send_meal_reminder(bot, user, MealType.BREAKFAST)

                if lunch_users:
                    logger.info(f"Sending lunch reminders to {len(lunch_users)} users")
                    for user in lunch_users:
                        await ReminderService.send_meal_reminder(bot, user, MealType.LUNCH)

                if dinner_users:
                    logger.info(f"Sending dinner reminders to {len(dinner_users)} users")
                    for user in dinner_users:
                        await ReminderService.send_meal_reminder(bot, user, MealType.DINNER)

                if snack_users:
                    logger.info(f"Sending snack reminders to {len(snack_users)} users")
                    for user in snack_users:
                        await ReminderService.send_meal_reminder(bot, user, MealType.SNACK)

                # Проверяем дневники
                if diary_check_users:
                    logger.info(f"Checking diaries for {len(diary_check_users)} users")
                    for user in diary_check_users:
                        try:
                            await DiaryCheckService._check_user_diary(bot, user, session)
                        except Exception as e:
                            logger.error("Error checking diary for user {}: {}", user.id, repr(e))

        except Exception as e:
            logger.error("Error in send_all_reminders_for_time: {}", repr(e))

    @staticmethod
    async def send_meal_reminder(bot: Bot, user: User, meal_type: MealType):
        """
        Отправить напоминание о приеме пищи конкретному пользователю

        Args:
            bot: Telegram bot instance
            user: Пользователь
            meal_type: Тип приема пищи
        """
        try:
            # Проверяем, включены ли напоминания
            if not user.reminders_enabled:
                return

            # Определяем название и эмодзи приема пищи
            meal_names = {
                MealType.BREAKFAST: ("завтрак", "🌅"),
                MealType.LUNCH: ("обед", "🌞"),
                MealType.DINNER: ("ужин", "🌙"),
                MealType.SNACK: ("перекус", "🍎")
            }

            meal_name, emoji = meal_names.get(meal_type, ("прием пищи", "🍽"))

            # Получаем активный план питания и блюда на сегодня
            async with async_session_maker() as session:
                today = datetime.now().date()

                # Получаем активный план на сегодня
                result = await session.execute(
                    select(MealPlan).where(
                        MealPlan.user_id == user.id,
                        MealPlan.is_active == True,
                        MealPlan.start_date <= today,
                        MealPlan.end_date >= today
                    ).limit(1)
                )
                active_plan = result.scalar_one_or_none()

                planned_meals = []
                if active_plan:
                    # Получаем день плана для сегодняшней даты
                    day_result = await session.execute(
                        select(MealPlanDay).where(
                            MealPlanDay.meal_plan_id == active_plan.id,
                            MealPlanDay.day_date == today
                        ).limit(1)
                    )
                    meal_plan_day = day_result.scalar_one_or_none()

                    if meal_plan_day:
                        # Получаем запланированные приемы пищи на сегодня
                        meals_result = await session.execute(
                            select(PlannedMeal).where(
                                PlannedMeal.meal_plan_day_id == meal_plan_day.id,
                                PlannedMeal.meal_type == meal_type.value
                            )
                        )
                        planned_meals = meals_result.scalars().all()

            # Формируем сообщение
            if planned_meals:
                # Есть запланированные блюда для этого приема пищи
                message = (
                    f"{emoji} <b>Время для приема пищи: {meal_name}!</b>\n\n"
                    f"📋 <b>Запланировано:</b>\n"
                )

                total_calories = 0
                total_proteins = 0
                total_fats = 0
                total_carbs = 0

                for meal in planned_meals:
                    message += f"• {meal.recipe_name}\n"
                    total_calories += meal.calories or 0
                    total_proteins += meal.proteins or 0
                    total_fats += meal.fats or 0
                    total_carbs += meal.carbs or 0

                if total_calories > 0:
                    message += (
                        f"\n📊 <b>КБЖУ:</b>\n"
                        f"🔥 {total_calories} ккал | "
                        f"Б: {total_proteins:.0f}г | "
                        f"Ж: {total_fats:.0f}г | "
                        f"У: {total_carbs:.0f}г\n"
                    )

                message += f"\n{FriendlyPhrases.get_encouragement()}"

            elif active_plan:
                # План есть, но нет блюда для этого приема пищи на сегодня
                message = (
                    f"{emoji} <b>Время для приема пищи: {meal_name}!</b>\n\n"
                    f"💡 В твоем плане не запланирован {meal_name} на сегодня.\n"
                    f"Но если проголодаешься - я всегда помогу подобрать что-то полезное!\n\n"
                    f"{FriendlyPhrases.get_encouragement()}"
                )
            else:
                # Нет активного плана
                message = (
                    f"{emoji} <b>Время для приема пищи: {meal_name}!</b>\n\n"
                    f"💡 У тебя пока нет активного плана питания.\n"
                    f"Создать план можно через 🍽 <b>Рацион</b> в главном меню.\n\n"
                    f"А пока можешь:\n"
                    f"📸 Сфотографировать еду для распознавания\n"
                    f"💬 Спросить меня о питании в AI-чате\n\n"
                    f"{FriendlyPhrases.get_encouragement()}"
                )

            # Отправляем уведомление
            await bot.send_message(
                chat_id=user.telegram_id,
                text=message,
                parse_mode='HTML'
            )

            # Отправляем клавиатуру отдельным сообщением, чтобы она спускалась вниз
            await bot.send_message(
                chat_id=user.telegram_id,
                text="Что будем делать?",
                reply_markup=main_menu_keyboard()
            )

            logger.info(f"Meal reminder sent to user {user.telegram_id} for {meal_type.value}")

        except TelegramError as e:
            logger.error("Telegram error sending reminder to user {}: {}", user.telegram_id, repr(e))
            # Если пользователь заблокировал бота, отключаем напоминания
            if "blocked" in str(e).lower() or "chat not found" in str(e).lower():
                async with async_session_maker() as session:
                    user.reminders_enabled = False
                    session.add(user)
                    await session.commit()
                    logger.info(f"Disabled reminders for user {user.telegram_id} (bot blocked)")
        except Exception as e:
            logger.error("Error sending reminder to user {}: {}", user.telegram_id, repr(e))

    @staticmethod
    async def send_reminders_for_meal_type(bot: Bot, meal_type: MealType, target_time: str):
        """
        Отправить напоминания всем пользователям, у которых настроено время для этого приема пищи

        Args:
            bot: Telegram bot instance
            meal_type: Тип приема пищи
            target_time: Время в формате HH:MM
        """
        try:
            async with async_session_maker() as session:
                # Определяем поле времени в зависимости от типа приема пищи
                time_field_map = {
                    MealType.BREAKFAST: User.breakfast_reminder_time,
                    MealType.LUNCH: User.lunch_reminder_time,
                    MealType.DINNER: User.dinner_reminder_time,
                    MealType.SNACK: User.snack_reminder_time
                }

                time_field = time_field_map.get(meal_type)
                if not time_field:
                    logger.warning(f"Unknown meal type for reminders: {meal_type}")
                    return

                # Получаем всех пользователей с включенными напоминаниями для этого времени
                result = await session.execute(
                    select(User).where(
                        User.reminders_enabled == True,
                        time_field == target_time,
                        User.is_active == True,
                        User.is_blocked == False
                    )
                )
                users = result.scalars().all()

                logger.info(f"Sending {meal_type.value} reminders to {len(users)} users at {target_time}")

                # Отправляем напоминания
                for user in users:
                    await ReminderService.send_meal_reminder(bot, user, meal_type)

        except Exception as e:
            logger.error("Error in send_reminders_for_meal_type: {}", repr(e))

    @staticmethod
    def parse_time(time_str: Optional[str]) -> Optional[time]:
        """
        Парсинг строки времени в формате HH:MM

        Args:
            time_str: Строка времени "HH:MM"

        Returns:
            datetime.time объект или None
        """
        if not time_str:
            return None

        try:
            hour, minute = map(int, time_str.split(':'))
            return time(hour=hour, minute=minute)
        except (ValueError, AttributeError):
            logger.warning(f"Invalid time format: {time_str}")
            return None

    @staticmethod
    async def setup_default_reminders(user_id: int):
        """
        Установить стандартные времена напоминаний для пользователя

        Args:
            user_id: Telegram ID пользователя
        """
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    return False

                # Устанавливаем стандартные времена
                user.reminders_enabled = True
                user.breakfast_reminder_time = "08:00"
                user.lunch_reminder_time = "13:00"
                user.dinner_reminder_time = "19:00"
                user.snack_reminder_time = None  # Перекус отключен по умолчанию

                await session.commit()
                logger.info(f"Set default reminders for user {user_id}")
                return True

        except Exception as e:
            logger.error("Error setting default reminders for user {}: {}", user_id, repr(e))
            return False

    @staticmethod
    async def update_reminder_time(
        user_id: int,
        meal_type: str,
        reminder_time: Optional[str]
    ) -> bool:
        """
        Обновить время напоминания для конкретного приема пищи

        Args:
            user_id: Telegram ID пользователя
            meal_type: Тип приема пищи (breakfast/lunch/dinner/snack)
            reminder_time: Время в формате HH:MM или None для отключения
        """
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    return False

                # Обновляем соответствующее поле
                field_map = {
                    "breakfast": "breakfast_reminder_time",
                    "lunch": "lunch_reminder_time",
                    "dinner": "dinner_reminder_time",
                    "snack": "snack_reminder_time"
                }

                field_name = field_map.get(meal_type)
                if not field_name:
                    return False

                setattr(user, field_name, reminder_time)
                await session.commit()

                logger.info(f"Updated {meal_type} reminder to {reminder_time} for user {user_id}")
                return True

        except Exception as e:
            logger.error("Error updating reminder time for user {}: {}", user_id, repr(e))
            return False

    @staticmethod
    async def toggle_reminders(user_id: int, enabled: bool) -> bool:
        """
        Включить/выключить все напоминания

        Args:
            user_id: Telegram ID пользователя
            enabled: True для включения, False для отключения
        """
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    return False

                user.reminders_enabled = enabled
                await session.commit()

                status = "enabled" if enabled else "disabled"
                logger.info(f"Reminders {status} for user {user_id}")
                return True

        except Exception as e:
            logger.error("Error toggling reminders for user {}: {}", user_id, repr(e))
            return False

    @staticmethod
    async def get_reminder_settings(user_id: int) -> Optional[Dict]:
        """
        Получить текущие настройки напоминаний пользователя

        Returns:
            Dict с настройками или None
        """
        try:
            async with async_session_maker() as session:
                result = await session.execute(
                    select(User).where(User.telegram_id == user_id)
                )
                user = result.scalar_one_or_none()

                if not user:
                    return None

                return {
                    "enabled": user.reminders_enabled,
                    "breakfast_time": user.breakfast_reminder_time,
                    "lunch_time": user.lunch_reminder_time,
                    "dinner_time": user.dinner_reminder_time,
                    "snack_time": user.snack_reminder_time,
                    "timezone": user.reminder_timezone or "UTC"
                }

        except Exception as e:
            logger.error("Error getting reminder settings for user {}: {}", user_id, repr(e))
            return None
