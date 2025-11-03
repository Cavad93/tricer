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
