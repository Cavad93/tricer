"""
Обработчики для опросов о самочувствии
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from loguru import logger

from app.db.session import async_session_maker
from app.models.user import User
from app.services.wellness_service import WellnessService

# Состояния диалога
(
    WELLNESS_ENERGY,
    WELLNESS_MOOD,
    WELLNESS_DIGESTIVE,
    WELLNESS_MENTAL_CLARITY,
    WELLNESS_HUNGER,
    WELLNESS_STRESS,
    WELLNESS_SYMPTOMS,
    WELLNESS_NOTES,
    SLEEP_HOURS,
    SLEEP_QUALITY,
) = range(10)


async def start_wellness_survey_after_meal(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Начинает опрос о самочувствии после приема пищи (вызывается через 30 минут)
    """
    query = update.callback_query

    if query:
        await query.answer()
        user_id = query.from_user.id

        # Извлекаем meal_id из callback_data
        callback_data = query.data
        if "_" in callback_data:
            parts = callback_data.split("_")
            if len(parts) >= 4:  # wellness_survey_start_{meal_id}
                try:
                    meal_id = int(parts[3])
                    context.user_data["wellness_meal_id"] = meal_id
                except (ValueError, IndexError):
                    meal_id = context.user_data.get("wellness_meal_id")
            else:
                meal_id = context.user_data.get("wellness_meal_id")
        else:
            meal_id = context.user_data.get("wellness_meal_id")
    else:
        user_id = update.effective_user.id
        meal_id = context.user_data.get("wellness_meal_id")

    # Сохраняем контекст
    context.user_data["wellness_survey_active"] = True
    context.user_data["wellness_time_after_meal"] = 30  # 30 минут прошло

    text = """
🌟 <b>Как ваше самочувствие после еды?</b>

Ответьте на несколько вопросов (займет 1-2 минуты).
Это поможет найти связь между питанием и вашим самочувствием! 📊

❓ <b>1/7: Уровень энергии</b>
Как вы себя чувствуете энергетически?
"""

    # Клавиатура с оценками 1-10
    keyboard = [
        [
            InlineKeyboardButton("1 😴", callback_data="energy_1"),
            InlineKeyboardButton("2", callback_data="energy_2"),
            InlineKeyboardButton("3", callback_data="energy_3"),
            InlineKeyboardButton("4", callback_data="energy_4"),
            InlineKeyboardButton("5", callback_data="energy_5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="energy_6"),
            InlineKeyboardButton("7", callback_data="energy_7"),
            InlineKeyboardButton("8", callback_data="energy_8"),
            InlineKeyboardButton("9", callback_data="energy_9"),
            InlineKeyboardButton("10 ⚡", callback_data="energy_10"),
        ],
        [InlineKeyboardButton("⏭️ Пропустить опрос", callback_data="wellness_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

    return WELLNESS_ENERGY


async def handle_energy_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка уровня энергии"""
    query = update.callback_query
    await query.answer()

    # Сохраняем ответ
    energy_level = int(query.data.split("_")[1])
    context.user_data["wellness_energy_level"] = energy_level

    text = """
❓ <b>2/7: Настроение</b>
Как ваше настроение?
"""

    keyboard = [
        [
            InlineKeyboardButton("1 😢", callback_data="mood_1"),
            InlineKeyboardButton("2", callback_data="mood_2"),
            InlineKeyboardButton("3", callback_data="mood_3"),
            InlineKeyboardButton("4", callback_data="mood_4"),
            InlineKeyboardButton("5", callback_data="mood_5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="mood_6"),
            InlineKeyboardButton("7", callback_data="mood_7"),
            InlineKeyboardButton("8", callback_data="mood_8"),
            InlineKeyboardButton("9", callback_data="mood_9"),
            InlineKeyboardButton("10 😄", callback_data="mood_10"),
        ],
        [InlineKeyboardButton("⏭️ Пропустить опрос", callback_data="wellness_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return WELLNESS_MOOD


async def handle_mood(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка настроения"""
    query = update.callback_query
    await query.answer()

    mood = int(query.data.split("_")[1])
    context.user_data["wellness_mood"] = mood

    text = """
❓ <b>3/7: Пищеварение</b>
Как ваше пищеварение? Есть ли дискомфорт?
"""

    keyboard = [
        [
            InlineKeyboardButton("1 🤢", callback_data="digestive_1"),
            InlineKeyboardButton("2", callback_data="digestive_2"),
            InlineKeyboardButton("3", callback_data="digestive_3"),
            InlineKeyboardButton("4", callback_data="digestive_4"),
            InlineKeyboardButton("5", callback_data="digestive_5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="digestive_6"),
            InlineKeyboardButton("7", callback_data="digestive_7"),
            InlineKeyboardButton("8", callback_data="digestive_8"),
            InlineKeyboardButton("9", callback_data="digestive_9"),
            InlineKeyboardButton("10 ✅", callback_data="digestive_10"),
        ],
        [InlineKeyboardButton("⏭️ Пропустить опрос", callback_data="wellness_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return WELLNESS_DIGESTIVE


async def handle_digestive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка пищеварения"""
    query = update.callback_query
    await query.answer()

    digestive = int(query.data.split("_")[1])
    context.user_data["wellness_digestive_comfort"] = digestive

    text = """
❓ <b>4/7: Ясность ума</b>
Насколько ясно мыслите? Можете ли сконцентрироваться?
"""

    keyboard = [
        [
            InlineKeyboardButton("1 🌫️", callback_data="mental_1"),
            InlineKeyboardButton("2", callback_data="mental_2"),
            InlineKeyboardButton("3", callback_data="mental_3"),
            InlineKeyboardButton("4", callback_data="mental_4"),
            InlineKeyboardButton("5", callback_data="mental_5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="mental_6"),
            InlineKeyboardButton("7", callback_data="mental_7"),
            InlineKeyboardButton("8", callback_data="mental_8"),
            InlineKeyboardButton("9", callback_data="mental_9"),
            InlineKeyboardButton("10 🧠", callback_data="mental_10"),
        ],
        [InlineKeyboardButton("⏭️ Пропустить опрос", callback_data="wellness_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return WELLNESS_MENTAL_CLARITY


async def handle_mental_clarity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ясности ума"""
    query = update.callback_query
    await query.answer()

    mental_clarity = int(query.data.split("_")[1])
    context.user_data["wellness_mental_clarity"] = mental_clarity

    text = """
❓ <b>5/7: Голод</b>
Как ваш уровень голода/сытости?
(1 = очень голоден, 10 = переел)
"""

    keyboard = [
        [
            InlineKeyboardButton("1 🍽️", callback_data="hunger_1"),
            InlineKeyboardButton("2", callback_data="hunger_2"),
            InlineKeyboardButton("3", callback_data="hunger_3"),
            InlineKeyboardButton("4", callback_data="hunger_4"),
            InlineKeyboardButton("5", callback_data="hunger_5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="hunger_6"),
            InlineKeyboardButton("7", callback_data="hunger_7"),
            InlineKeyboardButton("8", callback_data="hunger_8"),
            InlineKeyboardButton("9", callback_data="hunger_9"),
            InlineKeyboardButton("10 🤰", callback_data="hunger_10"),
        ],
        [InlineKeyboardButton("⏭️ Пропустить опрос", callback_data="wellness_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return WELLNESS_HUNGER


async def handle_hunger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка голода"""
    query = update.callback_query
    await query.answer()

    hunger = int(query.data.split("_")[1])
    context.user_data["wellness_hunger_level"] = hunger

    text = """
❓ <b>6/7: Стресс</b>
Каков ваш уровень стресса?
"""

    keyboard = [
        [
            InlineKeyboardButton("1 😌", callback_data="stress_1"),
            InlineKeyboardButton("2", callback_data="stress_2"),
            InlineKeyboardButton("3", callback_data="stress_3"),
            InlineKeyboardButton("4", callback_data="stress_4"),
            InlineKeyboardButton("5", callback_data="stress_5"),
        ],
        [
            InlineKeyboardButton("6", callback_data="stress_6"),
            InlineKeyboardButton("7", callback_data="stress_7"),
            InlineKeyboardButton("8", callback_data="stress_8"),
            InlineKeyboardButton("9", callback_data="stress_9"),
            InlineKeyboardButton("10 😰", callback_data="stress_10"),
        ],
        [InlineKeyboardButton("⏭️ Пропустить опрос", callback_data="wellness_skip")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return WELLNESS_STRESS


async def handle_stress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка стресса"""
    query = update.callback_query
    await query.answer()

    stress = int(query.data.split("_")[1])
    context.user_data["wellness_stress_level"] = stress

    text = """
❓ <b>7/7: Симптомы</b>
Есть ли какие-то физические симптомы?

Выберите все, что применимо:
"""

    keyboard = [
        [
            InlineKeyboardButton("Вздутие", callback_data="symptom_bloating"),
            InlineKeyboardButton("Усталость", callback_data="symptom_fatigue"),
        ],
        [
            InlineKeyboardButton("Головная боль", callback_data="symptom_headache"),
            InlineKeyboardButton("Тяжесть", callback_data="symptom_heaviness"),
        ],
        [
            InlineKeyboardButton("Изжога", callback_data="symptom_heartburn"),
            InlineKeyboardButton("Тошнота", callback_data="symptom_nausea"),
        ],
        [
            InlineKeyboardButton("✅ Нет симптомов", callback_data="symptom_none"),
        ],
        [
            InlineKeyboardButton("➡️ Продолжить", callback_data="symptoms_done"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Инициализируем список симптомов если его нет
    if "wellness_symptoms" not in context.user_data:
        context.user_data["wellness_symptoms"] = []

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return WELLNESS_SYMPTOMS


async def handle_symptoms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка симптомов"""
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "symptoms_done":
        # Переходим к заметкам
        text = """
📝 <b>Дополнительные заметки</b>

Хотите что-то добавить? (необязательно)

Напишите или нажмите "Пропустить":
"""

        keyboard = [
            [InlineKeyboardButton("⏭️ Пропустить", callback_data="notes_skip")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
        return WELLNESS_NOTES

    elif action == "symptom_none":
        context.user_data["wellness_symptoms"] = []
    else:
        # Добавляем/удаляем симптом
        symptom_map = {
            "symptom_bloating": "вздутие",
            "symptom_fatigue": "усталость",
            "symptom_headache": "головная боль",
            "symptom_heaviness": "тяжесть в желудке",
            "symptom_heartburn": "изжога",
            "symptom_nausea": "тошнота"
        }

        symptom = symptom_map.get(action)
        if symptom:
            symptoms = context.user_data.get("wellness_symptoms", [])
            if symptom in symptoms:
                symptoms.remove(symptom)
            else:
                symptoms.append(symptom)
            context.user_data["wellness_symptoms"] = symptoms

    # Обновляем сообщение с выбранными симптомами
    selected = context.user_data.get("wellness_symptoms", [])
    symptom_text = ", ".join(selected) if selected else "нет"

    text = f"""
❓ <b>7/7: Симптомы</b>
Есть ли какие-то физические симптомы?

<b>Выбрано:</b> {symptom_text}

Выберите все, что применимо:
"""

    keyboard = [
        [
            InlineKeyboardButton("Вздутие", callback_data="symptom_bloating"),
            InlineKeyboardButton("Усталость", callback_data="symptom_fatigue"),
        ],
        [
            InlineKeyboardButton("Головная боль", callback_data="symptom_headache"),
            InlineKeyboardButton("Тяжесть", callback_data="symptom_heaviness"),
        ],
        [
            InlineKeyboardButton("Изжога", callback_data="symptom_heartburn"),
            InlineKeyboardButton("Тошнота", callback_data="symptom_nausea"),
        ],
        [
            InlineKeyboardButton("✅ Нет симптомов", callback_data="symptom_none"),
        ],
        [
            InlineKeyboardButton("➡️ Продолжить", callback_data="symptoms_done"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    return WELLNESS_SYMPTOMS


async def handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка заметок"""
    if update.callback_query:
        # Пропуск заметок
        query = update.callback_query
        await query.answer()
        notes = None
        message_to_edit = query.message
    else:
        # Текстовые заметки
        notes = update.message.text
        message_to_edit = None

    context.user_data["wellness_notes"] = notes

    # Сохраняем запись в БД
    async with async_session_maker() as session:
        try:
            # Получаем user_id из БД
            from sqlalchemy import select
            user_result = await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                await update.effective_message.reply_text("Ошибка: пользователь не найден")
                return ConversationHandler.END

            # Создаем запись о самочувствии
            wellness_service = WellnessService()
            await wellness_service.create_wellness_log(
                session=session,
                user_id=user.id,
                meal_id=context.user_data.get("wellness_meal_id"),
                energy_level=context.user_data.get("wellness_energy_level"),
                mood=context.user_data.get("wellness_mood"),
                digestive_comfort=context.user_data.get("wellness_digestive_comfort"),
                mental_clarity=context.user_data.get("wellness_mental_clarity"),
                hunger_level=context.user_data.get("wellness_hunger_level"),
                stress_level=context.user_data.get("wellness_stress_level"),
                physical_symptoms=context.user_data.get("wellness_symptoms", []),
                notes=notes,
                time_after_meal_minutes=context.user_data.get("wellness_time_after_meal", 30)
            )

            success_text = """
✅ <b>Спасибо за ответы!</b>

Ваши данные сохранены.
Я буду анализировать связь между вашим питанием и самочувствием.

💡 Через несколько дней вы сможете получить персональные инсайты командой /wellness_insights
"""

            if message_to_edit:
                await message_to_edit.edit_text(success_text, parse_mode="HTML")
            else:
                await update.message.reply_text(success_text, parse_mode="HTML")

        except Exception as e:
            logger.error(f"Error saving wellness log: {e}")
            error_text = "Произошла ошибка при сохранении данных. Попробуйте позже."
            if message_to_edit:
                await message_to_edit.edit_text(error_text)
            else:
                await update.message.reply_text(error_text)

    # Очищаем контекст
    context.user_data["wellness_survey_active"] = False
    for key in list(context.user_data.keys()):
        if key.startswith("wellness_"):
            del context.user_data[key]

    return ConversationHandler.END


async def skip_wellness_survey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск опроса"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Опрос пропущен. Вы можете заполнить его позже командой /wellness",
        parse_mode="HTML"
    )

    # Очищаем контекст
    context.user_data["wellness_survey_active"] = False
    for key in list(context.user_data.keys()):
        if key.startswith("wellness_"):
            del context.user_data[key]

    return ConversationHandler.END


async def cancel_wellness(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена опроса"""
    await update.message.reply_text("Опрос отменен.")

    context.user_data["wellness_survey_active"] = False
    for key in list(context.user_data.keys()):
        if key.startswith("wellness_"):
            del context.user_data[key]

    return ConversationHandler.END


# ConversationHandler для опроса о самочувствии
wellness_survey_conversation = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_wellness_survey_after_meal, pattern="^wellness_survey_start")
    ],
    states={
        WELLNESS_ENERGY: [
            CallbackQueryHandler(handle_energy_level, pattern="^energy_"),
            CallbackQueryHandler(skip_wellness_survey, pattern="^wellness_skip$")
        ],
        WELLNESS_MOOD: [
            CallbackQueryHandler(handle_mood, pattern="^mood_"),
            CallbackQueryHandler(skip_wellness_survey, pattern="^wellness_skip$")
        ],
        WELLNESS_DIGESTIVE: [
            CallbackQueryHandler(handle_digestive, pattern="^digestive_"),
            CallbackQueryHandler(skip_wellness_survey, pattern="^wellness_skip$")
        ],
        WELLNESS_MENTAL_CLARITY: [
            CallbackQueryHandler(handle_mental_clarity, pattern="^mental_"),
            CallbackQueryHandler(skip_wellness_survey, pattern="^wellness_skip$")
        ],
        WELLNESS_HUNGER: [
            CallbackQueryHandler(handle_hunger, pattern="^hunger_"),
            CallbackQueryHandler(skip_wellness_survey, pattern="^wellness_skip$")
        ],
        WELLNESS_STRESS: [
            CallbackQueryHandler(handle_stress, pattern="^stress_"),
            CallbackQueryHandler(skip_wellness_survey, pattern="^wellness_skip$")
        ],
        WELLNESS_SYMPTOMS: [
            CallbackQueryHandler(handle_symptoms, pattern="^symptom_"),
            CallbackQueryHandler(handle_symptoms, pattern="^symptoms_done$"),
            CallbackQueryHandler(skip_wellness_survey, pattern="^wellness_skip$")
        ],
        WELLNESS_NOTES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_notes),
            CallbackQueryHandler(handle_notes, pattern="^notes_skip$")
        ],
    },
    fallbacks=[
        CommandHandler("cancel", cancel_wellness)
    ],
    name="wellness_survey",
    persistent=False
)
