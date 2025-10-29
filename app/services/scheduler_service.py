"""
Сервис для планирования и выполнения задач по расписанию
"""
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from loguru import logger
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.models.meal import MealType
from app.services.reminder_service import ReminderService


class SchedulerService:
    """Сервис для управления планировщиком задач"""

    def __init__(self, bot: Bot):
        """
        Инициализация планировщика

        Args:
            bot: Telegram bot instance
        """
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """Запустить планировщик"""
        try:
            # Добавляем задачи для проверки напоминаний каждую минуту
            # Это позволит отправлять напоминания в любое время, установленное пользователем
            self.scheduler.add_job(
                self._check_and_send_reminders,
                trigger=CronTrigger(minute='*'),  # Каждую минуту
                id='meal_reminders_check',
                replace_existing=True
            )

            # Запускаем планировщик
            self.scheduler.start()
            logger.info("Scheduler service started successfully")

        except Exception as e:
            logger.error(f"Error starting scheduler: {e}")

    def stop(self):
        """Остановить планировщик"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=False)
                logger.info("Scheduler service stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")

    async def _check_and_send_reminders(self):
        """
        Проверить и отправить напоминания для текущего времени
        Вызывается каждую минуту
        """
        try:
            # Получаем текущее время в формате HH:MM
            current_time = datetime.now().strftime("%H:%M")

            logger.debug(f"Checking reminders for time {current_time}")

            # Проверяем напоминания для каждого типа приема пищи
            await ReminderService.send_reminders_for_meal_type(
                self.bot, MealType.BREAKFAST, current_time
            )
            await ReminderService.send_reminders_for_meal_type(
                self.bot, MealType.LUNCH, current_time
            )
            await ReminderService.send_reminders_for_meal_type(
                self.bot, MealType.DINNER, current_time
            )
            await ReminderService.send_reminders_for_meal_type(
                self.bot, MealType.SNACK, current_time
            )

        except Exception as e:
            logger.error(f"Error in _check_and_send_reminders: {e}")

    def schedule_wellness_survey(self, telegram_id: int, meal_id: int, delay_minutes: int = 30):
        """
        Запланировать опрос о самочувствии через указанное время после еды

        Args:
            telegram_id: Telegram ID пользователя
            meal_id: ID приема пищи
            delay_minutes: Задержка в минутах (по умолчанию 30)
        """
        try:
            run_time = datetime.now() + timedelta(minutes=delay_minutes)

            job_id = f"wellness_survey_{telegram_id}_{meal_id}"

            self.scheduler.add_job(
                self._send_wellness_survey,
                trigger=DateTrigger(run_date=run_time),
                args=[telegram_id, meal_id],
                id=job_id,
                replace_existing=True
            )

            logger.info(f"Scheduled wellness survey for user {telegram_id}, meal {meal_id} at {run_time}")

        except Exception as e:
            logger.error(f"Error scheduling wellness survey: {e}")

    async def _send_wellness_survey(self, telegram_id: int, meal_id: int):
        """
        Отправить опрос о самочувствии пользователю

        Args:
            telegram_id: Telegram ID пользователя
            meal_id: ID приема пищи
        """
        try:
            text = """
🌟 <b>Как ваше самочувствие после еды?</b>

Прошло 30 минут после вашего приема пищи.
Ответьте на короткий опрос (займет 1-2 минуты).

Это поможет найти связь между питанием и вашим самочувствием! 📊
"""

            keyboard = [
                [InlineKeyboardButton("📝 Начать опрос", callback_data="wellness_survey_start")],
                [InlineKeyboardButton("⏭️ Пропустить", callback_data="wellness_skip")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Отправляем сообщение
            message = await self.bot.send_message(
                chat_id=telegram_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML"
            )

            logger.info(f"Sent wellness survey to user {telegram_id} for meal {meal_id}")

            # Сохраняем meal_id в context (это будет доступно в callback handler)
            # Но так как у нас нет прямого доступа к context здесь,
            # мы передадим meal_id через callback_data
            # Обновим кнопку с meal_id
            keyboard = [
                [InlineKeyboardButton("📝 Начать опрос", callback_data=f"wellness_survey_start_{meal_id}")],
                [InlineKeyboardButton("⏭️ Пропустить", callback_data="wellness_skip")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await message.edit_reply_markup(reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Error sending wellness survey: {e}")


# Глобальный экземпляр планировщика
scheduler_service: SchedulerService = None


def init_scheduler(bot: Bot) -> SchedulerService:
    """
    Инициализировать глобальный экземпляр планировщика

    Args:
        bot: Telegram bot instance

    Returns:
        SchedulerService instance
    """
    global scheduler_service
    scheduler_service = SchedulerService(bot)
    return scheduler_service


def get_scheduler() -> SchedulerService:
    """
    Получить глобальный экземпляр планировщика

    Returns:
        SchedulerService instance
    """
    return scheduler_service
