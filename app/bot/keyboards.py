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
            InlineKeyboardButton("🍽 Рацион", callback_data="meal_plan"),
            InlineKeyboardButton("🍴 Ресторан", callback_data="restaurant"),
        ],
        [
            InlineKeyboardButton("💬 AI-чат", callback_data="ai_chat"),
            InlineKeyboardButton("👤 Профиль", callback_data="profile"),
        ],
        [
            InlineKeyboardButton("📊 Отчеты", callback_data="reports"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings"),
        ],
        [
            InlineKeyboardButton("📋 Медицинские анализы", callback_data="medical_analysis"),
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


def budget_category_keyboard() -> InlineKeyboardMarkup:
    """Выбор бюджетной категории"""
    keyboard = [
        [InlineKeyboardButton("💰 Эконом", callback_data="budget_economy")],
        [InlineKeyboardButton("💵 Норм", callback_data="budget_normal")],
        [InlineKeyboardButton("💎 Премиум", callback_data="budget_premium")],
    ]
    return InlineKeyboardMarkup(keyboard)


def country_keyboard() -> InlineKeyboardMarkup:
    """Выбор страны"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Россия", callback_data="country_Россия")],
        [InlineKeyboardButton("🇰🇿 Казахстан", callback_data="country_Казахстан")],
        [InlineKeyboardButton("🇺🇦 Украина", callback_data="country_Украина")],
        [InlineKeyboardButton("🇧🇾 Беларусь", callback_data="country_Беларусь")],
        [InlineKeyboardButton("🇺🇿 Узбекистан", callback_data="country_Узбекистан")],
        [InlineKeyboardButton("🇦🇿 Азербайджан", callback_data="country_Азербайджан")],
        [InlineKeyboardButton("🇦🇲 Армения", callback_data="country_Армения")],
        [InlineKeyboardButton("🇬🇪 Грузия", callback_data="country_Грузия")],
        [InlineKeyboardButton("✍️ Другая (написать)", callback_data="country_other")],
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


def meal_recommendations_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора из рекомендованных вариантов"""
    keyboard = [
        [InlineKeyboardButton("✅ Вариант 1", callback_data="meal_rec_variant_1")],
        [InlineKeyboardButton("✅ Вариант 2", callback_data="meal_rec_variant_2")],
        [InlineKeyboardButton("✅ Вариант 3", callback_data="meal_rec_variant_3")],
        [InlineKeyboardButton("✏️ Свой вариант", callback_data="meal_rec_custom")],
        [InlineKeyboardButton("🚫 Передумал есть", callback_data="meal_rec_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def meal_choice_after_warning_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора после предупреждения о вреде"""
    keyboard = [
        [InlineKeyboardButton("💪 Всё равно съем это", callback_data="meal_choice_risky")],
        [InlineKeyboardButton("✅ Выберу альтернативу", callback_data="meal_choice_safe")],
        [InlineKeyboardButton("🚫 Передумал есть", callback_data="meal_rec_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)


def meal_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа приема пищи"""
    keyboard = [
        [InlineKeyboardButton("🌅 Завтрак", callback_data="meal_type_breakfast")],
        [InlineKeyboardButton("🌞 Обед", callback_data="meal_type_lunch")],
        [InlineKeyboardButton("🌙 Ужин", callback_data="meal_type_dinner")],
        [InlineKeyboardButton("🍎 Перекус", callback_data="meal_type_snack")],
        [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def add_meal_confirm_keyboard(meal_id: int = None) -> InlineKeyboardMarkup:
    """Подтверждение добавления еды в дневник"""
    keyboard = [
        [InlineKeyboardButton("✅ Добавить в дневник", callback_data=f"add_to_diary")],
        [InlineKeyboardButton("✏️ Изменить порцию", callback_data="edit_portion")],
        [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def diary_main_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для дневника с действиями"""
    keyboard = [
        [InlineKeyboardButton("✏️ Редактировать запись", callback_data="diary_edit_list")],
        [InlineKeyboardButton("🗑️ Удалить запись", callback_data="diary_delete_list")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def diary_meal_list_keyboard(meals: list, action: str) -> InlineKeyboardMarkup:
    """Клавиатура со списком приемов пищи для выбора действия"""
    keyboard = []

    meal_type_emoji = {
        "BREAKFAST": "🌅",
        "LUNCH": "🌞",
        "DINNER": "🌙",
        "SNACK": "🍎"
    }

    meal_type_names = {
        "BREAKFAST": "Завтрак",
        "LUNCH": "Обед",
        "DINNER": "Ужин",
        "SNACK": "Перекус"
    }

    for meal in meals:
        emoji = meal_type_emoji.get(meal.meal_type.value, "🍽")
        name = meal_type_names.get(meal.meal_type.value, "Прием пищи")
        time_str = meal.meal_time.strftime("%H:%M")

        button_text = f"{emoji} {name} ({time_str}) - {meal.total_calories} ккал"
        callback_data = f"diary_{action}_{meal.id}"

        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton("🔙 Назад к дневнику", callback_data="diary")])

    return InlineKeyboardMarkup(keyboard)


def diary_actions_keyboard(meal_id: int) -> InlineKeyboardMarkup:
    """Действия с приемом пищи в дневнике"""
    keyboard = [
        [InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_meal_{meal_id}")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Получить клавиатуру главного меню (алиас для совместимости)"""
    return main_menu_keyboard()
