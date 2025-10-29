"""
Обработчики команды /start и онбординга
"""
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from datetime import datetime

from app.bot.keyboards import (
    gender_keyboard,
    goal_keyboard,
    activity_level_keyboard,
    diet_type_keyboard,
    budget_category_keyboard,
    country_keyboard,
    skip_keyboard,
    main_menu_keyboard,
)
from app.bot.states import OnboardingStates
from app.bot.handlers.disclaimer import disclaimer_accept_callback, disclaimer_decline_callback
from app.models.user import Gender, Goal, ActivityLevel, DietType, BudgetCategory
from app.services.nutrition_calc import NutritionCalculator
from loguru import logger


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start"""
    user = update.effective_user

    logger.info(f"User {user.id} started the bot")

    # Проверяем, зарегистрирован ли пользователь в БД
    from app.db.session import async_session_maker
    from app.models.user import User
    from sqlalchemy import select

    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == user.id)
        )
        db_user = result.scalar_one_or_none()

        # Если пользователь уже прошел онбординг - показываем главное меню
        if db_user and db_user.onboarding_completed:
            logger.info(f"User {user.id} is already registered, showing main menu")

            # Обновляем время последней активности
            db_user.last_active_at = datetime.utcnow()
            await session.commit()

            await update.message.reply_text(
                f"👋 С возвращением, {db_user.preferred_name or db_user.first_name}!\n\n"
                f"Рад тебя снова видеть! 😊",
                reply_markup=main_menu_keyboard()
            )
            return ConversationHandler.END

    # Новый пользователь - показываем приветствие и дисклеймер
    await update.message.reply_text(
        f"👋 Привет!\n\n"
        "Я NutriAI - твой персональный AI-нутрициолог!\n\n"
        "Я помогу тебе:\n"
        "✅ Отслеживать питание (просто отправь фото еды)\n"
        "✅ Считать калории и БЖУ автоматически\n"
        "✅ Достигать твоих целей по весу и здоровью\n"
        "✅ Получать персональные рекомендации от AI\n\n"
        "Перед началом важно прочитать условия использования..."
    )

    # Показываем дисклеймер
    from app.bot.texts import MEDICAL_DISCLAIMER
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [InlineKeyboardButton("✅ Согласен", callback_data="disclaimer_accept")],
        [InlineKeyboardButton("❌ Не согласен", callback_data="disclaimer_decline")]
    ]

    await update.message.reply_text(
        MEDICAL_DISCLAIMER,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

    return OnboardingStates.DISCLAIMER


async def preferred_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода имени пользователя"""
    preferred_name = update.message.text.strip()

    if len(preferred_name) < 1 or len(preferred_name) > 50:
        await update.message.reply_text(
            "❌ Имя должно быть от 1 до 50 символов. Попробуй ещё раз:"
        )
        return OnboardingStates.PREFERRED_NAME

    context.user_data["preferred_name"] = preferred_name

    await update.message.reply_text(
        f"Приятно познакомиться, {preferred_name}! 😊\n\n"
        "Где ты живёшь? Выбери свою страну:\n\n"
        "Это нужно для точного подбора цен на продукты в твоём регионе.",
        reply_markup=country_keyboard()
    )

    return OnboardingStates.COUNTRY


async def country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора страны"""
    query = update.callback_query
    await query.answer()

    if query.data == "country_other":
        # Пользователь хочет ввести другую страну
        await query.edit_message_text(
            "Напиши название своей страны:"
        )
        return OnboardingStates.COUNTRY

    # Извлекаем название страны из callback_data
    country = query.data.replace("country_", "")
    context.user_data["country"] = country

    await query.edit_message_text(
        f"✅ Страна: {country}\n\n"
        "Теперь напиши свой город:"
    )

    return OnboardingStates.CITY


async def country_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка текстового ввода страны (если выбрал 'Другая')"""
    country = update.message.text.strip()

    if len(country) < 2 or len(country) > 100:
        await update.message.reply_text(
            "❌ Пожалуйста, введи корректное название страны:"
        )
        return OnboardingStates.COUNTRY

    context.user_data["country"] = country

    await update.message.reply_text(
        f"✅ Страна: {country}\n\n"
        "Теперь напиши свой город:"
    )

    return OnboardingStates.CITY


async def city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода города"""
    city = update.message.text.strip()

    if len(city) < 2 or len(city) > 100:
        await update.message.reply_text(
            "❌ Пожалуйста, введи корректное название города:"
        )
        return OnboardingStates.CITY

    context.user_data["city"] = city

    await update.message.reply_text(
        f"✅ Город: {city}\n\n"
        "Отлично! Теперь выбери свой пол:",
        reply_markup=gender_keyboard()
    )

    return OnboardingStates.GENDER


async def gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора пола"""
    query = update.callback_query
    await query.answer()

    gender_map = {
        "gender_male": Gender.MALE,
        "gender_female": Gender.FEMALE,
    }

    gender = gender_map.get(query.data)
    context.user_data["gender"] = gender

    gender_text = "мужской" if gender == Gender.MALE else "женский"

    await query.edit_message_text(
        f"✅ Пол: {gender_text}\n\n"
        "Теперь введи свой год рождения (например, 1990):"
    )

    return OnboardingStates.BIRTH_YEAR


async def birth_year_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода года рождения"""
    try:
        birth_year = int(update.message.text)
        current_year = datetime.now().year

        if birth_year < 1900 or birth_year > current_year:
            await update.message.reply_text(
                "❌ Пожалуйста, введи корректный год рождения (например, 1990):"
            )
            return OnboardingStates.BIRTH_YEAR

        age = current_year - birth_year

        if age < 16:
            await update.message.reply_text(
                "❌ Извини, бот предназначен для пользователей от 16 лет."
            )
            return ConversationHandler.END

        context.user_data["birth_year"] = birth_year
        context.user_data["age"] = age

        await update.message.reply_text(
            f"✅ Возраст: {age} лет\n\n"
            "Какой у тебя рост? (в сантиметрах, например, 175):"
        )

        return OnboardingStates.HEIGHT

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введи год рождения числом (например, 1990):"
        )
        return OnboardingStates.BIRTH_YEAR


async def height_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода роста"""
    try:
        height = int(update.message.text)

        if height < 100 or height > 250:
            await update.message.reply_text(
                "❌ Пожалуйста, введи корректный рост в см (например, 175):"
            )
            return OnboardingStates.HEIGHT

        context.user_data["height"] = height

        await update.message.reply_text(
            f"✅ Рост: {height} см\n\n"
            "Какой у тебя текущий вес? (в килограммах, например, 70):"
        )

        return OnboardingStates.CURRENT_WEIGHT

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введи рост числом в см (например, 175):"
        )
        return OnboardingStates.HEIGHT


async def current_weight_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода текущего веса"""
    try:
        weight = float(update.message.text.replace(",", "."))

        if weight < 30 or weight > 300:
            await update.message.reply_text(
                "❌ Пожалуйста, введи корректный вес в кг (например, 70):"
            )
            return OnboardingStates.CURRENT_WEIGHT

        context.user_data["current_weight"] = weight

        await update.message.reply_text(
            f"✅ Текущий вес: {weight} кг\n\n"
            "Какой вес ты хочешь достичь? (в кг, например, 65):"
        )

        return OnboardingStates.TARGET_WEIGHT

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введи вес числом в кг (например, 70):"
        )
        return OnboardingStates.CURRENT_WEIGHT


async def target_weight_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода целевого веса"""
    try:
        target_weight = float(update.message.text.replace(",", "."))

        if target_weight < 30 or target_weight > 300:
            await update.message.reply_text(
                "❌ Пожалуйста, введи корректный целевой вес в кг (например, 65):"
            )
            return OnboardingStates.TARGET_WEIGHT

        context.user_data["target_weight"] = target_weight

        await update.message.reply_text(
            f"✅ Целевой вес: {target_weight} кг\n\n"
            "Какая у тебя главная цель?",
            reply_markup=goal_keyboard()
        )

        return OnboardingStates.GOAL

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введи целевой вес числом в кг (например, 65):"
        )
        return OnboardingStates.TARGET_WEIGHT


async def goal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора цели"""
    query = update.callback_query
    await query.answer()

    goal_map = {
        "goal_weight_loss": Goal.WEIGHT_LOSS,
        "goal_weight_gain": Goal.WEIGHT_GAIN,
        "goal_maintenance": Goal.MAINTENANCE,
        "goal_health": Goal.HEALTH,
    }

    goal = goal_map.get(query.data)
    context.user_data["goal"] = goal

    goal_text = {
        Goal.WEIGHT_LOSS: "Похудение",
        Goal.WEIGHT_GAIN: "Набор массы",
        Goal.MAINTENANCE: "Поддержание веса",
        Goal.HEALTH: "Здоровое питание",
    }[goal]

    await query.edit_message_text(
        f"✅ Цель: {goal_text}\n\n"
        "Какой у тебя уровень физической активности?",
        reply_markup=activity_level_keyboard()
    )

    return OnboardingStates.ACTIVITY_LEVEL


async def activity_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора уровня активности"""
    query = update.callback_query
    await query.answer()

    activity_map = {
        "activity_minimal": ActivityLevel.MINIMAL,
        "activity_low": ActivityLevel.LOW,
        "activity_medium": ActivityLevel.MEDIUM,
        "activity_high": ActivityLevel.HIGH,
        "activity_very_high": ActivityLevel.VERY_HIGH,
    }

    activity = activity_map.get(query.data)
    context.user_data["activity_level"] = activity

    await query.edit_message_text(
        "✅ Уровень активности сохранен\n\n"
        "Какой тип питания ты предпочитаешь?",
        reply_markup=diet_type_keyboard()
    )

    return OnboardingStates.DIET_TYPE


async def diet_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора типа диеты"""
    query = update.callback_query
    await query.answer()

    diet_map = {
        "diet_omnivore": DietType.OMNIVORE,
        "diet_vegetarian": DietType.VEGETARIAN,
        "diet_vegan": DietType.VEGAN,
        "diet_pescatarian": DietType.PESCATARIAN,
    }

    diet = diet_map.get(query.data)
    context.user_data["diet_type"] = diet

    await query.edit_message_text(
        "✅ Тип питания сохранен\n\n"
        "Какой у тебя бюджет на питание?\n\n"
        "Это поможет мне составлять планы питания с учетом твоих финансовых возможностей:",
        reply_markup=budget_category_keyboard()
    )

    return OnboardingStates.BUDGET_CATEGORY


async def budget_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора бюджетной категории"""
    query = update.callback_query
    await query.answer()

    budget_map = {
        "budget_economy": BudgetCategory.ECONOMY,
        "budget_normal": BudgetCategory.NORMAL,
        "budget_premium": BudgetCategory.PREMIUM,
    }

    budget = budget_map.get(query.data)
    context.user_data["budget_category"] = budget

    budget_text = {
        BudgetCategory.ECONOMY: "Эконом",
        BudgetCategory.NORMAL: "Норм",
        BudgetCategory.PREMIUM: "Премиум",
    }[budget]

    await query.edit_message_text(
        f"✅ Бюджет: {budget_text}\n\n"
        "Есть ли у тебя аллергии или продукты, которые ты не ешь?\n\n"
        "Напиши их через запятую или нажми 'Пропустить':",
        reply_markup=skip_keyboard("allergies")
    )

    return OnboardingStates.ALLERGIES


async def allergies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода аллергий"""
    if update.message:
        allergies_text = update.message.text.strip()
        allergies = [a.strip() for a in allergies_text.split(",") if a.strip()]
        context.user_data["allergies"] = allergies
    else:
        context.user_data["allergies"] = []

    # Переходим к медицинским вопросам (Этап 4)
    await update.message.reply_text(
        "🏥 Теперь несколько вопросов о твоём здоровье.\n\n"
        "Есть ли у тебя хронические заболевания, которые я должен учитывать при составлении рациона?\n"
        "(Например: диабет, гипертония, заболевания ЖКТ и т.д.)\n\n"
        "Напиши их через запятую или нажми 'Пропустить' если нет:",
        reply_markup=skip_keyboard("chronic_conditions")
    )

    return OnboardingStates.CHRONIC_CONDITIONS


async def skip_allergies_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск ввода аллергий"""
    query = update.callback_query
    await query.answer()

    context.user_data["allergies"] = []

    # Переходим к медицинским вопросам (Этап 4)
    await query.edit_message_text(
        "🏥 Теперь несколько вопросов о твоём здоровье.\n\n"
        "Есть ли у тебя хронические заболевания, которые я должен учитывать при составлении рациона?\n"
        "(Например: диабет, гипертония, заболевания ЖКТ и т.д.)\n\n"
        "Напиши их через запятую или нажми 'Пропустить' если нет:",
        reply_markup=skip_keyboard("chronic_conditions")
    )

    return OnboardingStates.CHRONIC_CONDITIONS


async def chronic_conditions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода хронических заболеваний"""
    if update.message:
        conditions_text = update.message.text.strip()
        conditions = [c.strip() for c in conditions_text.split(",") if c.strip()]
        context.user_data["chronic_conditions"] = conditions
    else:
        context.user_data["chronic_conditions"] = []

    # Переходим к вопросу об удаленных органах
    await update.message.reply_text(
        "Были ли удалены какие-то органы?\n"
        "(Например: желчный пузырь, аппендикс и т.д.)\n\n"
        "Напиши их через запятую или нажми 'Пропустить' если нет:",
        reply_markup=skip_keyboard("removed_organs")
    )

    return OnboardingStates.REMOVED_ORGANS


async def skip_chronic_conditions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск ввода хронических заболеваний"""
    query = update.callback_query
    await query.answer()

    context.user_data["chronic_conditions"] = []

    # Переходим к вопросу об удаленных органах
    await query.edit_message_text(
        "Были ли удалены какие-то органы?\n"
        "(Например: желчный пузырь, аппендикс и т.д.)\n\n"
        "Напиши их через запятую или нажми 'Пропустить' если нет:",
        reply_markup=skip_keyboard("removed_organs")
    )

    return OnboardingStates.REMOVED_ORGANS


async def removed_organs_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ввода удаленных органов"""
    if update.message:
        organs_text = update.message.text.strip()
        organs = [o.strip() for o in organs_text.split(",") if o.strip()]
        context.user_data["removed_organs"] = organs
    else:
        context.user_data["removed_organs"] = []

    # Теперь рассчитываем целевые показатели и сохраняем профиль
    await calculate_and_save_profile(update, context)

    return ConversationHandler.END


async def skip_removed_organs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск ввода удаленных органов"""
    query = update.callback_query
    await query.answer()

    context.user_data["removed_organs"] = []

    await query.edit_message_text("⏭️ Пропускаем...")

    # Теперь рассчитываем целевые показатели и сохраняем профиль
    await calculate_and_save_profile(update, context)

    return ConversationHandler.END


async def calculate_and_save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Расчет целевых показателей и сохранение профиля"""
    user_data = context.user_data

    # Отправляем сообщение о расчете
    if update.callback_query:
        message = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⏳ Рассчитываю твои персональные показатели..."
        )
    else:
        message = await update.message.reply_text(
            "⏳ Рассчитываю твои персональные показатели..."
        )

    # Рассчитываем целевые показатели
    nutrition_targets = NutritionCalculator.calculate_nutrition_targets(
        gender=user_data["gender"],
        weight=user_data["current_weight"],
        height=user_data["height"],
        age=user_data["age"],
        activity_level=user_data["activity_level"],
        goal=user_data["goal"],
    )

    user_data["target_calories"] = nutrition_targets.calories
    user_data["target_proteins"] = nutrition_targets.proteins
    user_data["target_fats"] = nutrition_targets.fats
    user_data["target_carbs"] = nutrition_targets.carbs

    # Сохраняем пользователя в БД
    from app.db.session import async_session_maker
    from app.models.user import User
    from sqlalchemy import select
    from datetime import datetime

    async with async_session_maker() as session:
        try:
            # Проверяем, существует ли пользователь
            result = await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            user = result.scalar_one_or_none()

            if user:
                # Обновляем существующего пользователя
                user.username = update.effective_user.username
                user.first_name = update.effective_user.first_name
                user.last_name = update.effective_user.last_name
                user.language_code = update.effective_user.language_code
                user.preferred_name = user_data.get("preferred_name")
                user.country = user_data.get("country")
                user.city = user_data.get("city")
                user.gender = user_data["gender"]
                user.birth_year = user_data["birth_year"]
                user.height = user_data["height"]
                user.current_weight = user_data["current_weight"]
                user.target_weight = user_data["target_weight"]
                user.goal = user_data["goal"]
                user.activity_level = user_data["activity_level"]
                user.target_calories = nutrition_targets.calories
                user.target_proteins = nutrition_targets.proteins
                user.target_fats = nutrition_targets.fats
                user.target_carbs = nutrition_targets.carbs
                user.diet_type = user_data["diet_type"]
                user.budget_category = user_data.get("budget_category", BudgetCategory.NORMAL)
                user.allergies = user_data.get("allergies", [])
                # Медицинская информация (Этап 4)
                user.chronic_conditions = user_data.get("chronic_conditions", [])
                user.removed_organs = user_data.get("removed_organs", [])
                user.onboarding_completed = True
                user.updated_at = datetime.utcnow()
                user.last_active_at = datetime.utcnow()
            else:
                # Создаём нового пользователя
                user = User(
                    telegram_id=update.effective_user.id,
                    username=update.effective_user.username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name,
                    language_code=update.effective_user.language_code,
                    preferred_name=user_data.get("preferred_name"),
                    country=user_data.get("country"),
                    city=user_data.get("city"),
                    gender=user_data["gender"],
                    birth_year=user_data["birth_year"],
                    height=user_data["height"],
                    current_weight=user_data["current_weight"],
                    target_weight=user_data["target_weight"],
                    goal=user_data["goal"],
                    activity_level=user_data["activity_level"],
                    target_calories=nutrition_targets.calories,
                    target_proteins=nutrition_targets.proteins,
                    target_fats=nutrition_targets.fats,
                    target_carbs=nutrition_targets.carbs,
                    diet_type=user_data["diet_type"],
                    budget_category=user_data.get("budget_category", BudgetCategory.NORMAL),
                    allergies=user_data.get("allergies", []),
                    # Медицинская информация (Этап 4)
                    chronic_conditions=user_data.get("chronic_conditions", []),
                    removed_organs=user_data.get("removed_organs", []),
                    onboarding_completed=True,
                )
                session.add(user)

            await session.commit()
            await session.refresh(user)
            logger.info(f"User {update.effective_user.id} profile saved to database")

            # Генерируем медицинские ограничения на основе введенных данных (Этап 4)
            if user.chronic_conditions or user.removed_organs:
                try:
                    from app.services.medical_analysis_service import MedicalAnalysisService
                    logger.info(f"Generating medical restrictions for user {user.id}")
                    await MedicalAnalysisService.generate_medical_restrictions(user, session)
                    logger.info(f"Medical restrictions generated for user {user.id}")
                except Exception as e:
                    logger.error(f"Error generating medical restrictions: {e}")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error saving user profile: {e}")
            raise

    # Показываем результаты
    preferred_name = user_data.get("preferred_name", "")
    greeting = f"✅ Отлично, {preferred_name}! Твой профиль настроен!\n\n" if preferred_name else "✅ Отлично! Твой профиль настроен!\n\n"

    await message.edit_text(
        greeting +
        f"📊 Твои целевые показатели на день:\n"
        f"🔥 Калории: {nutrition_targets.calories} ккал\n"
        f"🥩 Белки: {nutrition_targets.proteins}г\n"
        f"🧈 Жиры: {nutrition_targets.fats}г\n"
        f"🍞 Углеводы: {nutrition_targets.carbs}г\n\n"
        "Теперь ты можешь начать отслеживать своё питание!"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"{preferred_name}, что хочешь сделать?" if preferred_name else "Что хочешь сделать?",
        reply_markup=main_menu_keyboard()
    )

    logger.info(f"User {update.effective_user.id} completed onboarding")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена онбординга"""
    await update.message.reply_text(
        "❌ Настройка профиля отменена.\n"
        "Используй /start чтобы начать заново."
    )
    return ConversationHandler.END


# ConversationHandler для онбординга
onboarding_conversation = ConversationHandler(
    entry_points=[CommandHandler("start", start_command)],
    states={
        OnboardingStates.DISCLAIMER: [
            CallbackQueryHandler(disclaimer_accept_callback, pattern="^disclaimer_accept$"),
            CallbackQueryHandler(disclaimer_decline_callback, pattern="^disclaimer_decline$")
        ],
        OnboardingStates.PREFERRED_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, preferred_name_handler)
        ],
        OnboardingStates.COUNTRY: [
            CallbackQueryHandler(country_callback, pattern="^country_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, country_text_handler)
        ],
        OnboardingStates.CITY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, city_handler)
        ],
        OnboardingStates.GENDER: [
            CallbackQueryHandler(gender_callback, pattern="^gender_")
        ],
        OnboardingStates.BIRTH_YEAR: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, birth_year_handler)
        ],
        OnboardingStates.HEIGHT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, height_handler)
        ],
        OnboardingStates.CURRENT_WEIGHT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, current_weight_handler)
        ],
        OnboardingStates.TARGET_WEIGHT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, target_weight_handler)
        ],
        OnboardingStates.GOAL: [
            CallbackQueryHandler(goal_callback, pattern="^goal_")
        ],
        OnboardingStates.ACTIVITY_LEVEL: [
            CallbackQueryHandler(activity_level_callback, pattern="^activity_")
        ],
        OnboardingStates.DIET_TYPE: [
            CallbackQueryHandler(diet_type_callback, pattern="^diet_")
        ],
        OnboardingStates.BUDGET_CATEGORY: [
            CallbackQueryHandler(budget_category_callback, pattern="^budget_")
        ],
        OnboardingStates.ALLERGIES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, allergies_handler),
            CallbackQueryHandler(skip_allergies_callback, pattern="^skip_allergies")
        ],
        OnboardingStates.CHRONIC_CONDITIONS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, chronic_conditions_handler),
            CallbackQueryHandler(skip_chronic_conditions_callback, pattern="^skip_chronic_conditions")
        ],
        OnboardingStates.REMOVED_ORGANS: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, removed_organs_handler),
            CallbackQueryHandler(skip_removed_organs_callback, pattern="^skip_removed_organs")
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_command)],
    per_message=False,
)
