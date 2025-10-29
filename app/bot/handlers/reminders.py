"""
Обработчики для настройки напоминаний о приемах пищи
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger
from sqlalchemy import select

from app.models.user import User
from app.db.session import async_session_maker
from app.bot.keyboards import back_to_menu_keyboard


# Состояния для конфигурации напоминаний
class ReminderSetupStates:
    CHOOSING_MEAL = 1
    ENTERING_TIME = 2


async def setup_reminders_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало настройки напоминаний"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            await query.edit_message_text(
                "❌ Пользователь не найден",
                reply_markup=back_to_menu_keyboard()
            )
            return ConversationHandler.END

        # Показываем меню настройки напоминаний
        reminders_text = (
            "🔔 <b>Настройка напоминаний</b>\n\n"
            "Я могу напоминать тебе о приемах пищи по расписанию!\n\n"
            "<b>Текущие настройки:</b>\n"
        )

        if db_user.breakfast_reminder_time:
            reminders_text += f"🌅 Завтрак: {db_user.breakfast_reminder_time}\n"
        else:
            reminders_text += "🌅 Завтрак: не настроен\n"

        if db_user.lunch_reminder_time:
            reminders_text += f"🌞 Обед: {db_user.lunch_reminder_time}\n"
        else:
            reminders_text += "🌞 Обед: не настроен\n"

        if db_user.dinner_reminder_time:
            reminders_text += f"🌙 Ужин: {db_user.dinner_reminder_time}\n"
        else:
            reminders_text += "🌙 Ужин: не настроен\n"

        if db_user.snack_reminder_time:
            reminders_text += f"🍎 Перекус: {db_user.snack_reminder_time}\n"
        else:
            reminders_text += "🍎 Перекус: не настроен\n"

        reminders_text += f"\n<b>Статус:</b> {'✅ Включены' if db_user.reminders_enabled else '❌ Выключены'}\n"
        reminders_text += "\n💡 Выбери, какой прием пищи настроить:"

    keyboard = [
        [InlineKeyboardButton("🌅 Завтрак", callback_data="reminder_meal_breakfast")],
        [InlineKeyboardButton("🌞 Обед", callback_data="reminder_meal_lunch")],
        [InlineKeyboardButton("🌙 Ужин", callback_data="reminder_meal_dinner")],
        [InlineKeyboardButton("🍎 Перекус", callback_data="reminder_meal_snack")],
        [
            InlineKeyboardButton(
                "❌ Выключить все" if db_user.reminders_enabled else "✅ Включить все",
                callback_data="toggle_reminders"
            )
        ],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]

    await query.edit_message_text(
        reminders_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ReminderSetupStates.CHOOSING_MEAL


async def select_meal_for_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора приема пищи для настройки"""
    query = update.callback_query
    await query.answer()

    meal_type = query.data.replace("reminder_meal_", "")

    # Сохраняем выбранный тип приема пищи в контексте
    context.user_data["reminder_meal_type"] = meal_type

    meal_names = {
        "breakfast": "Завтрак",
        "lunch": "Обед",
        "dinner": "Ужин",
        "snack": "Перекус"
    }

    meal_emoji = {
        "breakfast": "🌅",
        "lunch": "🌞",
        "dinner": "🌙",
        "snack": "🍎"
    }

    meal_name = meal_names.get(meal_type, "Прием пищи")
    emoji = meal_emoji.get(meal_type, "🍽")

    # Предлагаем стандартные варианты времени
    standard_times = {
        "breakfast": ["07:00", "08:00", "09:00", "10:00"],
        "lunch": ["12:00", "13:00", "14:00", "15:00"],
        "dinner": ["18:00", "19:00", "20:00", "21:00"],
        "snack": ["10:00", "16:00", "17:00", "22:00"]
    }

    times = standard_times.get(meal_type, ["09:00", "13:00", "19:00"])

    keyboard = []
    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(times), 2):
        row = []
        row.append(InlineKeyboardButton(times[i], callback_data=f"set_time_{times[i]}"))
        if i + 1 < len(times):
            row.append(InlineKeyboardButton(times[i + 1], callback_data=f"set_time_{times[i + 1]}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("✍️ Ввести свое время", callback_data="custom_time")])
    keyboard.append([InlineKeyboardButton("🗑️ Удалить напоминание", callback_data="delete_reminder")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="setup_reminders")])

    await query.edit_message_text(
        f"{emoji} <b>{meal_name}</b>\n\n"
        f"Выбери время напоминания или введи свое в формате HH:MM (например, 09:30):",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ReminderSetupStates.ENTERING_TIME


async def set_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установить время напоминания"""
    query = update.callback_query
    user = update.effective_user

    if query:
        await query.answer()
        time_str = query.data.replace("set_time_", "")
    else:
        # Пользователь ввел время вручную
        time_str = update.message.text.strip()

    # Валидация формата времени
    if not _validate_time_format(time_str):
        if query:
            await query.edit_message_text(
                "❌ Неверный формат времени!\n\n"
                "Используй формат HH:MM (например, 09:30)\n"
                "Часы: 00-23, минуты: 00-59",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="setup_reminders")]
                ])
            )
        else:
            await update.message.reply_text(
                "❌ Неверный формат времени!\n\n"
                "Используй формат HH:MM (например, 09:30)\n"
                "Часы: 00-23, минуты: 00-59"
            )
        return ReminderSetupStates.ENTERING_TIME

    # Получаем тип приема пищи из контекста
    meal_type = context.user_data.get("reminder_meal_type")
    if not meal_type:
        if query:
            await query.edit_message_text(
                "❌ Ошибка: тип приема пищи не найден",
                reply_markup=back_to_menu_keyboard()
            )
        return ConversationHandler.END

    # Сохраняем время в базу данных
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return ConversationHandler.END

        # Устанавливаем время для соответствующего приема пищи
        field_map = {
            "breakfast": "breakfast_reminder_time",
            "lunch": "lunch_reminder_time",
            "dinner": "dinner_reminder_time",
            "snack": "snack_reminder_time"
        }

        field_name = field_map.get(meal_type)
        if field_name:
            setattr(db_user, field_name, time_str)
            # Автоматически включаем напоминания, если они были выключены
            if not db_user.reminders_enabled:
                db_user.reminders_enabled = True

        await session.commit()

    meal_names = {
        "breakfast": "Завтрак",
        "lunch": "Обед",
        "dinner": "Ужин",
        "snack": "Перекус"
    }

    success_text = (
        f"✅ <b>Напоминание настроено!</b>\n\n"
        f"⏰ {meal_names.get(meal_type, 'Прием пищи')}: {time_str}\n\n"
        f"Я буду напоминать тебе каждый день в это время."
    )

    keyboard = [
        [InlineKeyboardButton("🔔 Настроить другие напоминания", callback_data="setup_reminders")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]

    if query:
        await query.edit_message_text(
            success_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            success_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # Очищаем контекст
    context.user_data.pop("reminder_meal_type", None)

    return ConversationHandler.END


async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить напоминание для выбранного приема пищи"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    meal_type = context.user_data.get("reminder_meal_type")

    if not meal_type:
        await query.edit_message_text(
            "❌ Ошибка: тип приема пищи не найден",
            reply_markup=back_to_menu_keyboard()
        )
        return ConversationHandler.END

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return ConversationHandler.END

        # Удаляем время для соответствующего приема пищи
        field_map = {
            "breakfast": "breakfast_reminder_time",
            "lunch": "lunch_reminder_time",
            "dinner": "dinner_reminder_time",
            "snack": "snack_reminder_time"
        }

        field_name = field_map.get(meal_type)
        if field_name:
            setattr(db_user, field_name, None)

        await session.commit()

    meal_names = {
        "breakfast": "Завтрак",
        "lunch": "Обед",
        "dinner": "Ужин",
        "snack": "Перекус"
    }

    success_text = f"✅ Напоминание для приема пищи '{meal_names.get(meal_type)}' удалено"

    keyboard = [
        [InlineKeyboardButton("🔔 Настроить другие напоминания", callback_data="setup_reminders")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]

    await query.edit_message_text(
        success_text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    context.user_data.pop("reminder_meal_type", None)

    return ConversationHandler.END


async def toggle_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Включить/выключить все напоминания"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        if not db_user:
            return ConversationHandler.END

        # Переключаем статус
        db_user.reminders_enabled = not db_user.reminders_enabled
        new_status = db_user.reminders_enabled

        await session.commit()

    status_text = "✅ Напоминания включены" if new_status else "❌ Напоминания выключены"

    keyboard = [
        [InlineKeyboardButton("🔔 Настроить напоминания", callback_data="setup_reminders")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]

    await query.edit_message_text(
        f"{status_text}\n\n"
        f"{'Ты будешь получать напоминания по настроенному расписанию.' if new_status else 'Ты не будешь получать напоминания.'}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ConversationHandler.END


async def request_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запросить ввод произвольного времени"""
    query = update.callback_query
    await query.answer()

    meal_type = context.user_data.get("reminder_meal_type")

    meal_names = {
        "breakfast": "Завтрак",
        "lunch": "Обед",
        "dinner": "Ужин",
        "snack": "Перекус"
    }

    await query.edit_message_text(
        f"✍️ <b>Введи время для напоминания '{meal_names.get(meal_type)}'</b>\n\n"
        f"Формат: HH:MM (например, 09:30)\n"
        f"Часы: 00-23, минуты: 00-59",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data=f"reminder_meal_{meal_type}")]
        ])
    )

    return ReminderSetupStates.ENTERING_TIME


def _validate_time_format(time_str: str) -> bool:
    """Валидация формата времени HH:MM"""
    try:
        parts = time_str.split(':')
        if len(parts) != 2:
            return False

        hour = int(parts[0])
        minute = int(parts[1])

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return False

        return True
    except (ValueError, AttributeError):
        return False


async def cancel_reminder_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена настройки напоминаний"""
    query = update.callback_query
    if query:
        await query.answer()

    context.user_data.pop("reminder_meal_type", None)

    return ConversationHandler.END
