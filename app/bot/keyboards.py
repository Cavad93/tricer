"""
Клавиатуры для Telegram бота
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню"""
    keyboard = [
        [
            InlineKeyboardButton("📸 Добавить еду", callback_data="add_food"),
            InlineKeyboardButton("📊 Дневник", callback_data="diary"),
        ],
        [
            InlineKeyboardButton("💬 AI-чат", callback_data="ai_chat"),
            InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("📈 Статистика", callback_data="stats"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def gender_keyboard() -> InlineKeyboardMarkup:
    """Выбор пола"""
    keyboard = [
        [
            InlineKeyboardButton("👨 Мужской", callback_data="gender_male"),
            InlineKeyboardButton("👩 Женский", callback_data="gender_female"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def goal_keyboard() -> InlineKeyboardMarkup:
    """Выбор цели"""
    keyboard = [
        [InlineKeyboardButton("📉 Похудение", callback_data="goal_weight_loss")],
        [InlineKeyboardButton("📈 Набор массы", callback_data="goal_weight_gain")],
        [InlineKeyboardButton("➡️ Поддержание веса", callback_data="goal_maintenance")],
        [InlineKeyboardButton("💚 Здоровое питание", callback_data="goal_health")],
    ]
    return InlineKeyboardMarkup(keyboard)


def activity_level_keyboard() -> InlineKeyboardMarkup:
    """Выбор уровня активности"""
    keyboard = [
        [InlineKeyboardButton("😴 Минимальная (сидячий образ жизни)", callback_data="activity_minimal")],
        [InlineKeyboardButton("🚶 Низкая (1-3 тренировки/неделя)", callback_data="activity_low")],
        [InlineKeyboardButton("🏃 Средняя (3-5 тренировок/неделя)", callback_data="activity_medium")],
        [InlineKeyboardButton("💪 Высокая (5-7 тренировок/неделя)", callback_data="activity_high")],
        [InlineKeyboardButton("🔥 Очень высокая (2+ тренировки/день)", callback_data="activity_very_high")],
    ]
    return InlineKeyboardMarkup(keyboard)


def diet_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа диеты"""
    keyboard = [
        [InlineKeyboardButton("🍖 Всеядный", callback_data="diet_omnivore")],
        [InlineKeyboardButton("🥗 Вегетарианец", callback_data="diet_vegetarian")],
        [InlineKeyboardButton("🌱 Веган", callback_data="diet_vegan")],
        [InlineKeyboardButton("🐟 Пескетарианец (рыба)", callback_data="diet_pescatarian")],
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{action}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"cancel_{action}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def skip_keyboard(step: str) -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой пропустить"""
    keyboard = [
        [InlineKeyboardButton("⏭️ Пропустить", callback_data=f"skip_{step}")]
    ]
    return InlineKeyboardMarkup(keyboard)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    keyboard = [
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)
