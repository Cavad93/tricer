"""
Сервис для планирования и выполнения задач по расписанию
"""
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from telegram import Bot

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
