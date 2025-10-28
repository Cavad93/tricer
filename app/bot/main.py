"""
Главный файл Telegram бота NutriAI
"""
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from loguru import logger
import sys

from app.config import settings
from app.bot.handlers.start import onboarding_conversation
from app.bot.handlers.photo import photo_handler
from app.bot.keyboards import main_menu_keyboard, back_to_menu_keyboard


# Настройка логирования
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.LOG_LEVEL,
)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🤖 *NutriAI - Твой AI-нутрициолог*\n\n"
        "*Основные команды:*\n"
        "/start - Начать работу / Настроить профиль\n"
        "/help - Показать эту справку\n"
        "/profile - Мой профиль\n"
        "/menu - Главное меню\n\n"
        "*Как пользоваться:*\n"
        "📸 Отправь фото еды - я автоматически распознаю блюдо и посчитаю калории\n"
        "💬 Задай вопрос о питании - получи ответ от AI\n"
        "📊 Смотри статистику и прогресс в дневнике\n\n"
        "*Нужна помощь?* Просто напиши мне!"
    )

    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /menu"""
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=main_menu_keyboard()
    )


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /profile"""
    # TODO: Получить профиль из БД
    user_data = context.user_data

    if not user_data.get("target_calories"):
        await update.message.reply_text(
            "У тебя еще нет профиля.\n"
            "Используй /start чтобы настроить профиль."
        )
        return

    profile_text = (
        "👤 *Твой профиль*\n\n"
        f"Пол: {'Мужской' if user_data.get('gender') == 'male' else 'Женский'}\n"
        f"Возраст: {user_data.get('age')} лет\n"
        f"Рост: {user_data.get('height')} см\n"
        f"Текущий вес: {user_data.get('current_weight')} кг\n"
        f"Целевой вес: {user_data.get('target_weight')} кг\n\n"
        f"📊 *Целевые показатели на день:*\n"
        f"🔥 Калории: {user_data.get('target_calories')} ккал\n"
        f"🥩 Белки: {user_data.get('target_proteins')}г\n"
        f"🧈 Жиры: {user_data.get('target_fats')}г\n"
        f"🍞 Углеводы: {user_data.get('target_carbs')}г\n"
    )

    await update.message.reply_text(
        profile_text,
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку главного меню"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Главное меню:",
        reply_markup=main_menu_keyboard()
    )


async def add_food_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Добавить еду'"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📸 *Добавить еду*\n\n"
        "Отправь мне фото своего блюда, и я автоматически:\n"
        "✅ Распознаю что это за еда\n"
        "✅ Определю размер порции\n"
        "✅ Посчитаю калории и БЖУ\n\n"
        "Или просто напиши название блюда и вес (например: 'Гречка 200г')",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def diary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Дневник'"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📊 *Дневник питания*\n\n"
        "Эта функция будет доступна в следующей версии!\n"
        "Здесь ты сможешь:\n"
        "• Просматривать все приемы пищи\n"
        "• Видеть прогресс по калориям и БЖУ\n"
        "• Анализировать статистику за неделю/месяц",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def ai_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'AI-чат'"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "💬 *AI-чат*\n\n"
        "Задай мне любой вопрос о питании, и я постараюсь помочь!\n\n"
        "Например:\n"
        "• Что лучше съесть перед тренировкой?\n"
        "• Можно ли мне шоколад на диете?\n"
        "• Почему я не худею?\n"
        "• Какие продукты богаты белком?\n\n"
        "Просто напиши свой вопрос в чат!",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Профиль'"""
    query = update.callback_query
    await query.answer()

    user_data = context.user_data

    if not user_data.get("target_calories"):
        await query.edit_message_text(
            "У тебя еще нет профиля.\n"
            "Используй /start чтобы настроить профиль."
        )
        return

    profile_text = (
        "👤 *Твой профиль*\n\n"
        f"Возраст: {user_data.get('age')} лет\n"
        f"Рост: {user_data.get('height')} см\n"
        f"Текущий вес: {user_data.get('current_weight')} кг\n"
        f"Целевой вес: {user_data.get('target_weight')} кг\n\n"
        f"📊 *Целевые показатели на день:*\n"
        f"🔥 Калории: {user_data.get('target_calories')} ккал\n"
        f"🥩 Белки: {user_data.get('target_proteins')}г\n"
        f"🧈 Жиры: {user_data.get('target_fats')}г\n"
        f"🍞 Углеводы: {user_data.get('target_carbs')}г\n"
    )

    await query.edit_message_text(
        profile_text,
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Статистика'"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📈 *Статистика*\n\n"
        "Эта функция будет доступна в следующей версии!\n"
        "Здесь ты увидишь:\n"
        "• Динамику веса\n"
        "• Графики калорий и БЖУ\n"
        "• AI-инсайты о твоем питании\n"
        "• Прогресс к цели",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Настройки'"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "⚙️ *Настройки*\n\n"
        "Эта функция будет доступна в следующей версии!\n"
        "Здесь ты сможешь:\n"
        "• Изменить профиль\n"
        "• Управлять уведомлениями\n"
        "• Подключить фитнес-трекеры\n"
        "• Оформить Premium подписку",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    await update.message.reply_text(
        "Текстовые сообщения будут обрабатываться в следующей версии!\n"
        "Используй /menu для доступа к функциям бота."
    )


# Обработчик фото импортирован из app.bot.handlers.photo


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}")

    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка при обработке запроса. Попробуйте позже."
        )


def main():
    """Главная функция запуска бота"""
    logger.info("Starting NutriAI Bot...")

    # Создаем приложение
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # Добавляем обработчики
    application.add_handler(onboarding_conversation)
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("profile", profile_command))

    # Callback handlers для кнопок
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(add_food_callback, pattern="^add_food$"))
    application.add_handler(CallbackQueryHandler(diary_callback, pattern="^diary$"))
    application.add_handler(CallbackQueryHandler(ai_chat_callback, pattern="^ai_chat$"))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile$"))
    application.add_handler(CallbackQueryHandler(stats_callback, pattern="^stats$"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^settings$"))

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    logger.info("Bot started successfully!")

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
