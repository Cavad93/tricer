"""
Обработчики для настройки напоминаний о приемах пищи
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger

from app.db.session import async_session_maker
from app.services.reminder_service import ReminderService
from app.bot.keyboards import main_menu_keyboard
from sqlalchemy import select
from app.models.user import User

# Состояния
WAITING_CUSTOM_TIME = 1


async def reminder_setup_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предложение настроить напоминания (вызывается после создания плана)"""
    query = update.callback_query
    if query:
        await query.answer()

    text = (
        "⏰ <b>Напоминания о приемах пищи</b>\n\n"
        "Хотите, чтобы я напоминал вам о времени приема пищи?\n\n"
        "Это поможет придерживаться режима питания!"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Да, настроить!", callback_data="reminder_yes")],
        [InlineKeyboardButton("❌ Нет, не нужно", callback_data="reminder_no")],
    ]

    if query:
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    return ConversationHandler.END


async def reminder_setup_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь согласился на напоминания - предлагаем стандартное время"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    text = (
        "⏰ <b>Настройка напоминаний</b>\n\n"
        "Предлагаю стандартное время:\n\n"
        "🌅 Завтрак: 08:00\n"
        "🌞 Обед: 13:00\n"
        "🌙 Ужин: 19:00\n\n"
        "Вас устраивает это время?"
    )

    keyboard = [
        [InlineKeyboardButton("✅ Да, устраивает!", callback_data="reminder_standard")],
        [InlineKeyboardButton("✏️ Хочу своё время", callback_data="reminder_custom")],
        [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )


async def reminder_setup_standard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить стандартное время напоминаний"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    try:
        # Устанавливаем стандартные напоминания
        success = await ReminderService.setup_default_reminders(user_id)

        if success:
            text = (
                "✅ <b>Напоминания настроены!</b>\n\n"
                "Я буду напоминать вам о приемах пищи:\n\n"
                "🌅 Завтрак: 08:00\n"
                "🌞 Обед: 13:00\n"
                "🌙 Ужин: 19:00\n\n"
                "Вы можете изменить время в настройках в любой момент."
            )
        else:
            text = "❌ Ошибка при настройке напоминаний. Попробуйте позже."

        await query.edit_message_text(
            text,
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error("Error setting up standard reminders for user {}: {}", user_id, repr(e))
        await query.edit_message_text(
            "❌ Ошибка при настройке напоминаний",
            reply_markup=main_menu_keyboard()
        )


async def reminder_setup_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало настройки своего времени"""
    query = update.callback_query
    await query.answer()

    text = (
        "✏️ <b>Свое время напоминаний</b>\n\n"
        "Введите время для каждого приема пищи в формате:\n\n"
        "Завтрак: 08:00\n"
        "Обед: 13:00\n"
        "Ужин: 19:00\n\n"
        "Или напишите в любом формате, я попробую распознать!"
    )

    await query.edit_message_text(text, parse_mode="HTML")
    return WAITING_CUSTOM_TIME


async def reminder_process_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного пользовательского времени"""
    user_id = update.effective_user.id
    time_text = update.message.text

    try:
        # Используем AI для парсинга времени
        from app.services.claude_ai import ClaudeAIService
        claude_service = ClaudeAIService()

        prompt = f"""Распознай время для напоминаний о приемах пищи.

ТЕКСТ:
{time_text}

Верни JSON в формате:
{{
  "breakfast": "HH:MM" или null,
  "lunch": "HH:MM" или null,
  "dinner": "HH:MM" или null,
  "snack": "HH:MM" или null
}}

ВАЖНО: Верни ТОЛЬКО JSON, без дополнительного текста."""

        response = await claude_service.async_client.messages.create(
            model=claude_service.model,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Парсим ответ
        response_text = response.content[0].text
        times = claude_service.extract_json_from_response(response_text)

        if not times:
            await update.message.reply_text(
                "❌ Не удалось распознать время. Попробуйте ещё раз.",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END

        # Обновляем времена напоминаний
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user_id)
            )
            user = result.scalar_one_or_none()

            if user:
                user.reminders_enabled = True
                user.breakfast_reminder_time = times.get("breakfast")
                user.lunch_reminder_time = times.get("lunch")
                user.dinner_reminder_time = times.get("dinner")
                user.snack_reminder_time = times.get("snack")

                await session.commit()

                result_text = "✅ <b>Напоминания настроены!</b>\n\n"

                if times.get("breakfast"):
                    result_text += f"🌅 Завтрак: {times['breakfast']}\n"
                if times.get("lunch"):
                    result_text += f"🌞 Обед: {times['lunch']}\n"
                if times.get("dinner"):
                    result_text += f"🌙 Ужин: {times['dinner']}\n"
                if times.get("snack"):
                    result_text += f"🍎 Перекус: {times['snack']}\n"

                result_text += "\nВы можете изменить время в настройках."

                await update.message.reply_text(
                    result_text,
                    reply_markup=main_menu_keyboard(),
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    "❌ Пользователь не найден",
                    reply_markup=main_menu_keyboard()
                )

        return ConversationHandler.END

    except Exception as e:
        logger.error("Error processing custom reminder time for user {}: {}", user_id, repr(e))
        await update.message.reply_text(
            "❌ Ошибка при настройке напоминаний",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END


async def reminder_setup_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь отказался от напоминаний"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✅ Хорошо, напоминания не будут настроены.\n\n"
        "Вы всегда можете включить их в настройках.",
        reply_markup=main_menu_keyboard()
    )


async def cancel_reminder_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена настройки напоминаний"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "❌ Настройка отменена",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Настройка отменена",
            reply_markup=main_menu_keyboard()
        )

    return ConversationHandler.END
