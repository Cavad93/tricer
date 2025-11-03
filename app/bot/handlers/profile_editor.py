"""
Обработчики для редактирования профиля (152-ФЗ: право на исправление данных)

Функции:
- Редактирование wellness данных (хронические заболевания, удаленные органы)
- Редактирование пищевых исключений
- Редактирование основных данных профиля
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.states import ProfileStates
from app.db.session import async_session_maker
from app.models.user import User, Goal, ActivityLevel, DietType, BudgetCategory
from sqlalchemy import select

logger = logging.getLogger(__name__)


# ==============================================
# WELLNESS ДАННЫЕ (фильтр контента)
# ==============================================

async def edit_chronic_conditions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало редактирования хронических заболеваний
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Показываем текущие данные
        current_conditions = user.chronic_conditions if user.chronic_conditions else []
        current_text = ", ".join(current_conditions) if current_conditions else "Не указано"

        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить все", callback_data="clear_chronic_conditions")],
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📋 <b>Редактирование хронических заболеваний</b>\n\n"
            f"<b>Текущие данные:</b> {current_text}\n\n"
            f"⚠️ <b>Напоминание:</b> Эти данные используются как ФИЛЬТР КОНТЕНТА - "
            f"чтобы исключить нежелательные продукты из рациона (не лечебная диета!).\n\n"
            f"Введи новый список через запятую:\n"
            f"<i>Например: диабет 2 типа, гипертония, гастрит</i>\n\n"
            f"Или нажми кнопку ниже:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_CHRONIC_CONDITIONS


async def save_chronic_conditions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение отредактированных хронических заболеваний
    """
    if not update.message or not update.message.text:
        return ProfileStates.EDITING_CHRONIC_CONDITIONS

    conditions_text = update.message.text.strip()
    conditions = [c.strip() for c in conditions_text.split(",") if c.strip()]

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.chronic_conditions = conditions
        await session.commit()

        logger.info(f"User {user.id} updated chronic_conditions: {conditions}")

    conditions_display = ", ".join(conditions) if conditions else "Не указано"

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ <b>Данные обновлены!</b>\n\n"
        f"<b>Хронические заболевания:</b> {conditions_display}\n\n"
        f"Эти данные будут использоваться как фильтр контента при составлении рациона.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


async def clear_chronic_conditions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Очистка хронических заболеваний
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.chronic_conditions = []
        await session.commit()

        logger.info(f"User {user.id} cleared chronic_conditions")

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "✅ <b>Данные удалены!</b>\n\n"
        "Хронические заболевания больше не будут учитываться при составлении рациона.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


async def edit_removed_organs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало редактирования удаленных органов
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Показываем текущие данные
        current_organs = user.removed_organs if user.removed_organs else []
        current_text = ", ".join(current_organs) if current_organs else "Не указано"

        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить все", callback_data="clear_removed_organs")],
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🔧 <b>Редактирование удаленных органов</b>\n\n"
            f"<b>Текущие данные:</b> {current_text}\n\n"
            f"⚠️ <b>Напоминание:</b> Эти данные используются как ФИЛЬТР КОНТЕНТА - "
            f"чтобы исключить нежелательные продукты из рациона (не лечебная диета!).\n\n"
            f"Введи новый список через запятую:\n"
            f"<i>Например: желчный пузырь, аппендикс</i>\n\n"
            f"Или нажми кнопку ниже:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_REMOVED_ORGANS


async def save_removed_organs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение отредактированных удаленных органов
    """
    if not update.message or not update.message.text:
        return ProfileStates.EDITING_REMOVED_ORGANS

    organs_text = update.message.text.strip()
    organs = [o.strip() for o in organs_text.split(",") if o.strip()]

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.removed_organs = organs
        await session.commit()

        logger.info(f"User {user.id} updated removed_organs: {organs}")

    organs_display = ", ".join(organs) if organs else "Не указано"

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ <b>Данные обновлены!</b>\n\n"
        f"<b>Удаленные органы:</b> {organs_display}\n\n"
        f"Эти данные будут использоваться как фильтр контента при составлении рациона.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


async def clear_removed_organs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Очистка удаленных органов
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.removed_organs = []
        await session.commit()

        logger.info(f"User {user.id} cleared removed_organs")

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "✅ <b>Данные удалены!</b>\n\n"
        "Удаленные органы больше не будут учитываться при составлении рациона.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


# ==============================================
# ПИЩЕВЫЕ ИСКЛЮЧЕНИЯ
# ==============================================

async def edit_food_exclusions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало редактирования пищевых исключений
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Показываем текущие данные
        current_exclusions = user.food_exclusions if user.food_exclusions else []
        current_text = ", ".join(current_exclusions) if current_exclusions else "Не указано"

        keyboard = [
            [InlineKeyboardButton("🗑️ Очистить все", callback_data="clear_food_exclusions")],
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"❗ <b>Редактирование пищевых исключений</b>\n\n"
            f"<b>Текущие данные:</b> {current_text}\n\n"
            f"Укажи продукты, которые КАТЕГОРИЧЕСКИ не хочешь в рационе:\n"
            f"<i>Например: молоко, грибы, рыба, свинина</i>\n\n"
            f"Введи новый список через запятую или нажми кнопку ниже:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_FOOD_EXCLUSIONS


async def save_food_exclusions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение отредактированных пищевых исключений
    """
    if not update.message or not update.message.text:
        return ProfileStates.EDITING_FOOD_EXCLUSIONS

    exclusions_text = update.message.text.strip()
    exclusions = [e.strip() for e in exclusions_text.split(",") if e.strip()]

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.food_exclusions = exclusions
        await session.commit()

        logger.info(f"User {user.id} updated food_exclusions: {exclusions}")

    exclusions_display = ", ".join(exclusions) if exclusions else "Не указано"

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ <b>Данные обновлены!</b>\n\n"
        f"<b>Пищевые исключения:</b> {exclusions_display}\n\n"
        f"Эти продукты не будут включаться в рацион.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


async def clear_food_exclusions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Очистка пищевых исключений
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.food_exclusions = []
        await session.commit()

        logger.info(f"User {user.id} cleared food_exclusions")

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "✅ <b>Данные удалены!</b>\n\n"
        "Пищевые исключения сброшены. Все продукты теперь разрешены.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


# ==============================================
# ОСНОВНЫЕ ДАННЫЕ ПРОФИЛЯ
# ==============================================

async def edit_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало редактирования имени
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        current_name = user.preferred_name or "Не указано"

        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"✏️ <b>Редактирование имени</b>\n\n"
            f"<b>Текущее имя:</b> {current_name}\n\n"
            f"Введи новое имя:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_NAME


async def save_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение нового имени
    """
    if not update.message or not update.message.text:
        return ProfileStates.EDITING_NAME

    new_name = update.message.text.strip()

    if len(new_name) > 50:
        await update.message.reply_text(
            "❌ Имя слишком длинное. Максимум 50 символов."
        )
        return ProfileStates.EDITING_NAME

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.preferred_name = new_name
        await session.commit()

        logger.info(f"User {user.id} updated preferred_name: {new_name}")

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ <b>Имя обновлено!</b>\n\n"
        f"<b>Новое имя:</b> {new_name}",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


async def edit_height_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало редактирования роста
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        current_height = user.height

        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"📏 <b>Редактирование роста</b>\n\n"
            f"<b>Текущий рост:</b> {current_height} см\n\n"
            f"Введи новый рост в сантиметрах (например: 175):",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_HEIGHT


async def save_height_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение нового роста
    """
    if not update.message or not update.message.text:
        return ProfileStates.EDITING_HEIGHT

    try:
        new_height = int(update.message.text.strip())

        if new_height < 100 or new_height > 250:
            await update.message.reply_text(
                "❌ Некорректное значение. Рост должен быть от 100 до 250 см."
            )
            return ProfileStates.EDITING_HEIGHT

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введи число (например: 175)."
        )
        return ProfileStates.EDITING_HEIGHT

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.height = new_height

        # Пересчитываем целевые калории и БЖУ
        from app.services.nutrition_calc import NutritionCalculator
        nutrition = NutritionCalculator.calculate_daily_nutrition(
            weight=user.current_weight,
            height=user.height,
            age=user.age,
            gender=user.gender,
            activity_level=user.activity_level,
            goal=user.goal
        )

        user.target_calories = nutrition["calories"]
        user.target_proteins = nutrition["proteins"]
        user.target_fats = nutrition["fats"]
        user.target_carbs = nutrition["carbs"]

        await session.commit()

        logger.info(f"User {user.id} updated height: {new_height}, recalculated nutrition")

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ <b>Рост обновлен!</b>\n\n"
        f"<b>Новый рост:</b> {new_height} см\n\n"
        f"Целевые калории и БЖУ пересчитаны автоматически.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


async def edit_target_weight_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало редактирования целевого веса
    """
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        current_weight = user.target_weight

        keyboard = [
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🎯 <b>Редактирование целевого веса</b>\n\n"
            f"<b>Текущий целевой вес:</b> {current_weight} кг\n\n"
            f"Введи новый целевой вес в килограммах (например: 70):",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_TARGET_WEIGHT


async def save_target_weight_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение нового целевого веса
    """
    if not update.message or not update.message.text:
        return ProfileStates.EDITING_TARGET_WEIGHT

    try:
        new_target_weight = float(update.message.text.strip().replace(',', '.'))

        if new_target_weight < 30 or new_target_weight > 300:
            await update.message.reply_text(
                "❌ Некорректное значение. Вес должен быть от 30 до 300 кг."
            )
            return ProfileStates.EDITING_TARGET_WEIGHT

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введи число (например: 70 или 70.5)."
        )
        return ProfileStates.EDITING_TARGET_WEIGHT

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.target_weight = new_target_weight

        # Пересчитываем целевые калории и БЖУ
        from app.services.nutrition_calc import NutritionCalculator
        nutrition = NutritionCalculator.calculate_daily_nutrition(
            weight=user.current_weight,
            height=user.height,
            age=user.age,
            gender=user.gender,
            activity_level=user.activity_level,
            goal=user.goal
        )

        user.target_calories = nutrition["calories"]
        user.target_proteins = nutrition["proteins"]
        user.target_fats = nutrition["fats"]
        user.target_carbs = nutrition["carbs"]

        await session.commit()

        logger.info(f"User {user.id} updated target_weight: {new_target_weight}, recalculated nutrition")

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ <b>Целевой вес обновлен!</b>\n\n"
        f"<b>Новый целевой вес:</b> {new_target_weight} кг\n\n"
        f"Целевые калории и БЖУ пересчитаны автоматически.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


async def edit_goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начало редактирования цели
    """
    query = update.callback_query
    await query.answer()

    goal_names = {
        Goal.WEIGHT_LOSS: "Похудение",
        Goal.WEIGHT_GAIN: "Набор массы",
        Goal.MAINTENANCE: "Поддержание веса",
        Goal.HEALTH: "Здоровое питание"
    }

    keyboard = [
        [InlineKeyboardButton("📉 Похудение", callback_data="set_goal_weight_loss")],
        [InlineKeyboardButton("📈 Набор массы", callback_data="set_goal_weight_gain")],
        [InlineKeyboardButton("⚖️ Поддержание веса", callback_data="set_goal_maintenance")],
        [InlineKeyboardButton("🥗 Здоровое питание", callback_data="set_goal_health")],
        [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "🎯 <b>Редактирование цели</b>\n\n"
        "Выбери новую цель:",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ProfileStates.EDITING_GOAL


async def save_goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Сохранение новой цели
    """
    query = update.callback_query
    await query.answer()

    goal_map = {
        "set_goal_weight_loss": Goal.WEIGHT_LOSS,
        "set_goal_weight_gain": Goal.WEIGHT_GAIN,
        "set_goal_maintenance": Goal.MAINTENANCE,
        "set_goal_health": Goal.HEALTH
    }

    new_goal = goal_map.get(query.data)
    if not new_goal:
        await query.edit_message_text("❌ Неизвестная цель")
        return ConversationHandler.END

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        user.goal = new_goal

        # Пересчитываем целевые калории и БЖУ
        from app.services.nutrition_calc import NutritionCalculator
        nutrition = NutritionCalculator.calculate_daily_nutrition(
            weight=user.current_weight,
            height=user.height,
            age=user.age,
            gender=user.gender,
            activity_level=user.activity_level,
            goal=user.goal
        )

        user.target_calories = nutrition["calories"]
        user.target_proteins = nutrition["proteins"]
        user.target_fats = nutrition["fats"]
        user.target_carbs = nutrition["carbs"]

        await session.commit()

        logger.info(f"User {user.id} updated goal: {new_goal.value}, recalculated nutrition")

    goal_names = {
        Goal.WEIGHT_LOSS: "Похудение",
        Goal.WEIGHT_GAIN: "Набор массы",
        Goal.MAINTENANCE: "Поддержание веса",
        Goal.HEALTH: "Здоровое питание"
    }

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ <b>Цель обновлена!</b>\n\n"
        f"<b>Новая цель:</b> {goal_names[new_goal]}\n\n"
        f"Целевые калории и БЖУ пересчитаны автоматически.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


# ============================================================================
# РЕДАКТИРОВАНИЕ УРОВНЯ АКТИВНОСТИ (activity_level)
# ============================================================================

async def edit_activity_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования уровня активности"""
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Показываем текущий уровень активности
        activity_names = {
            ActivityLevel.MINIMAL: "😴 Минимальная (сидячий образ жизни)",
            ActivityLevel.LOW: "🚶 Низкая (1-3 тренировки/неделя)",
            ActivityLevel.MEDIUM: "🏃 Средняя (3-5 тренировок/неделя)",
            ActivityLevel.HIGH: "💪 Высокая (5-7 тренировок/неделя)",
            ActivityLevel.VERY_HIGH: "🔥 Очень высокая (2+ тренировки/день)"
        }

        current_text = activity_names.get(user.activity_level, "Не указано")

        # Импортируем готовую клавиатуру
        from app.bot.keyboards import activity_level_keyboard
        keyboard_markup = activity_level_keyboard()

        # Добавляем кнопку отмены
        keyboard = keyboard_markup.inline_keyboard + [
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🏃 <b>Редактирование уровня активности</b>\n\n"
            f"<b>Текущий уровень:</b> {current_text}\n\n"
            f"⚠️ <b>Важно:</b> При изменении уровня активности целевые калории и БЖУ "
            f"будут автоматически пересчитаны.\n\n"
            f"Выбери новый уровень активности:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_ACTIVITY_LEVEL


async def save_activity_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение выбранного уровня активности с пересчётом КБЖУ"""
    query = update.callback_query
    await query.answer()

    # Парсим callback_data для получения значения
    activity_map = {
        "activity_minimal": ActivityLevel.MINIMAL,
        "activity_low": ActivityLevel.LOW,
        "activity_medium": ActivityLevel.MEDIUM,
        "activity_high": ActivityLevel.HIGH,
        "activity_very_high": ActivityLevel.VERY_HIGH
    }

    new_activity = activity_map.get(query.data)
    if not new_activity:
        await query.edit_message_text("❌ Неверный уровень активности")
        return ConversationHandler.END

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Сохраняем новый уровень активности
        user.activity_level = new_activity

        # Пересчитываем КБЖУ
        from app.services.nutrition_service import calculate_nutrition_targets
        nutrition = calculate_nutrition_targets(
            weight=user.weight,
            height=user.height,
            age=user.age,
            sex=user.sex,
            activity_level=user.activity_level,
            goal=user.goal
        )

        user.target_calories = nutrition["calories"]
        user.target_protein = nutrition["protein"]
        user.target_fats = nutrition["fats"]
        user.target_carbs = nutrition["carbs"]

        await session.commit()

    activity_names = {
        ActivityLevel.MINIMAL: "😴 Минимальная (сидячий образ жизни)",
        ActivityLevel.LOW: "🚶 Низкая (1-3 тренировки/неделя)",
        ActivityLevel.MEDIUM: "🏃 Средняя (3-5 тренировок/неделя)",
        ActivityLevel.HIGH: "💪 Высокая (5-7 тренировок/неделя)",
        ActivityLevel.VERY_HIGH: "🔥 Очень высокая (2+ тренировки/день)"
    }

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ <b>Уровень активности обновлён!</b>\n\n"
        f"<b>Новый уровень:</b> {activity_names[new_activity]}\n\n"
        f"Целевые калории и БЖУ пересчитаны автоматически.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


# ============================================================================
# РЕДАКТИРОВАНИЕ ТИПА ПИТАНИЯ (diet_type)
# ============================================================================

async def edit_diet_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования типа питания"""
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Показываем текущий тип питания
        diet_names = {
            DietType.OMNIVORE: "🍖 Всеядный",
            DietType.VEGETARIAN: "🥗 Вегетарианец",
            DietType.VEGAN: "🌱 Веган",
            DietType.PESCATARIAN: "🐟 Пескетарианец"
        }

        current_text = diet_names.get(user.diet_type, "Не указано")

        # Импортируем готовую клавиатуру
        from app.bot.keyboards import diet_type_keyboard
        keyboard_markup = diet_type_keyboard()

        # Добавляем кнопку отмены
        keyboard = keyboard_markup.inline_keyboard + [
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🍽️ <b>Редактирование типа питания</b>\n\n"
            f"<b>Текущий тип:</b> {current_text}\n\n"
            f"⚠️ <b>Важно:</b> Тип питания влияет на формирование рациона - "
            f"из меню будут исключены неподходящие продукты.\n\n"
            f"Выбери новый тип питания:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_DIET_TYPE


async def save_diet_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение выбранного типа питания"""
    query = update.callback_query
    await query.answer()

    # Парсим callback_data для получения значения
    diet_map = {
        "diet_omnivore": DietType.OMNIVORE,
        "diet_vegetarian": DietType.VEGETARIAN,
        "diet_vegan": DietType.VEGAN,
        "diet_pescatarian": DietType.PESCATARIAN
    }

    new_diet = diet_map.get(query.data)
    if not new_diet:
        await query.edit_message_text("❌ Неверный тип питания")
        return ConversationHandler.END

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Сохраняем новый тип питания
        user.diet_type = new_diet
        await session.commit()

    diet_names = {
        DietType.OMNIVORE: "🍖 Всеядный",
        DietType.VEGETARIAN: "🥗 Вегетарианец",
        DietType.VEGAN: "🌱 Веган",
        DietType.PESCATARIAN: "🐟 Пескетарианец"
    }

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ <b>Тип питания обновлён!</b>\n\n"
        f"<b>Новый тип:</b> {diet_names[new_diet]}\n\n"
        f"Изменения будут учтены при формировании следующих рационов.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


# ============================================================================
# РЕДАКТИРОВАНИЕ БЮДЖЕТНОЙ КАТЕГОРИИ (budget_category)
# ============================================================================

async def edit_budget_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало редактирования бюджетной категории"""
    query = update.callback_query
    await query.answer()

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Показываем текущий бюджет
        budget_names = {
            BudgetCategory.ECONOMY: "💰 Эконом",
            BudgetCategory.NORMAL: "💵 Норм",
            BudgetCategory.PREMIUM: "💎 Премиум"
        }

        current_text = budget_names.get(user.budget_category, "Не указано")

        # Импортируем готовую клавиатуру
        from app.bot.keyboards import budget_category_keyboard
        keyboard_markup = budget_category_keyboard()

        # Добавляем кнопку отмены
        keyboard = keyboard_markup.inline_keyboard + [
            [InlineKeyboardButton("❌ Отмена", callback_data="profile")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"💰 <b>Редактирование бюджетной категории</b>\n\n"
            f"<b>Текущий бюджет:</b> {current_text}\n\n"
            f"⚠️ <b>Важно:</b> Бюджет влияет на формирование списка покупок - "
            f"подбираются продукты в соответствующем ценовом диапазоне.\n\n"
            f"Выбери новую бюджетную категорию:",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )

    return ProfileStates.EDITING_BUDGET


async def save_budget_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение выбранной бюджетной категории"""
    query = update.callback_query
    await query.answer()

    # Парсим callback_data для получения значения
    budget_map = {
        "budget_economy": BudgetCategory.ECONOMY,
        "budget_normal": BudgetCategory.NORMAL,
        "budget_premium": BudgetCategory.PREMIUM
    }

    new_budget = budget_map.get(query.data)
    if not new_budget:
        await query.edit_message_text("❌ Неверная бюджетная категория")
        return ConversationHandler.END

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await query.edit_message_text("❌ Пользователь не найден")
            return ConversationHandler.END

        # Сохраняем новый бюджет
        user.budget_category = new_budget
        await session.commit()

    budget_names = {
        BudgetCategory.ECONOMY: "💰 Эконом",
        BudgetCategory.NORMAL: "💵 Норм",
        BudgetCategory.PREMIUM: "💎 Премиум"
    }

    keyboard = [
        [InlineKeyboardButton("👤 Вернуться в профиль", callback_data="profile")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"✅ <b>Бюджетная категория обновлена!</b>\n\n"
        f"<b>Новый бюджет:</b> {budget_names[new_budget]}\n\n"
        f"Изменения будут учтены при формировании следующих списков покупок.",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    return ConversationHandler.END


# ============================================================================
# ОБРАБОТЧИК ОТМЕНЫ
# ============================================================================

# Обработчик отмены редактирования
async def cancel_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отмена редактирования и возврат в профиль
    """
    query = update.callback_query
    if query:
        await query.answer()

    # Возвращаемся в профиль
    from app.bot.main import profile_callback
    return await profile_callback(update, context)
