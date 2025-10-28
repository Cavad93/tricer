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
    skip_keyboard,
    main_menu_keyboard,
)
from app.bot.states import OnboardingStates
from app.models.user import Gender, Goal, ActivityLevel, DietType
from app.services.nutrition_calc import NutritionCalculator
from loguru import logger


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start"""
    user = update.effective_user

    logger.info(f"User {user.id} started the bot")

    # Проверяем, есть ли пользователь в БД
    # TODO: добавить проверку в БД

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я NutriAI - твой персональный AI-нутрициолог!\n\n"
        "Я помогу тебе:\n"
        "✅ Отслеживать питание (просто отправь фото еды)\n"
        "✅ Считать калории и БЖУ автоматически\n"
        "✅ Достигать твоих целей по весу и здоровью\n"
        "✅ Получать персональные рекомендации от AI\n\n"
        "Давай начнем с настройки твоего профиля! Это займет всего 2 минуты."
    )

    await update.message.reply_text(
        "Выбери свой пол:",
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

    # Рассчитываем целевые показатели
    await calculate_and_save_profile(update, context)

    return ConversationHandler.END


async def skip_allergies_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Пропуск ввода аллергий"""
    query = update.callback_query
    await query.answer()

    context.user_data["allergies"] = []

    await query.edit_message_text("⏭️ Пропускаем...")

    # Рассчитываем целевые показатели
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
    from app.db.session import AsyncSessionLocal
    from app.models.user import User
    from sqlalchemy import select
    from datetime import datetime

    async with AsyncSessionLocal() as session:
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
                user.allergies = user_data.get("allergies", [])
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
                    allergies=user_data.get("allergies", []),
                    onboarding_completed=True,
                )
                session.add(user)

            await session.commit()
            logger.info(f"User {update.effective_user.id} profile saved to database")

        except Exception as e:
            await session.rollback()
            logger.error(f"Error saving user profile: {e}")
            raise

    # Показываем результаты
    await message.edit_text(
        "✅ Отлично! Твой профиль настроен!\n\n"
        f"📊 Твои целевые показатели на день:\n"
        f"🔥 Калории: {nutrition_targets.calories} ккал\n"
        f"🥩 Белки: {nutrition_targets.proteins}г\n"
        f"🧈 Жиры: {nutrition_targets.fats}г\n"
        f"🍞 Углеводы: {nutrition_targets.carbs}г\n\n"
        "Теперь ты можешь начать отслеживать своё питание!"
    )

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Что хочешь сделать?",
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
        OnboardingStates.ALLERGIES: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, allergies_handler),
            CallbackQueryHandler(skip_allergies_callback, pattern="^skip_allergies")
        ],
    },
    fallbacks=[CommandHandler("cancel", cancel_command)],
    per_message=False,
)
