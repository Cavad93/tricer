"""
Главный файл Telegram бота NutriAI
"""
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)
from telegram.request import HTTPXRequest
import sys
from app.config import settings
from app.core.loguru_setup import setup_bot_logger

# Настройка профессиональной системы логирования
logger = setup_bot_logger(level=settings.LOG_LEVEL)
from app.db.session import async_session_maker
from sqlalchemy import select
from app.models.user import User
from app.bot.handlers.start import onboarding_conversation
from app.bot.handlers.photo import (
    photo_handler,
    handle_verification,
    handle_clarification,
    handle_food_intention,
    meal_type_selected,
    cancel_food_add
)
from app.bot.handlers.chat import (
    chat_message_handler,
    clear_chat_command,
    chat_stats_command
)
from app.bot.handlers.meal_choice import (
    handle_meal_variant_choice,
    handle_custom_meal_start,
    handle_custom_meal_input,
    handle_meal_cancel,
    handle_risky_choice,
    handle_safe_choice,
    cancel_custom_meal,
    WAITING_CUSTOM_MEAL
)
from app.bot.handlers.diary import (
    diary_callback,
    delete_meal_callback,
    diary_edit_list_callback,
    diary_delete_list_callback,
    diary_edit_meal_callback,
    diary_delete_meal_callback,
    edit_portion_start_callback,
    edit_portion_input,
    cancel_edit_portion,
    remove_food_from_meal_callback,
    delete_food_callback,
    delete_whole_meal_callback,
    add_food_to_meal_callback,
    WAITING_PORTION_INPUT
)
from app.bot.handlers.meal_plan import (
    meal_plan_start,
    meal_plan_period_selected,
    handle_start_timing,
    handle_batch_cooking,
    handle_cooking_time_selection,
    reuse_weekly_plan_yes,
    reuse_weekly_plan_no,
    handle_preference_response,
    handle_chronic_conditions_response,
    skip_chronic_conditions_check_callback,
    handle_acute_conditions_response,
    skip_acute_conditions_callback,
    confirm_medical_generation_callback,
    handle_price_calculation_yes,
    handle_price_calculation_no,
    handle_shop_single,
    handle_shop_multiple,
    handle_feedback_positive,
    handle_feedback_negative,
    handle_change_request,
    view_meal_plan,
    view_shopping_list,
    cancel_meal_plan,
    global_feedback_positive_callback,
    global_feedback_negative_callback
)
from app.bot.keyboards import main_menu_keyboard, back_to_menu_keyboard
from app.bot.states import FoodAddStates, MealPlanStates, RestaurantStates, PantryStates, ReminderSettingsStates
from app.bot.handlers.restaurant import (
    restaurant_start,
    restaurant_photo_handler,
    handle_mood_selection,
    analyze_menu_and_recommend,
    cancel_restaurant,
    handle_restaurant_used_response,
    handle_restaurant_dish_selection,
    handle_restaurant_search_more,
    handle_restaurant_manual_input,
    handle_restaurant_manual_dish_name
)
from app.bot.handlers.reminders import (
    ReminderSetupStates,
    setup_reminders_start,
    select_meal_for_reminder,
    set_reminder_time,
    delete_reminder,
    toggle_reminders,
    request_custom_time,
    cancel_reminder_setup
)
from app.bot.handlers.reports import get_reports_conversation_handler
from app.bot.handlers.wellness import wellness_survey_conversation
from app.bot.handlers.medical_analysis import medical_analysis_conversation
from app.bot.handlers.privacy import (
    privacy_settings_command,
    export_data_callback,
    delete_account_callback,
    confirm_delete_account_callback,
    revoke_consent_callback,
    cancel_privacy_action
)
from app.bot.handlers.steps import (
    handle_steps_skip,
    handle_steps_range
)
from app.bot.handlers.pantry import (
    pantry_start,
    pantry_add_start,
    pantry_process_input,
    pantry_delete_list,
    pantry_delete_item,
    pantry_create_plan_start,
    pantry_edit_product_for_plan,
    pantry_save_edited_quantity,
    pantry_confirm_and_create_plan
)
from app.bot.handlers.reminder_settings import (
    reminder_setup_start,
    reminder_setup_yes,
    reminder_setup_standard,
    reminder_setup_custom,
    reminder_process_custom_time,
    reminder_setup_no,
    cancel_reminder_setup
)
from app.services.scheduler_service import init_scheduler
from prometheus_client import start_http_server
from app.metrics import (
    MetricsUpdater,
    set_bot_info,
    track_command,
    user_registrations_total
)


# Логирование уже настроено через setup_bot_logger() в начале файла


async def safe_answer_callback_query(query, text: str = None, show_alert: bool = False):
    """
    Безопасный ответ на callback query с обработкой устаревших запросов

    Args:
        query: CallbackQuery объект
        text: Текст для отображения (опционально)
        show_alert: Показывать как alert (опционально)

    Returns:
        bool: True если ответ успешен, False если query устарел
    """
    from telegram.error import BadRequest

    try:
        await query.answer(text=text, show_alert=show_alert)
        return True
    except BadRequest as e:
        if "query is too old" in str(e).lower() or "query id is invalid" in str(e).lower():
            logger.debug(f"Callback query {query.id} is too old, skipping answer")
            return False
        # Если это другая BadRequest ошибка, пробрасываем дальше
        raise


async def safe_edit_or_send_message(query, text: str, **kwargs):
    """
    Безопасное редактирование сообщения или отправка нового при ошибке

    Args:
        query: CallbackQuery объект
        text: Текст сообщения
        **kwargs: Дополнительные параметры (reply_markup, parse_mode и т.д.)

    Returns:
        Message: Отправленное или отредактированное сообщение
    """
    from telegram.error import BadRequest

    try:
        # Сначала пытаемся ответить на callback query
        await safe_answer_callback_query(query)

        # Затем пытаемся отредактировать сообщение
        return await query.edit_message_text(text=text, **kwargs)
    except BadRequest as e:
        error_msg = str(e).lower()
        # Если сообщение слишком старое или уже удалено, отправляем новое
        if any(phrase in error_msg for phrase in [
            "message is not modified",
            "message to edit not found",
            "query is too old",
            "message can't be edited"
        ]):
            logger.debug(f"Cannot edit message, sending new one: {e}")
            # Отправляем новое сообщение
            return await query.message.reply_text(text=text, **kwargs)
        # Если это другая ошибка, пробрасываем дальше
        raise


@track_command('help')
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "🤖 *NutriAI - Твой AI-нутрициолог*\n\n"
        "*Основные команды:*\n"
        "/start - Начать работу / Настроить профиль\n"
        "/help - Показать эту справку\n"
        "/profile - Мой профиль\n"
        "/menu - Главное меню\n"
        "/clear_chat - Очистить историю AI-чата\n"
        "/chat_stats - Статистика использования\n"
        "/wellness_insights - AI-анализ самочувствия\n\n"
        "*Как пользоваться:*\n"
        "📸 Отправь фото еды - я автоматически распознаю блюдо и посчитаю калории\n"
        "🌟 Заполняй опросы о самочувствии через 30 мин после еды\n"
        "💬 Напиши вопрос о питании - получи ответ от AI с учетом твоего профиля\n"
        "📊 Используй /menu для доступа ко всем функциям\n\n"
        "*AI-чат:*\n"
        "Просто напиши мне любой вопрос о питании, и я отвечу с учетом:\n"
        "• Твоих целей и параметров\n"
        "• Истории нашего разговора\n"
        "• Научных данных о питании\n\n"
        "*Нужна помощь?* Просто напиши мне!"
    )

    await update.message.reply_text(
        help_text,
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


@track_command('menu')
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /menu"""
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=main_menu_keyboard()
    )


@track_command('profile')
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

    # Сбрасываем флаг ожидания изменений плана
    if "waiting_for_plan_changes" in context.user_data:
        context.user_data["waiting_for_plan_changes"] = False

    await safe_edit_or_send_message(
        query,
        "Главное меню:",
        reply_markup=main_menu_keyboard()
    )


async def add_food_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Добавить еду'"""
    query = update.callback_query

    await safe_edit_or_send_message(
        query,
        "📸 *Добавить еду*\n\n"
        "Отправь мне фото своего блюда, и я автоматически:\n"
        "✅ Распознаю что это за еда\n"
        "✅ Определю размер порции\n"
        "✅ Посчитаю калории и БЖУ\n\n"
        "Или просто напиши название блюда и вес (например: 'Гречка 200г')",
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


# diary_callback теперь импортируется из app.bot.handlers.diary


async def ai_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'AI-чат'"""
    query = update.callback_query

    user = update.effective_user

    # Получаем статистику использования
    async with async_session_maker() as session:
        from app.models.user import User
        from sqlalchemy import select

        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if db_user:
            from app.services.usage_service import UsageService
            stats = await UsageService.get_usage_stats(session, db_user.id)

            limit_info = ""
            if not stats['is_premium']:
                remaining = stats['chat_limit'] - stats['chat_messages']
                limit_info = f"\n\n_Осталось сообщений сегодня: {remaining}/{stats['chat_limit']}_"
        else:
            limit_info = ""

    await safe_edit_or_send_message(
        query,
        "💬 *AI-чат активирован*\n\n"
        "Я - твой персональный AI-нутрициолог! Задай мне любой вопрос о питании.\n\n"
        "🎯 *Я учитываю:*\n"
        "• Твой профиль и цели\n"
        "• Историю нашего разговора\n"
        "• Твои предпочтения и аллергии\n"
        "• Научные данные о питании\n\n"
        "💡 *Примеры вопросов:*\n"
        "• Что съесть перед тренировкой?\n"
        "• Почему я не худею?\n"
        "• Можно ли мне шоколад?\n"
        "• Как увеличить белок в рационе?\n"
        "• Составь меню на сегодня\n\n"
        "📝 Просто напиши свой вопрос в чат!"
        + limit_info,
        parse_mode="Markdown",
        reply_markup=back_to_menu_keyboard()
    )


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Профиль'"""
    query = update.callback_query

    # Получаем данные из БД
    async with async_session_maker() as session:
        from app.models.user import User
        from sqlalchemy import select

        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.onboarding_completed:
            await safe_edit_or_send_message(
                query,
                "У тебя еще нет профиля.\n"
                "Используй /start чтобы настроить профиль.",
                reply_markup=back_to_menu_keyboard()
            )
            return

        # Формируем текст о времени готовки
        cooking_time_text = ""
        if user.preferred_cooking_time_minutes:
            cooking_time_text = f"⏰ Время на готовку: до {user.preferred_cooking_time_minutes} мин\n"
        else:
            cooking_time_text = "⏰ Время на готовку: не указано\n"

        # Рассчитываем ИМТ и получаем историю веса
        from app.services.nutrition_calc import NutritionCalculator
        from app.services.weight_service import WeightService

        bmi = NutritionCalculator.calculate_bmi(user.current_weight, user.height)
        bmi_category = NutritionCalculator.get_bmi_category(bmi)
        weight_history = await WeightService.get_weight_history(user.id, session, limit=10)

        # Формируем текст о весе
        weight_text = f"Текущий вес: {user.current_weight} кг\n"
        weight_text += f"ИМТ: {bmi} ({bmi_category})\n"
        weight_text += f"Целевой вес: {user.target_weight} кг\n"

        # Добавляем изменение веса если есть история
        if len(weight_history) >= 2:
            weight_change = WeightService.calculate_weight_change(weight_history)
            if weight_change:
                change_emoji = "📉" if weight_change < 0 else "📈"
                change_text = f"{abs(weight_change)} кг" if weight_change < 0 else f"+{weight_change} кг"
                weight_text += f"{change_emoji} Изменение: {change_text}\n"

        # Экранируем специальные символы для MarkdownV2
        def escape_markdown(text):
            """Экранирует специальные символы для MarkdownV2"""
            special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special_chars:
                text = text.replace(char, f'\\{char}')
            return text

        # Формируем текст профиля
        age_text = escape_markdown(f"{user.age} лет")
        height_text = escape_markdown(f"{user.height} см")
        weight_text_escaped = escape_markdown(weight_text)
        calories_text = escape_markdown(f"{user.target_calories} ккал")
        proteins_text = escape_markdown(f"{user.target_proteins}г")
        fats_text = escape_markdown(f"{user.target_fats}г")
        carbs_text = escape_markdown(f"{user.target_carbs}г")
        cooking_text_escaped = escape_markdown(cooking_time_text)

        profile_text = (
            "👤 *Твой профиль*\n\n"
            f"Возраст: {age_text}\n"
            f"Рост: {height_text}\n"
            f"{weight_text_escaped}\n"
            f"📊 *Целевые показатели на день:*\n"
            f"🔥 Калории: {calories_text}\n"
            f"🥩 Белки: {proteins_text}\n"
            f"🧈 Жиры: {fats_text}\n"
            f"🍞 Углеводы: {carbs_text}\n\n"
            f"⚙️ *Предпочтения:*\n"
            f"{cooking_text_escaped}\n"
            "────────────\n"
            "⚠️ _Напоминание: NutriAI не является медицинским сервисом\\.\n"
            "При проблемах со здоровьем обратитесь к врачу\\._\n"
            "────────────"
        )

        # Добавляем кнопки управления профилем
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [InlineKeyboardButton("⚖️ Изменить вес", callback_data="change_weight")],
            [InlineKeyboardButton("⏰ Изменить время на готовку", callback_data="change_cooking_time")],
            [InlineKeyboardButton("📦 Экспорт данных", callback_data="export_data")],
            [InlineKeyboardButton("🗑️ Удалить аккаунт", callback_data="delete_account")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]

        await safe_edit_or_send_message(
            query,
            profile_text,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def change_cooking_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик изменения времени на готовку"""
    query = update.callback_query

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    cooking_time_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡️ До 15 минут", callback_data="set_cooking_time_15")],
        [InlineKeyboardButton("⏱ 15-30 минут", callback_data="set_cooking_time_30")],
        [InlineKeyboardButton("🕐 30-60 минут", callback_data="set_cooking_time_60")],
        [InlineKeyboardButton("🕑 Больше часа", callback_data="set_cooking_time_90")],
        [InlineKeyboardButton("⏩ Не важно", callback_data="set_cooking_time_skip")],
        [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
    ])

    await safe_edit_or_send_message(
        query,
        "⏰ <b>Выбери предпочитаемое время на приготовление одного блюда:</b>\n\n"
        "Это влияет на подбор рецептов в планах питания.",
        reply_markup=cooking_time_keyboard,
        parse_mode='HTML'
    )


async def set_cooking_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение нового времени на готовку"""
    query = update.callback_query

    # Маппинг callback_data на минуты
    cooking_time_map = {
        "set_cooking_time_15": 15,
        "set_cooking_time_30": 30,
        "set_cooking_time_60": 60,
        "set_cooking_time_90": 90,
        "set_cooking_time_skip": None
    }

    cooking_time = cooking_time_map.get(query.data)

    # Сохраняем в БД
    async with async_session_maker() as session:
        from app.models.user import User
        from sqlalchemy import select

        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.preferred_cooking_time_minutes = cooking_time
            await session.commit()

            # Формируем текст подтверждения
            if cooking_time:
                time_text = f"до {cooking_time} минут"
            else:
                time_text = "любое время"

            await safe_edit_or_send_message(
                query,
                f"✅ Отлично! Время на готовку изменено на: {time_text}.\n\n"
                f"Теперь рецепты в планах питания будут подбираться с учетом этого времени.",
                reply_markup=back_to_menu_keyboard()
            )


async def change_weight_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик изменения веса"""
    query = update.callback_query

    await safe_edit_or_send_message(
        query,
        "⚖️ <b>Введи свой текущий вес в килограммах</b>\n\n"
        "Например: 75 или 68.5",
        parse_mode='HTML'
    )

    from app.bot.states import ProfileStates
    return ProfileStates.WAITING_NEW_WEIGHT


async def handle_new_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода нового веса"""
    try:
        new_weight = float(update.message.text.replace(",", "."))

        if new_weight < 30 or new_weight > 300:
            await update.message.reply_text(
                "❌ Пожалуйста, введи корректный вес в кг (от 30 до 300):"
            )
            from app.bot.states import ProfileStates
            return ProfileStates.WAITING_NEW_WEIGHT

        # Сохраняем новый вес
        async with async_session_maker() as session:
            from app.models.user import User
            from app.services.weight_service import WeightService
            from app.services.nutrition_calc import NutritionCalculator
            from sqlalchemy import select

            result = await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            user = result.scalar_one_or_none()

            if user:
                old_weight = user.current_weight

                # Добавляем запись в историю веса
                await WeightService.add_weight_entry(
                    user_id=user.id,
                    weight=new_weight,
                    session=session
                )

                # Обновляем текущий вес пользователя
                await WeightService.update_user_current_weight(
                    user=user,
                    new_weight=new_weight,
                    session=session
                )

                # Рассчитываем новый ИМТ
                bmi = NutritionCalculator.calculate_bmi(new_weight, user.height)
                bmi_category = NutritionCalculator.get_bmi_category(bmi)

                # Формируем текст подтверждения
                weight_diff = new_weight - old_weight
                if weight_diff > 0:
                    change_text = f"📈 +{abs(weight_diff):.1f} кг"
                elif weight_diff < 0:
                    change_text = f"📉 {weight_diff:.1f} кг"
                else:
                    change_text = "без изменений"

                await update.message.reply_text(
                    f"✅ <b>Вес успешно обновлен!</b>\n\n"
                    f"Предыдущий вес: {old_weight} кг\n"
                    f"Новый вес: {new_weight} кг\n"
                    f"Изменение: {change_text}\n\n"
                    f"📊 Твой ИМТ: {bmi} ({bmi_category})\n"
                    f"🎯 Целевой вес: {user.target_weight} кг",
                    parse_mode='HTML'
                )

                # Генерируем персонализированное сообщение от AI (если есть значимое изменение)
                if abs(weight_diff) >= 0.1:
                    try:
                        from app.services.weight_support_service import WeightSupportService

                        # Показываем индикатор печати
                        await update.message.chat.send_action("typing")

                        ai_message = await WeightSupportService.generate_weight_change_message(
                            user=user,
                            old_weight=old_weight,
                            new_weight=new_weight,
                            session=session
                        )

                        await update.message.reply_text(
                            ai_message,
                            reply_markup=back_to_menu_keyboard()
                        )
                    except Exception as e:
                        logger.error("Error generating AI weight message: {}", repr(e))
                        # Если AI не сработал, просто показываем меню
                        await update.message.reply_text(
                            "Что хочешь сделать дальше?",
                            reply_markup=back_to_menu_keyboard()
                        )
                else:
                    # Если изменения нет, просто показываем меню
                    await update.message.reply_text(
                        "Что хочешь сделать дальше?",
                        reply_markup=back_to_menu_keyboard()
                    )

                return ConversationHandler.END

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введи вес числом (например, 75 или 68.5):"
        )
        from app.bot.states import ProfileStates
        return ProfileStates.WAITING_NEW_WEIGHT


# Reports callback теперь обрабатывается через get_reports_conversation_handler


@track_command('wellness_insights')
async def wellness_insights_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда для получения AI-анализа паттернов самочувствия
    """
    user = update.effective_user

    await update.message.reply_text(
        "🔄 Анализирую ваши данные о самочувствии и питании...\n\n"
        "Это может занять несколько секунд."
    )

    async with async_session_maker() as session:
        from app.models.user import User
        from app.services.wellness_service import WellnessService
        from sqlalchemy import select

        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            await update.message.reply_text(
                "❌ Ошибка: пользователь не найден",
                reply_markup=back_to_menu_keyboard()
            )
            return

        # Запускаем анализ
        wellness_service = WellnessService()
        analysis = await wellness_service.analyze_wellness_patterns(
            session=session,
            user_id=db_user.id,
            days=14  # Анализируем последние 14 дней
        )

        if analysis.get("status") == "no_data":
            await update.message.reply_text(
                "📊 <b>Недостаточно данных</b>\n\n"
                "Для анализа нужно заполнять опросы о самочувствии после приемов пищи.\n\n"
                "💡 Опросы появляются автоматически через 30 минут после того, как вы добавляете еду.",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard()
            )
            return

        if analysis.get("status") == "error":
            await update.message.reply_text(
                f"❌ Ошибка при анализе: {analysis.get('message')}",
                reply_markup=back_to_menu_keyboard()
            )
            return

        # Формируем красивый ответ
        if "summary" in analysis:
            response = f"🌟 <b>Анализ самочувствия за 14 дней</b>\n\n"
            response += f"<b>Общий балл:</b> {analysis.get('overall_wellness_score', 'N/A')}/10\n\n"
            response += f"📝 <b>Резюме:</b>\n{analysis['summary']}\n\n"

            # Основные проблемы
            if analysis.get("key_issues"):
                response += "<b>⚠️ Основные проблемы:</b>\n"
                for issue in analysis["key_issues"][:3]:  # Топ-3
                    response += f"• {issue.get('issue')} ({issue.get('severity')})\n"
                response += "\n"

            # Рекомендации
            if analysis.get("recommendations"):
                response += "<b>💡 Рекомендации:</b>\n"
                for rec in analysis["recommendations"][:3]:  # Топ-3
                    response += f"• {rec.get('action')}\n"
                response += "\n"

            # Продукты
            if analysis.get("foods_to_increase"):
                foods = ", ".join(analysis["foods_to_increase"][:5])
                response += f"<b>✅ Увеличить:</b> {foods}\n"
            if analysis.get("foods_to_decrease"):
                foods = ", ".join(analysis["foods_to_decrease"][:5])
                response += f"<b>⛔️ Уменьшить:</b> {foods}\n"

            await update.message.reply_text(
                response,
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard()
            )
        else:
            # Если JSON не распарсился, отправляем текстовый анализ
            await update.message.reply_text(
                f"🌟 <b>Анализ самочувствия</b>\n\n{analysis.get('text_analysis', 'Анализ выполнен')}",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard()
            )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатия на кнопку 'Настройки'"""
    query = update.callback_query

    user = update.effective_user

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            await safe_edit_or_send_message(
                query,
                "❌ Пользователь не найден",
                reply_markup=back_to_menu_keyboard()
            )
            return

        # Формируем текст с текущими настройками
        reminders_status = "✅ Включены" if db_user.reminders_enabled else "❌ Выключены"

        settings_text = (
            "⚙️ <b>Настройки</b>\n\n"
            f"🔔 <b>Напоминания:</b> {reminders_status}\n"
        )

        if db_user.reminders_enabled:
            if db_user.breakfast_reminder_time:
                settings_text += f"  🌅 Завтрак: {db_user.breakfast_reminder_time}\n"
            if db_user.lunch_reminder_time:
                settings_text += f"  🌞 Обед: {db_user.lunch_reminder_time}\n"
            if db_user.dinner_reminder_time:
                settings_text += f"  🌙 Ужин: {db_user.dinner_reminder_time}\n"
            if db_user.snack_reminder_time:
                settings_text += f"  🍎 Перекус: {db_user.snack_reminder_time}\n"

    # Создаем кнопки настроек
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [InlineKeyboardButton("🔔 Настроить напоминания", callback_data="setup_reminders")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]

    await safe_edit_or_send_message(
        query,
        settings_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# Обработчик текстовых сообщений импортирован из app.bot.handlers.chat


# Обработчик фото импортирован из app.bot.handlers.photo


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    import traceback
    from telegram.error import TimedOut, NetworkError, RetryAfter, BadRequest

    error = context.error

    # Список некритичных ошибок, которые не требуют уведомления пользователя
    ignored_errors = (TimedOut, NetworkError, RetryAfter)

    # Логируем все ошибки
    logger.error(f"Update {update} caused error {error}")

    # Если это некритичная ошибка - не беспокоим пользователя
    if isinstance(error, ignored_errors):
        logger.warning(f"Ignored non-critical error: {type(error).__name__}")
        return

    # Специальная обработка BadRequest для устаревших callback queries и неизмененных сообщений
    if isinstance(error, BadRequest):
        error_msg = str(error).lower()

        # Если это ошибка устаревшего callback query
        if "query is too old" in error_msg or "query id is invalid" in error_msg:
            logger.warning(f"Callback query too old: {error}")

            # Если есть callback query, отправляем пользователю новое сообщение
            if update and update.callback_query:
                try:
                    await update.callback_query.message.reply_text(
                        "⏰ Эта кнопка устарела. Вот свежее меню:",
                        reply_markup=main_menu_keyboard()
                    )
                    logger.info("Sent fresh menu to user after old callback query")
                except Exception as e:
                    logger.error(f"Failed to send fresh menu: {e}")
            return

        # Если это ошибка "message is not modified" - просто игнорируем (сообщение уже актуально)
        if "message is not modified" in error_msg or "message can't be edited" in error_msg:
            logger.debug(f"Ignored non-critical BadRequest: {error}")
            return

        # Для других BadRequest ошибок просто логируем
        logger.warning(f"BadRequest error: {error}")
        return

    # Для серьезных ошибок логируем traceback
    logger.error("".join(traceback.format_exception(type(error), error, error.__traceback__)))

    # Показываем пользователю сообщение только при реальных ошибках
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "😔 Что-то пошло не так. Попробуй еще раз.\n\n"
                "Если проблема повторяется - напиши /start и начни заново."
            )
        except Exception as e:
            # Если не удалось отправить сообщение об ошибке - просто логируем
            logger.error("Failed to send error message to user: {}", repr(e))


async def check_expired_plans_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Периодическая задача для проверки и деактивации истёкших планов питания
    Запускается каждые 24 часа
    """
    from app.db.session import async_session_maker
    from app.services.meal_plan_service import MealPlanService

    try:
        async with async_session_maker() as session:
            count = await MealPlanService.deactivate_expired_plans(session)
            if count > 0:
                logger.info(f"Auto-deactivated {count} expired meal plans")
    except Exception as e:
        logger.error("Error in check_expired_plans_job: {}", repr(e), exc_info=True)


async def post_init(application: Application) -> None:
    """Инициализация базы данных и планировщика после создания приложения"""
    from app.db.session import init_db, engine
    await init_db()
    logger.info("Database initialized")

    # Debug: показываем значение CLOUDFLARE_WORKER_URL
    logger.info("CLOUDFLARE_WORKER_URL = {}", settings.CLOUDFLARE_WORKER_URL)

    # Инициализируем и запускаем планировщик для напоминаний
    scheduler = init_scheduler(application.bot)
    scheduler.start()
    logger.info("Reminder scheduler initialized and started")

    # Добавляем периодическую задачу для проверки истёкших планов
    # Запускается каждые 24 часа (86400 секунд)
    job_queue = application.job_queue
    if job_queue:
        # Запускаем первую проверку через 60 секунд после старта
        job_queue.run_once(check_expired_plans_job, when=60)
        # Затем запускаем каждые 24 часа
        job_queue.run_repeating(check_expired_plans_job, interval=86400, first=120)
        logger.info("Scheduled job for checking expired meal plans (every 24 hours)")

    # Устанавливаем информацию о боте для метрик
    set_bot_info(version="1.0.0", env=settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "production")
    logger.info("Bot metrics info set")

    # Инициализируем и запускаем MetricsUpdater для периодического обновления gauge метрик
    try:
        from app.celery_app import celery_app
        celery_instance = celery_app
    except ImportError:
        celery_instance = None
        logger.warning("Celery not available, some metrics will not be collected")

    metrics_updater = MetricsUpdater(
        db_pool=engine.pool if hasattr(engine, 'pool') else None,
        celery_app=celery_instance,
        update_interval=15  # Обновляем метрики каждые 15 секунд
    )
    await metrics_updater.start()
    logger.info("Metrics updater started (interval: 15s)")

    # Сохраняем ссылку на metrics_updater в application.bot_data для graceful shutdown
    application.bot_data['metrics_updater'] = metrics_updater


async def post_shutdown(application: Application) -> None:
    """Корректное завершение работы при остановке приложения"""
    logger.info("Shutting down bot...")

    # Останавливаем MetricsUpdater
    metrics_updater = application.bot_data.get('metrics_updater')
    if metrics_updater:
        logger.info("Stopping metrics updater...")
        await metrics_updater.stop()
        logger.info("Metrics updater stopped")

    logger.info("Bot shutdown completed")


def main():
    """Главная функция запуска бота"""
    logger.info("Starting NutriAI Bot...")

    # Запускаем Prometheus metrics HTTP сервер
    metrics_port = getattr(settings, 'METRICS_PORT', 8000)
    try:
        start_http_server(metrics_port)
        logger.info(f"Prometheus metrics server started on port {metrics_port}")
        logger.info(f"Metrics available at: http://0.0.0.0:{metrics_port}/metrics")
    except Exception as e:
        logger.error(f"Failed to start metrics server: {e}")
        logger.warning("Bot will continue without metrics endpoint")

    # Настраиваем таймауты для Telegram API (увеличены для работы с медленными сетями)
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,      # 30 сек на подключение
        read_timeout=30.0,          # 30 сек на чтение ответа
        write_timeout=30.0,         # 30 сек на отправку
        pool_timeout=10.0           # 10 сек на получение соединения из пула
    )

    # Создаем приложение с post_init/post_shutdown hooks для инициализации БД и корректного завершения
    # concurrent_updates=True позволяет обрабатывать обновления от разных пользователей параллельно
    application = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).request(request).post_init(post_init).post_shutdown(post_shutdown).concurrent_updates(True).build()

    # ConversationHandler для добавления еды по фото
    food_add_conversation = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO, photo_handler)],
        states={
            FoodAddStates.ASKING_VERIFICATION: [
                # Спрашиваем: распознано верно?
                CallbackQueryHandler(handle_verification, pattern="^verification_"),
                CallbackQueryHandler(cancel_food_add, pattern="^main_menu$")
            ],
            FoodAddStates.ASKING_CLARIFICATION: [
                # Ожидаем текстовое уточнение от пользователя
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_clarification),
                CallbackQueryHandler(cancel_food_add, pattern="^main_menu$")
            ],
            FoodAddStates.ASKING_INTENTION: [
                # Спрашиваем: будет есть или просто узнать
                CallbackQueryHandler(handle_food_intention, pattern="^intention_"),
                CallbackQueryHandler(cancel_food_add, pattern="^main_menu$")
            ],
            FoodAddStates.WAITING_MEAL_TYPE: [
                CallbackQueryHandler(meal_type_selected, pattern="^meal_type_"),
                CallbackQueryHandler(cancel_food_add, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_food_add, pattern="^main_menu$")
        ],
        per_message=False
    )

    # ConversationHandler для функции "Ресторан"
    restaurant_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(restaurant_start, pattern="^restaurant$")],
        states={
            RestaurantStates.ASKING_MOOD: [
                MessageHandler(filters.PHOTO, restaurant_photo_handler),
                CallbackQueryHandler(cancel_restaurant, pattern="^main_menu$")
            ],
            RestaurantStates.ASKING_MEAL_TIME: [
                CallbackQueryHandler(handle_mood_selection, pattern="^mood_"),
                CallbackQueryHandler(cancel_restaurant, pattern="^main_menu$")
            ],
            RestaurantStates.ANALYZING_MENU: [
                CallbackQueryHandler(analyze_menu_and_recommend, pattern="^restaurant_meal_"),
                CallbackQueryHandler(handle_restaurant_dish_selection, pattern="^restaurant_dish_"),
                CallbackQueryHandler(handle_restaurant_search_more, pattern="^restaurant_search_more$"),
                CallbackQueryHandler(handle_restaurant_manual_input, pattern="^restaurant_manual_input$"),
                CallbackQueryHandler(cancel_restaurant, pattern="^main_menu$")
            ],
            RestaurantStates.WAITING_MANUAL_DISH_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_restaurant_manual_dish_name),
                CallbackQueryHandler(cancel_restaurant, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_restaurant, pattern="^main_menu$")
        ],
        per_message=False
    )

    # ConversationHandler для настройки напоминаний
    reminder_setup_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(setup_reminders_start, pattern="^setup_reminders$")],
        states={
            ReminderSetupStates.CHOOSING_MEAL: [
                CallbackQueryHandler(select_meal_for_reminder, pattern="^reminder_meal_"),
                CallbackQueryHandler(toggle_reminders, pattern="^toggle_reminders$"),
                CallbackQueryHandler(cancel_reminder_setup, pattern="^main_menu$")
            ],
            ReminderSetupStates.ENTERING_TIME: [
                CallbackQueryHandler(set_reminder_time, pattern="^set_time_"),
                CallbackQueryHandler(delete_reminder, pattern="^delete_reminder$"),
                CallbackQueryHandler(request_custom_time, pattern="^custom_time$"),
                CallbackQueryHandler(select_meal_for_reminder, pattern="^reminder_meal_"),
                CallbackQueryHandler(setup_reminders_start, pattern="^setup_reminders$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_reminder_time),
                CallbackQueryHandler(cancel_reminder_setup, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_reminder_setup, pattern="^main_menu$")
        ],
        per_message=False,
        allow_reentry=True
    )

    # ConversationHandler для создания плана питания
    meal_plan_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(meal_plan_start, pattern="^meal_plan$|^create_new_plan$")],
        states={
            MealPlanStates.WAITING_PERIOD: [
                CallbackQueryHandler(meal_plan_period_selected, pattern="^plan_period_"),
                CallbackQueryHandler(reuse_weekly_plan_yes, pattern="^reuse_weekly_yes$"),
                CallbackQueryHandler(reuse_weekly_plan_no, pattern="^reuse_weekly_no$"),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.ASKING_START_TIMING: [
                CallbackQueryHandler(handle_start_timing, pattern="^start_timing_"),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.ASKING_BATCH_COOKING: [
                CallbackQueryHandler(handle_batch_cooking, pattern="^batch_"),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.ASKING_COOKING_TIME: [
                CallbackQueryHandler(handle_cooking_time_selection, pattern="^cooking_time_"),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.ASKING_PREFERENCES: [
                # Единый обработчик для всех вопросов о предпочтениях
                CallbackQueryHandler(handle_preference_response, pattern="^preferences_skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_preference_response),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.CHECKING_CHRONIC_CONDITIONS: [
                # Уточнение состояния хронических заболеваний (Этап 4 - доработка)
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chronic_conditions_response),
                CallbackQueryHandler(skip_chronic_conditions_check_callback, pattern="^skip_chronic_check$"),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.CHECKING_ACUTE_CONDITIONS: [
                # Проверка наличия острых состояний (Этап 4 - доработка)
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_acute_conditions_response),
                CallbackQueryHandler(skip_acute_conditions_callback, pattern="^skip_acute_check$"),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.ASKING_PRICE_CALCULATION: [
                # Подтверждение создания плана с медицинскими ограничениями
                CallbackQueryHandler(confirm_medical_generation_callback, pattern="^confirm_medical_generation$"),
                # Вопрос о необходимости расчёта цены
                CallbackQueryHandler(handle_price_calculation_yes, pattern="^price_yes$"),
                CallbackQueryHandler(handle_price_calculation_no, pattern="^price_no$"),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.ASKING_SHOP_PREFERENCE: [
                # Вопрос о предпочтениях по магазинам (один или несколько)
                CallbackQueryHandler(handle_shop_single, pattern="^shop_single$"),
                CallbackQueryHandler(handle_shop_multiple, pattern="^shop_multiple$"),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ],
            MealPlanStates.ASKING_FEEDBACK: [
                # Обработчики обратной связи после создания плана
                CallbackQueryHandler(handle_feedback_positive, pattern="^feedback_positive$"),
                CallbackQueryHandler(handle_feedback_negative, pattern="^feedback_negative$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            MealPlanStates.ASKING_CHANGES: [
                # Обработчик запросов на изменение плана
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_change_request),
                CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_meal_plan, pattern="^main_menu$")
        ],
        per_message=False,
        allow_reentry=True
    )

    # ConversationHandler для изменения веса в профиле
    from app.bot.states import ProfileStates
    change_weight_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(change_weight_callback, pattern="^change_weight$")],
        states={
            ProfileStates.WAITING_NEW_WEIGHT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_weight),
                CallbackQueryHandler(profile_callback, pattern="^profile$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ],
        per_message=False
    )

    # ConversationHandler для управления продуктами дома
    pantry_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(pantry_start, pattern="^pantry$"),
            CallbackQueryHandler(pantry_create_plan_start, pattern="^pantry_create_plan$")
        ],
        states={
            PantryStates.WAITING_PRODUCTS_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pantry_process_input),
                CallbackQueryHandler(pantry_start, pattern="^pantry$")
            ],
            PantryStates.REVIEWING_FOR_PLAN: [
                CallbackQueryHandler(pantry_edit_product_for_plan, pattern="^pantry_edit_for_plan_"),
                CallbackQueryHandler(pantry_confirm_and_create_plan, pattern="^pantry_confirm_create_plan$"),
                CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
            ],
            PantryStates.EDITING_PRODUCT_QUANTITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pantry_save_edited_quantity)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(main_menu_callback, pattern="^main_menu$")
        ],
        per_message=False,
        allow_reentry=True
    )

    # ConversationHandler для настройки напоминаний после создания плана
    reminder_settings_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(reminder_setup_start, pattern="^reminder_setup_start$")],
        states={
            ReminderSettingsStates.WAITING_CUSTOM_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reminder_process_custom_time)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_reminder_setup, pattern="^main_menu$")
        ],
        per_message=False,
        allow_reentry=True
    )

    # Добавляем обработчики
    # ВАЖНО: порядок имеет значение! ConversationHandler с более специфичными условиями должны быть первыми
    application.add_handler(onboarding_conversation)
    application.add_handler(change_weight_conversation)  # Обработчик изменения веса
    application.add_handler(pantry_conversation)  # Обработчик продуктов дома
    application.add_handler(reminder_settings_conversation)  # Обработчик настройки напоминаний после создания плана
    application.add_handler(medical_analysis_conversation)  # Обработчик медицинских анализов - ПЕРЕД food_add_conversation!
    application.add_handler(restaurant_conversation)  # Обработчик функции "Ресторан" - ПЕРЕД food_add_conversation!
    application.add_handler(food_add_conversation)  # Обработчик фото с ConversationHandler (перехватывает ВСЕ фото)
    application.add_handler(meal_plan_conversation)  # Обработчик плана питания
    application.add_handler(reminder_setup_conversation)  # Обработчик настройки напоминаний
    application.add_handler(get_reports_conversation_handler())  # Обработчик отчетов
    application.add_handler(wellness_survey_conversation)  # Обработчик опросов о самочувствии
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("clear_chat", clear_chat_command))
    application.add_handler(CommandHandler("chat_stats", chat_stats_command))
    application.add_handler(CommandHandler("wellness_insights", wellness_insights_command))

    # Команды управления конфиденциальностью (152-ФЗ)
    application.add_handler(CommandHandler("privacy_settings", privacy_settings_command))
    application.add_handler(CommandHandler("export_data", export_data_callback))
    application.add_handler(CommandHandler("delete_account", delete_account_callback))

    # Callback handlers для кнопок
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    application.add_handler(CallbackQueryHandler(add_food_callback, pattern="^add_food$"))
    application.add_handler(CallbackQueryHandler(diary_callback, pattern="^diary$"))
    application.add_handler(CallbackQueryHandler(delete_meal_callback, pattern="^delete_meal_"))
    application.add_handler(CallbackQueryHandler(diary_edit_list_callback, pattern="^diary_edit_list$"))
    application.add_handler(CallbackQueryHandler(diary_delete_list_callback, pattern="^diary_delete_list$"))
    application.add_handler(CallbackQueryHandler(diary_delete_meal_callback, pattern="^diary_delete_"))

    # Callback handlers для редактирования приемов пищи
    application.add_handler(CallbackQueryHandler(remove_food_from_meal_callback, pattern="^remove_food_from_meal_"))
    application.add_handler(CallbackQueryHandler(delete_food_callback, pattern="^delete_food_"))
    application.add_handler(CallbackQueryHandler(delete_whole_meal_callback, pattern="^delete_whole_meal_"))
    application.add_handler(CallbackQueryHandler(add_food_to_meal_callback, pattern="^add_food_to_meal_"))
    application.add_handler(CallbackQueryHandler(diary_edit_meal_callback, pattern="^diary_edit_"))

    application.add_handler(CallbackQueryHandler(ai_chat_callback, pattern="^ai_chat$"))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile$"))
    application.add_handler(CallbackQueryHandler(settings_callback, pattern="^settings$"))

    # Callback handlers для управления конфиденциальностью (152-ФЗ)
    application.add_handler(CallbackQueryHandler(export_data_callback, pattern="^export_data$"))
    application.add_handler(CallbackQueryHandler(delete_account_callback, pattern="^delete_account$"))
    application.add_handler(CallbackQueryHandler(confirm_delete_account_callback, pattern="^confirm_delete$"))
    application.add_handler(CallbackQueryHandler(revoke_consent_callback, pattern="^revoke_consent$"))
    application.add_handler(CallbackQueryHandler(cancel_privacy_action, pattern="^privacy_settings$"))

    # Callback handlers для плана питания
    application.add_handler(CallbackQueryHandler(view_meal_plan, pattern="^view_plan_"))
    application.add_handler(CallbackQueryHandler(view_shopping_list, pattern="^shopping_list_"))

    # Глобальные обработчики для feedback кнопок (работают вне ConversationHandler)
    # Используются когда уведомление приходит от Celery задачи
    application.add_handler(CallbackQueryHandler(global_feedback_positive_callback, pattern="^feedback_positive_\\d+$"))
    application.add_handler(CallbackQueryHandler(global_feedback_negative_callback, pattern="^feedback_negative_\\d+$"))

    # Callback handlers для настроек времени готовки
    application.add_handler(CallbackQueryHandler(change_cooking_time_callback, pattern="^change_cooking_time$"))
    application.add_handler(CallbackQueryHandler(set_cooking_time_callback, pattern="^set_cooking_time_"))

    # Callback handlers для ресторана (отложенные уточнения)
    application.add_handler(CallbackQueryHandler(handle_restaurant_used_response, pattern="^restaurant_used_"))
    application.add_handler(CallbackQueryHandler(handle_restaurant_dish_selection, pattern="^restaurant_dish_"))

    # Callback handlers для учета шагов
    application.add_handler(CallbackQueryHandler(handle_steps_skip, pattern="^steps_skip$"))
    application.add_handler(CallbackQueryHandler(handle_steps_range, pattern="^steps_range_"))

    # Callback handlers для продуктов дома
    application.add_handler(CallbackQueryHandler(pantry_add_start, pattern="^pantry_add$"))
    application.add_handler(CallbackQueryHandler(pantry_delete_list, pattern="^pantry_delete_list$"))
    application.add_handler(CallbackQueryHandler(pantry_delete_item, pattern="^pantry_delete_"))

    # Callback handlers для настройки напоминаний после создания плана
    application.add_handler(CallbackQueryHandler(reminder_setup_yes, pattern="^reminder_yes$"))
    application.add_handler(CallbackQueryHandler(reminder_setup_no, pattern="^reminder_no$"))
    application.add_handler(CallbackQueryHandler(reminder_setup_standard, pattern="^reminder_standard$"))
    application.add_handler(CallbackQueryHandler(reminder_setup_custom, pattern="^reminder_custom$"))

    # Callback handlers для выбора рекомендованных блюд
    application.add_handler(CallbackQueryHandler(handle_meal_variant_choice, pattern="^meal_rec_variant_"))
    application.add_handler(CallbackQueryHandler(handle_meal_cancel, pattern="^meal_rec_cancel$"))
    application.add_handler(CallbackQueryHandler(handle_risky_choice, pattern="^meal_choice_risky$"))
    application.add_handler(CallbackQueryHandler(handle_safe_choice, pattern="^meal_choice_safe$"))

    # ConversationHandler для ввода своего варианта блюда
    custom_meal_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_custom_meal_start, pattern="^meal_rec_custom$")],
        states={
            WAITING_CUSTOM_MEAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_meal_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel_custom_meal)],
        allow_reentry=True
    )
    application.add_handler(custom_meal_conversation)

    # ConversationHandler для редактирования порции
    edit_portion_conversation = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_portion_start_callback, pattern="^edit_portion_")],
        states={
            WAITING_PORTION_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_portion_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel_edit_portion)],
        allow_reentry=True
    )
    application.add_handler(edit_portion_conversation)

    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message_handler))

    # Обработчик ошибок
    application.add_error_handler(error_handler)

    logger.info("Bot started successfully!")

    # === ВЫБОР РЕЖИМА: WEBHOOK ИЛИ POLLING ===
    if settings.USE_WEBHOOK:
        # WEBHOOK MODE
        logger.info("="*60)
        logger.info("Starting in WEBHOOK mode")
        logger.info(f"Webhook URL: {settings.WEBHOOK_URL}")
        logger.info(f"Listening on: {settings.WEBHOOK_LISTEN}:{settings.WEBHOOK_PORT}")
        logger.info("="*60)

        # Настраиваем webhook
        if settings.WEBHOOK_SSL_CERT and settings.WEBHOOK_SSL_KEY:
            # С собственным SSL сертификатом
            application.run_webhook(
                listen=settings.WEBHOOK_LISTEN,
                port=settings.WEBHOOK_PORT,
                url_path=settings.WEBHOOK_PATH,
                webhook_url=settings.WEBHOOK_URL,
                secret_token=settings.WEBHOOK_SECRET,
                cert=settings.WEBHOOK_SSL_CERT,
                key=settings.WEBHOOK_SSL_KEY,
                allowed_updates=Update.ALL_TYPES
            )
        else:
            # Без SSL (nginx делает SSL termination)
            application.run_webhook(
                listen=settings.WEBHOOK_LISTEN,
                port=settings.WEBHOOK_PORT,
                url_path=settings.WEBHOOK_PATH,
                webhook_url=settings.WEBHOOK_URL,
                secret_token=settings.WEBHOOK_SECRET,
                allowed_updates=Update.ALL_TYPES
            )
    else:
        # POLLING MODE (текущий режим)
        logger.info("="*60)
        logger.info("Starting in POLLING mode")
        logger.info("Note: For production with >200 users, consider switching to WEBHOOK mode")
        logger.info("="*60)

        # Запускаем бота (run_polling сам управляет event loop)
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
