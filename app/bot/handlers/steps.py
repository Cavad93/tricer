"""
Обработчики для учета шагов пользователя
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode
from loguru import logger
from datetime import date

from app.db.session import async_session_maker
from app.models.user import User
from app.services.steps_tracking_service import StepsTrackingService
from app.services.steps_request_service import StepsRequestService
from app.bot.keyboards import back_to_menu_keyboard
from sqlalchemy import select


# Состояния для ConversationHandler
class StepsStates:
    WAITING_STEPS_INPUT = 1


async def steps_range_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка выбора диапазона шагов
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    range_value = query.data

    # Получаем количество шагов из диапазона
    steps = StepsRequestService.get_steps_from_range(range_value)

    if steps == 0:
        await query.edit_message_text(
            "❌ Произошла ошибка. Попробуй ввести количество шагов числом.",
            reply_markup=back_to_menu_keyboard()
        )
        return ConversationHandler.END

    # Сохраняем шаги
    await save_user_steps(user.id, steps, query)

    return ConversationHandler.END


async def steps_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка пропуска ввода шагов
    """
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "⏭️ Хорошо, пропускаем учет шагов.\n\n"
        "Ты всегда можешь ввести количество шагов позже через меню.",
        reply_markup=back_to_menu_keyboard()
    )

    return ConversationHandler.END


async def steps_manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Обработка ручного ввода количества шагов
    """
    user = update.effective_user
    text = update.message.text.strip()

    # Пытаемся преобразовать в число
    try:
        steps = int(text.replace(" ", "").replace(",", "").replace(".", ""))

        if steps < 0:
            await update.message.reply_text(
                "❌ Количество шагов не может быть отрицательным. Попробуй еще раз:"
            )
            return StepsStates.WAITING_STEPS_INPUT

        if steps > 100000:
            await update.message.reply_text(
                "❌ Слишком большое число! Максимум 100,000 шагов. Попробуй еще раз:"
            )
            return StepsStates.WAITING_STEPS_INPUT

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введи число (например: 8500):"
        )
        return StepsStates.WAITING_STEPS_INPUT

    # Сохраняем шаги
    await save_user_steps(user.id, steps, update.message)

    return ConversationHandler.END


async def save_user_steps(telegram_id: int, steps: int, message_or_query):
    """
    Сохранить шаги пользователя и вывести результат

    Args:
        telegram_id: Telegram ID пользователя
        steps: Количество шагов
        message_or_query: Объект message или query для ответа
    """
    try:
        async with async_session_maker() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                error_text = "❌ Пользователь не найден"
                if hasattr(message_or_query, 'edit_message_text'):
                    await message_or_query.edit_message_text(error_text)
                else:
                    await message_or_query.reply_text(error_text)
                return

            # Сохраняем шаги
            await StepsTrackingService.save_steps(
                user_id=db_user.id,
                steps=steps,
                session=session
            )

            # Получаем информацию об активности
            activity_message = StepsTrackingService.get_activity_message(steps)

            # Рассчитываем бонусные калории
            from app.models.user_steps import UserSteps
            steps_entry = UserSteps(user_id=db_user.id, date=date.today(), steps=steps)
            bonus_calories = steps_entry.bonus_calories

            # Формируем ответ
            response = f"""
✅ <b>Шаги сохранены!</b>

📊 Количество шагов: <b>{steps:,}</b>

{activity_message}
"""

            if bonus_calories > 0:
                response += f"""
🎁 <b>Отличная новость!</b>
Благодаря твоей активности, завтра у тебя будет дополнительно <b>+{bonus_calories} ккал</b> в запасе!

Продолжай в том же духе! 💪
"""
            else:
                response += """
💡 <b>Совет:</b> Попробуй завтра пройти больше 5000 шагов, и ты получишь бонусные калории на следующий день!
"""

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ])

            if hasattr(message_or_query, 'edit_message_text'):
                await message_or_query.edit_message_text(
                    response,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            else:
                await message_or_query.reply_text(
                    response,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )

            logger.info(f"Saved steps for user {db_user.id}: {steps} steps, bonus: {bonus_calories} kcal")

    except Exception as e:
        logger.error(f"Error saving steps for user {telegram_id}: {e}", exc_info=True)
        error_text = "❌ Произошла ошибка при сохранении шагов. Попробуй позже."

        if hasattr(message_or_query, 'edit_message_text'):
            await message_or_query.edit_message_text(error_text)
        else:
            await message_or_query.reply_text(error_text)


# ConversationHandler для ввода шагов (ручной ввод)
steps_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(steps_range_callback, pattern="^steps_range_"),
    ],
    states={
        StepsStates.WAITING_STEPS_INPUT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, steps_manual_input),
        ],
    },
    fallbacks=[
        CallbackQueryHandler(steps_skip_callback, pattern="^steps_skip$"),
    ],
    per_message=False,
    allow_reentry=True
)


# Отдельные обработчики для кнопок (не ConversationHandler)
async def handle_steps_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка пропуска ввода шагов"""
    return await steps_skip_callback(update, context)


async def handle_steps_range(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора диапазона шагов"""
    return await steps_range_callback(update, context)
