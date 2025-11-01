"""
Celery задачи для генерации планов питания

ВАЖНО: Использует специальный механизм управления event loop
для предотвращения ошибки "RuntimeError: Event loop is closed"
"""
from app.celery_app import celery_app
from app.db.celery_session import celery_session_maker, cleanup_celery_connections
from app.celery_event_loop import run_async_task, managed_session_scope
from app.services.meal_plan_service import MealPlanService
from app.services.shopping_list_service import ShoppingListService
from app.services.pdf_generator import PDFGeneratorService
from app.models.meal_plan import PlanPeriod
from sqlalchemy import select
from app.models.user import User
from loguru import logger
import asyncio


@celery_app.task(
    bind=True,                    # Получать self (для retry)
    name='tasks.generate_meal_plan',
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=180,          # Мягкий лимит 3 минуты
    time_limit=240                # Жесткий лимит 4 минуты
)
def generate_meal_plan_task(
    self,
    user_id: int,
    period_type: str,
    preferences: dict = None,
    medical_context: dict = None,
    calculate_prices: bool = True,
    start_date: str = None  # ISO format: "2025-01-15"
):
    """
    Фоновая задача: Генерация плана питания

    Args:
        user_id: Telegram ID пользователя
        period_type: Период плана ('day', 'week', 'month')
        preferences: Предпочтения пользователя
        medical_context: Медицинский контекст
        calculate_prices: Рассчитывать ли цены
        start_date: Дата начала плана (ISO format)

    Returns:
        dict: Информация о созданном плане
    """
    try:
        logger.info(f"[Celery] Starting meal plan generation for user {user_id}, period={period_type}")

        # Парсим start_date если передан
        from datetime import date
        parsed_start_date = None
        if start_date:
            parsed_start_date = date.fromisoformat(start_date)

        # Используем run_async_task вместо asyncio.run()
        # Это гарантирует правильное управление event loop
        result = run_async_task(
            _generate_meal_plan_async,
            user_id,
            PlanPeriod(period_type),
            preferences,
            medical_context,
            calculate_prices,
            parsed_start_date
        )

        logger.info(f"[Celery] Meal plan generated successfully for user {user_id}")
        return result

    except Exception as exc:
        from celery.exceptions import SoftTimeLimitExceeded

        if isinstance(exc, SoftTimeLimitExceeded):
            logger.error(f"[Celery] Task time limit exceeded for user {user_id}. Task took too long.")
            # Не делаем retry при таймауте - это может быть из-за rate limiting API
            raise

        logger.error(f"[Celery] Error generating meal plan: {exc}", exc_info=True)
        # Retry задачи при ошибке
        raise self.retry(exc=exc)

    finally:
        # КРИТИЧНО: Очищаем соединения после задачи
        # Это предотвращает накопление "мертвых" соединений с закрытым loop
        try:
            run_async_task(cleanup_celery_connections)
        except Exception as cleanup_error:
            logger.warning(f"[Celery] Error during connection cleanup: {cleanup_error}")


async def _generate_meal_plan_async(
    user_id: int,
    period_type: PlanPeriod,
    preferences: dict,
    medical_context: dict,
    calculate_prices: bool,
    start_date=None
) -> dict:
    """
    Асинхронная часть генерации плана

    Использует celery_session_maker и managed_session_scope
    для правильной работы с event loop

    Returns:
        dict: {
            'plan_id': int,
            'pdf_plan_path': str,
            'pdf_shopping_path': str,
            'total_cost': float,
            'daily_calories': int
        }
    """
    async with managed_session_scope(celery_session_maker) as session:
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        logger.info(f"[Celery] User found: {user.preferred_name or user.first_name}")

        # Деактивируем старые планы
        logger.info(f"[Celery] Deactivating old plans...")
        await MealPlanService.deactivate_old_plans(session, user.telegram_id)

        # Генерируем план
        logger.info(f"[Celery] Generating meal plan via AI...")
        meal_plan = await MealPlanService.generate_meal_plan(
            session,
            user.telegram_id,
            period_type,
            start_date=start_date,
            preferences=preferences,
            medical_context=medical_context
        )

        logger.info(f"[Celery] Meal plan generated: id={meal_plan.id}")

        # Создаём список покупок
        logger.info(f"[Celery] Creating shopping list...")
        shopping_list = await ShoppingListService.create_shopping_list(
            session,
            meal_plan.id,
            search_prices=calculate_prices
        )

        logger.info(f"[Celery] Shopping list created: total_cost={shopping_list.total_cost}")

        # Генерируем PDF
        logger.info(f"[Celery] Generating PDFs...")
        days = await MealPlanService.get_meal_plan_days(session, meal_plan.id)
        days_data = []
        for day in days:
            meals = await MealPlanService.get_day_meals(session, day.id)
            days_data.append((day, meals))

        pdf_plan_path = await PDFGeneratorService.generate_meal_plan_pdf(
            meal_plan,
            days_data,
            user.preferred_name or user.first_name,
            user.city,
            user.gender.value if user.gender else "male"
        )

        logger.info(f"[Celery] Meal plan PDF generated: {pdf_plan_path}")

        items = await ShoppingListService.get_shopping_items(session, shopping_list.id)
        pdf_shopping_path = await PDFGeneratorService.generate_shopping_list_pdf(
            shopping_list,
            items,
            meal_plan,
            user.preferred_name or user.first_name,
            user.city
        )

        logger.info(f"[Celery] Shopping list PDF generated: {pdf_shopping_path}")

        # Сохраняем пути к PDF
        meal_plan.pdf_path = pdf_plan_path
        shopping_list.pdf_path = pdf_shopping_path
        # commit будет выполнен автоматически в managed_session_scope

        logger.info(f"[Celery] Task completed successfully for user {user_id}")

        return {
            'plan_id': meal_plan.id,
            'pdf_plan_path': pdf_plan_path,
            'pdf_shopping_path': pdf_shopping_path,
            'total_cost': float(shopping_list.total_cost),
            'daily_calories': meal_plan.daily_calories,
            'period_type': period_type.value
        }


@celery_app.task(
    bind=True,
    name='tasks.notify_user_plan_ready',
    max_retries=5,
    soft_time_limit=60,           # Мягкий лимит 60 секунд
    time_limit=90,                # Жесткий лимит 90 секунд
    default_retry_delay=10
)
def notify_user_plan_ready(self, plan_data: dict, user_id: int):
    """
    Задача: Уведомить пользователя о готовности плана

    Args:
        plan_data: Данные о плане (результат generate_meal_plan_task)
        user_id: Telegram ID пользователя
    """
    try:
        logger.info(f"[Celery] Notifying user {user_id} about plan {plan_data['plan_id']}")

        # Используем run_async_task вместо asyncio.run()
        # Это гарантирует правильное управление event loop
        run_async_task(_notify_user_async, plan_data, user_id)

        logger.info(f"[Celery] User {user_id} notified successfully")

    except Exception as e:
        logger.error(f"[Celery] Error notifying user {user_id}: {e}", exc_info=True)
        # Retry при ошибках
        raise self.retry(exc=e)

    finally:
        # КРИТИЧНО: Очищаем соединения после задачи
        try:
            run_async_task(cleanup_celery_connections)
        except Exception as cleanup_error:
            logger.warning(f"[Celery] Error during connection cleanup: {cleanup_error}")


async def _notify_user_async(plan_data: dict, user_id: int):
    """
    Асинхронная отправка уведомлений пользователю

    Args:
        plan_data: Данные о плане
        user_id: Telegram ID пользователя
    """
    from telegram import Bot, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.error import TelegramError
    from app.config import settings

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    # Определяем текст периода
    period_text_map = {
        'day': '1 день',
        'week': 'неделю',
        'month': 'месяц'
    }
    period_text = period_text_map.get(plan_data.get('period_type', 'day'), 'план')

    # Отправляем PDF с планом питания
    with open(plan_data['pdf_plan_path'], 'rb') as pdf_file:
        await bot.send_document(
            chat_id=user_id,
            document=InputFile(pdf_file, filename=f"План_питания_{period_text}.pdf"),
            caption=f"📋 Твой план питания на {period_text} готов!"
        )

    logger.info(f"[Celery] Meal plan PDF sent to user {user_id}")

    # Отправляем PDF со списком покупок
    with open(plan_data['pdf_shopping_path'], 'rb') as pdf_file:
        await bot.send_document(
            chat_id=user_id,
            document=InputFile(pdf_file, filename=f"Список_покупок_{period_text}.pdf"),
            caption=f"🛒 Список покупок (~{plan_data['total_cost']:.2f} ₽)"
        )

    logger.info(f"[Celery] Shopping list PDF sent to user {user_id}")

    # Отправляем сообщение с кнопками
    keyboard = [
        [InlineKeyboardButton("📄 Просмотреть план", callback_data=f"view_plan_{plan_data['plan_id']}")],
        [InlineKeyboardButton("✅ Всё отлично!", callback_data=f"feedback_positive_{plan_data['plan_id']}")],
        [InlineKeyboardButton("🔄 Хочу изменить", callback_data=f"feedback_negative_{plan_data['plan_id']}")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]

    await bot.send_message(
        chat_id=user_id,
        text=f"✅ <b>План питания создан!</b>\n\n"
             f"🎯 Калорий в день: {plan_data['daily_calories']} ккал\n"
             f"💰 Стоимость продуктов: ~{plan_data['total_cost']:.2f} ₽\n\n"
             f"<i>Как тебе план?</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

    # Закрываем соединение с Telegram API
    await bot.shutdown()
