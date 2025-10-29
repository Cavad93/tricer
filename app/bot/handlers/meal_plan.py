"""
Обработчики для функции "Рацион"
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger

from app.bot.states import MealPlanStates
from app.bot.keyboards import back_to_menu_keyboard
from app.db.session import async_session_maker
from app.models.user import User
from app.models.meal_plan import PlanPeriod
from app.services.meal_plan_service import MealPlanService
from app.services.shopping_list_service import ShoppingListService
from app.services.pdf_generator import PDFGeneratorService
from sqlalchemy import select


def meal_plan_period_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора периода плана питания"""
    keyboard = [
        [InlineKeyboardButton("📅 На день", callback_data="plan_period_day")],
        [InlineKeyboardButton("📆 На неделю", callback_data="plan_period_week")],
        [InlineKeyboardButton("🗓 На месяц", callback_data="plan_period_month")],
        [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def meal_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало создания плана питания"""
    query = update.callback_query
    if query:
        await query.answer()

    # Если это callback "create_new_plan", деактивируем старые планы и показываем выбор периода
    if query and query.data == 'create_new_plan':
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            user = result.scalar_one_or_none()

            if user:
                # Деактивируем старые планы
                await MealPlanService.deactivate_old_plans(session, user.telegram_id)

        # Показываем выбор периода для нового плана
        text = """🍽 Создание плана питания

Я создам для тебя персональный план питания с учетом твоих целей, предпочтений и бюджета!

На какой период создать план?"""

        await query.edit_message_text(text, reply_markup=meal_plan_period_keyboard())
        return MealPlanStates.WAITING_PERIOD

    # Проверяем есть ли активный план
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.onboarding_completed:
            text = "❌ Сначала завершите настройку профиля! Используйте /start"

            if query:
                await query.edit_message_text(text, reply_markup=back_to_menu_keyboard())
            else:
                await update.message.reply_text(text, reply_markup=back_to_menu_keyboard())

            return ConversationHandler.END

        # Проверяем активный план
        active_plan = await MealPlanService.get_active_meal_plan(session, user.telegram_id)

        if active_plan:
            # Словарь для отображения периода
            period_names = {
                "day": "На день",
                "week": "На неделю",
                "month": "На месяц"
            }
            period_str = active_plan.period_type.value if hasattr(active_plan.period_type, 'value') else str(active_plan.period_type)
            period_name = period_names.get(period_str.lower(), "Неизвестно")

            # Есть активный план - предлагаем просмотреть или создать новый
            text = f"""У тебя уже есть активный план питания!

📋 Период: {period_name}
📅 Даты: {active_plan.start_date.strftime('%d.%m.%Y')} - {active_plan.end_date.strftime('%d.%m.%Y')}

Что хочешь сделать?"""

            keyboard = [
                [InlineKeyboardButton("📄 Просмотреть план", callback_data=f"view_plan_{active_plan.id}")],
                [InlineKeyboardButton("🛒 Список покупок", callback_data=f"shopping_list_{active_plan.id}")],
                [InlineKeyboardButton("🔄 Создать новый", callback_data="create_new_plan")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
            ]

            if query:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

            return ConversationHandler.END

    # Нет активного плана - создаем новый
    text = """
🍽 Создание плана питания

Я создам для тебя персональный план питания с учетом твоих целей, предпочтений и бюджета!

На какой период создать план?
"""

    if query:
        await query.edit_message_text(text, reply_markup=meal_plan_period_keyboard())
    else:
        await update.message.reply_text(text, reply_markup=meal_plan_period_keyboard())

    return MealPlanStates.WAITING_PERIOD


async def meal_plan_period_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора периода плана питания"""
    query = update.callback_query
    await query.answer()

    # Определяем период
    period_map = {
        "plan_period_day": PlanPeriod.DAY,
        "plan_period_week": PlanPeriod.WEEK,
        "plan_period_month": PlanPeriod.MONTH,
    }

    period = period_map.get(query.data)

    if not period:
        await query.edit_message_text(
            "❌ Ошибка выбора периода",
            reply_markup=back_to_menu_keyboard()
        )
        return ConversationHandler.END

    # Сохраняем период в контекст
    context.user_data["meal_plan_period"] = period

    period_text = {
        PlanPeriod.DAY: "1 день",
        PlanPeriod.WEEK: "неделю (7 дней)",
        PlanPeriod.MONTH: "месяц (30 дней)"
    }[period]

    # Инициализируем счетчик вопросов и данные
    context.user_data["preference_step"] = 1
    context.user_data["favorite_foods"] = None
    context.user_data["additional_dislikes"] = None
    context.user_data["special_requests"] = None

    # Используем дружелюбные фразы
    from app.bot.texts import FriendlyPhrases
    import random

    clarify_phrase = random.choice(FriendlyPhrases.CLARIFY_PREFERENCES)

    # Задаем первый вопрос
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    skip_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Пропустить", callback_data="preferences_skip")]
    ])

    await query.edit_message_text(
        f"✅ Отлично! Создам план на {period_text}.\n\n"
        f"{clarify_phrase}\n\n"
        "❓ <b>Вопрос 1 из 3:</b> Есть ли у тебя любимые блюда или продукты, которые хотел бы видеть в плане?\n\n"
        "Напиши их через запятую или нажми 'Пропустить'.",
        reply_markup=skip_keyboard,
        parse_mode='HTML'
    )

    return MealPlanStates.ASKING_PREFERENCES


async def handle_preference_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Универсальный обработчик ответов на вопросы о предпочтениях"""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    step = context.user_data.get("preference_step", 1)

    # Определяем источник: callback или текст
    is_skip = update.callback_query is not None

    if is_skip:
        query = update.callback_query
        await query.answer()
        response = None
    else:
        response = update.message.text.strip()

    # Сохраняем ответ в зависимости от шага
    if step == 1:
        context.user_data["favorite_foods"] = response
        context.user_data["preference_step"] = 2

        skip_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Пропустить", callback_data="preferences_skip")]
        ])

        text = "❓ <b>Вопрос 2 из 3:</b> Есть ли продукты, которые категорически не хочешь видеть в плане?\n\n" \
               "Напиши их через запятую или нажми 'Пропустить'."

        if response:
            text = "✅ Отлично, учту!\n\n" + text

        if is_skip:
            await query.edit_message_text(text, reply_markup=skip_keyboard, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=skip_keyboard, parse_mode='HTML')

        return MealPlanStates.ASKING_PREFERENCES

    elif step == 2:
        context.user_data["additional_dislikes"] = response
        context.user_data["preference_step"] = 3

        skip_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➡️ Пропустить", callback_data="preferences_skip")]
        ])

        text = "❓ <b>Вопрос 3 из 3:</b> Есть ли какие-то особые пожелания к плану?\n\n" \
               "Например: больше белка, легкие перекусы, готовка до 30 мин и т.д.\n\n" \
               "Напиши свои пожелания или нажми 'Пропустить'."

        if response:
            text = "✅ Понял!\n\n" + text

        if is_skip:
            await query.edit_message_text(text, reply_markup=skip_keyboard, parse_mode='HTML')
        else:
            await update.message.reply_text(text, reply_markup=skip_keyboard, parse_mode='HTML')

        return MealPlanStates.ASKING_PREFERENCES

    elif step == 3:
        context.user_data["special_requests"] = response

        # Все вопросы заданы, начинаем генерацию
        from app.bot.texts import FriendlyPhrases
        import random

        creation_phrase = random.choice(FriendlyPhrases.PLAN_CREATION_START)

        period = context.user_data.get("meal_plan_period")
        period_text = {
            PlanPeriod.DAY: "1 день",
            PlanPeriod.WEEK: "неделю (7 дней)",
            PlanPeriod.MONTH: "месяц (30 дней)"
        }[period]

        progress_text = f"{creation_phrase}\n\n" \
                       f"⏳ Создаю персональный план питания на {period_text}...\n\n" \
                       "Это может занять до 2 минут. Пожалуйста, подожди."

        if is_skip:
            progress_message = await query.edit_message_text(progress_text)
        else:
            progress_message = await update.message.reply_text(progress_text)

        return await generate_meal_plan_with_preferences(update, context, progress_message)


async def handle_feedback_positive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка положительной обратной связи"""
    query = update.callback_query
    await query.answer()

    plan_id = context.user_data.get("current_plan_id")

    # Используем дружелюбные фразы для поощрения
    from app.bot.texts import FriendlyPhrases
    import random

    praise = random.choice(FriendlyPhrases.PRAISE)

    text = f"{praise}\n\n" \
           "Если понадобится помощь или захочешь изменить план - обращайся! 💚\n\n" \
           "Чтобы посмотреть план в любой момент, нажми 📋 Рацион в меню."

    keyboard = [
        [InlineKeyboardButton("📄 Просмотреть план", callback_data=f"view_plan_{plan_id}")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ConversationHandler.END


async def handle_feedback_negative(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка отрицательной обратной связи - запрос пожеланий"""
    query = update.callback_query
    await query.answer()

    text = "🔄 Хорошо, давай скорректируем план!\n\n" \
           "Расскажи, что именно ты хотел бы изменить?\n\n" \
           "Например:\n" \
           "• Заменить определенные блюда\n" \
           "• Изменить калорийность\n" \
           "• Убрать/добавить продукты\n" \
           "• Изменить время приготовления\n\n" \
           "Напиши свои пожелания:"

    cancel_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
    ])

    await query.edit_message_text(text, reply_markup=cancel_keyboard)

    return MealPlanStates.ASKING_CHANGES


async def handle_change_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка запроса на изменение плана"""
    change_requests = update.message.text.strip()

    if not change_requests:
        await update.message.reply_text(
            "❌ Пожалуйста, опиши что хочешь изменить.",
            reply_markup=back_to_menu_keyboard()
        )
        return ConversationHandler.END

    # Показываем прогресс
    progress_message = await update.message.reply_text(
        "⏳ Отлично! Вношу изменения в план...\n\n"
        "Это может занять до 2 минут. Подожди немного."
    )

    try:
        period = context.user_data.get("meal_plan_period")
        old_plan_id = context.user_data.get("current_plan_id")

        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            user = result.scalar_one_or_none()

            # Деактивируем старый план
            await MealPlanService.deactivate_old_plans(session, user.telegram_id)

            # Собираем preferences из context с добавлением новых пожеланий
            old_preferences = {
                "favorite_foods": context.user_data.get("favorite_foods"),
                "additional_dislikes": context.user_data.get("additional_dislikes"),
                "special_requests": context.user_data.get("special_requests")
            }

            # Объединяем старые пожелания с новыми
            combined_requests = ""
            if old_preferences.get("special_requests"):
                combined_requests = old_preferences["special_requests"] + "\n\n"
            combined_requests += f"ВАЖНЫЕ ИЗМЕНЕНИЯ: {change_requests}"

            new_preferences = {
                "favorite_foods": old_preferences.get("favorite_foods"),
                "additional_dislikes": old_preferences.get("additional_dislikes"),
                "special_requests": combined_requests
            }

            # Генерируем новый план с учетом изменений
            meal_plan = await MealPlanService.generate_meal_plan(
                session,
                user.telegram_id,
                period,
                preferences=new_preferences
            )

            await progress_message.edit_text(
                "✅ План обновлен!\n\n"
                "📊 Создаю новый список покупок..."
            )

            # Создаем новый список покупок
            shopping_list = await ShoppingListService.create_shopping_list(
                session,
                meal_plan.id,
                search_prices=True
            )

            await progress_message.edit_text(
                "✅ Список покупок готов!\n\n"
                "📄 Генерирую PDF документы..."
            )

            # Генерируем новые PDF
            days = await MealPlanService.get_meal_plan_days(session, meal_plan.id)
            days_data = []

            for day in days:
                meals = await MealPlanService.get_day_meals(session, day.id)
                days_data.append((day, meals))

            period_text = {
                PlanPeriod.DAY: "1 день",
                PlanPeriod.WEEK: "неделю (7 дней)",
                PlanPeriod.MONTH: "месяц (30 дней)"
            }[period]

            # PDF с планом питания
            pdf_plan_path = await PDFGeneratorService.generate_meal_plan_pdf(
                meal_plan,
                days_data,
                user.preferred_name or user.first_name,
                user.city
            )

            # PDF со списком покупок
            items = await ShoppingListService.get_shopping_items(session, shopping_list.id)
            pdf_shopping_path = await PDFGeneratorService.generate_shopping_list_pdf(
                shopping_list,
                items,
                meal_plan,
                user.preferred_name or user.first_name,
                user.city
            )

            shopping_list.pdf_path = pdf_shopping_path
            await session.commit()

        # Показываем результат
        await progress_message.edit_text(
            f"✨ Готово! План обновлен с учетом твоих пожеланий!\n\n"
            f"Отправляю новые PDF файлы..."
        )

        # Отправляем новые PDF
        from telegram import InputFile

        with open(pdf_plan_path, 'rb') as pdf_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(pdf_file, filename=f"План_питания_{period_text}_обновленный.pdf"),
                caption=f"📋 Обновленный план питания на {period_text}"
            )

        with open(pdf_shopping_path, 'rb') as pdf_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(pdf_file, filename=f"Список_покупок_{period_text}_обновленный.pdf"),
                caption=f"🛒 Обновленный список покупок (~{shopping_list.total_cost:.2f} ₽)"
            )

        # Снова запрашиваем обратную связь
        from app.bot.texts import FriendlyPhrases
        import random

        feedback_phrase = random.choice(FriendlyPhrases.FEEDBACK_REQUEST)

        feedback_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Теперь отлично!", callback_data="feedback_positive")],
            [InlineKeyboardButton("🔄 Еще изменения", callback_data="feedback_negative")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])

        context.user_data["current_plan_id"] = meal_plan.id

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📝 {feedback_phrase}",
            reply_markup=feedback_keyboard
        )

        logger.info(f"Meal plan updated for user {update.effective_user.id}: plan_id={meal_plan.id}")

        return MealPlanStates.ASKING_FEEDBACK

    except Exception as e:
        logger.error(f"Error updating meal plan: {e}", exc_info=True)

        await progress_message.edit_text(
            "❌ Произошла ошибка при обновлении плана.\n\n"
            "Попробуй позже или обратись в поддержку.",
            reply_markup=back_to_menu_keyboard()
        )

        return ConversationHandler.END


async def generate_meal_plan_with_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE, progress_message) -> int:
    """Генерация плана с учетом предпочтений"""
    period = context.user_data.get("meal_plan_period")

    try:
        # Генерируем план через AI
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == update.effective_user.id)
            )
            user = result.scalar_one_or_none()

            # Деактивируем старые планы
            await MealPlanService.deactivate_old_plans(session, user.telegram_id)

            # Собираем preferences из context
            preferences = {
                "favorite_foods": context.user_data.get("favorite_foods"),
                "additional_dislikes": context.user_data.get("additional_dislikes"),
                "special_requests": context.user_data.get("special_requests")
            }

            # Генерируем новый план с учетом preferences
            meal_plan = await MealPlanService.generate_meal_plan(
                session,
                user.telegram_id,
                period,
                preferences=preferences
            )

            await progress_message.edit_text(
                f"✅ План питания создан!\n\n"
                f"📊 Теперь создаю список покупок и рассчитываю стоимость..."
            )

            # Создаем список покупок
            shopping_list = await ShoppingListService.create_shopping_list(
                session,
                meal_plan.id,
                search_prices=True
            )

            await progress_message.edit_text(
                f"✅ Список покупок готов!\n\n"
                f"📄 Генерирую PDF документы..."
            )

            # Генерируем PDF
            days = await MealPlanService.get_meal_plan_days(session, meal_plan.id)
            days_data = []

            for day in days:
                meals = await MealPlanService.get_day_meals(session, day.id)
                days_data.append((day, meals))

            # PDF с планом питания
            pdf_plan_path = await PDFGeneratorService.generate_meal_plan_pdf(
                meal_plan,
                days_data,
                user.preferred_name or user.first_name,
                user.city
            )

            # PDF со списком покупок
            items = await ShoppingListService.get_shopping_items(session, shopping_list.id)
            pdf_shopping_path = await PDFGeneratorService.generate_shopping_list_pdf(
                shopping_list,
                items,
                meal_plan,
                user.preferred_name or user.first_name,
                user.city
            )

            # Сохраняем пути к PDF
            shopping_list.pdf_path = pdf_shopping_path
            await session.commit()

        # Показываем результат
        await progress_message.edit_text(
            f"✨ Готово! Твой план питания на {period_text} создан!\n\n"
            f"📊 Калорий в день: ~{meal_plan.daily_calories} ккал\n"
            f"🛒 Стоимость продуктов: ~{shopping_list.total_cost:.2f} ₽\n\n"
            f"Отправляю тебе PDF файлы..."
        )

        # Отправляем PDF файлы
        with open(pdf_plan_path, 'rb') as pdf_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(pdf_file, filename=f"План_питания_{period_text}.pdf"),
                caption=f"📋 План питания на {period_text}"
            )

        with open(pdf_shopping_path, 'rb') as pdf_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=InputFile(pdf_file, filename=f"Список_покупок_{period_text}.pdf"),
                caption=f"🛒 Список покупок (примерная стоимость: {shopping_list.total_cost:.2f} ₽)"
            )

        # Показываем краткую информацию
        summary_text = f"""
✅ <b>План питания успешно создан!</b>

📅 Период: {period_text}
🎯 Калорий в день: {meal_plan.daily_calories} ккал
💰 Стоимость продуктов: ~{shopping_list.total_cost:.2f} ₽

<i>Все файлы сохранены и будут обновляться автоматически.</i>
"""

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=summary_text,
            parse_mode='HTML'
        )

        logger.info(f"Meal plan created for user {update.effective_user.id}: plan_id={meal_plan.id}")

        # Запрашиваем обратную связь
        from app.bot.texts import FriendlyPhrases
        import random

        feedback_phrase = random.choice(FriendlyPhrases.FEEDBACK_REQUEST)

        feedback_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Всё отлично!", callback_data="feedback_positive")],
            [InlineKeyboardButton("🔄 Хочу изменить", callback_data="feedback_negative")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])

        # Сохраняем plan_id в контексте для дальнейшего использования
        context.user_data["current_plan_id"] = meal_plan.id

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"📝 {feedback_phrase}",
            reply_markup=feedback_keyboard
        )

        return MealPlanStates.ASKING_FEEDBACK

    except Exception as e:
        logger.error(f"Error creating meal plan: {e}", exc_info=True)

        await progress_message.edit_text(
            f"❌ Произошла ошибка при создании плана питания.\n\n"
            f"Попробуй позже или обратись в поддержку.",
            reply_markup=back_to_menu_keyboard()
        )

        return ConversationHandler.END


async def view_meal_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр плана питания"""
    query = update.callback_query
    await query.answer()

    plan_id = int(query.data.split("_")[-1])

    async with async_session_maker() as session:
        meal_plan = await MealPlanService.get_meal_plan_by_id(session, plan_id)

        if not meal_plan:
            await query.edit_message_text(
                "❌ План питания не найден",
                reply_markup=back_to_menu_keyboard()
            )
            return

        days = await MealPlanService.get_meal_plan_days(session, plan_id)

        # Формируем текст с планом
        period_text = {
            "day": "1 день",
            "week": "неделю",
            "month": "месяц"
        }[meal_plan.period_type]

        text = f"📋 <b>План питания на {period_text}</b>\n\n"
        text += f"📅 {meal_plan.start_date.strftime('%d.%m.%Y')} - {meal_plan.end_date.strftime('%d.%m.%Y')}\n"
        text += f"🎯 Калорий в день: {meal_plan.daily_calories} ккал\n\n"

        # Показываем первые 3 дня
        for i, day in enumerate(days[:3]):
            meals = await MealPlanService.get_day_meals(session, day.id)

            text += f"<b>День {day.day_number} ({day.day_date.strftime('%d.%m.%Y')})</b>\n"

            meal_icons = {
                "breakfast": "🌅",
                "lunch": "🌞",
                "dinner": "🌙",
                "snack": "🍎"
            }

            for meal in meals[:2]:  # Показываем только 2 приема пищи
                icon = meal_icons.get(meal.meal_type, "🍽")
                text += f"{icon} {meal.recipe_name} - {meal.calories} ккал\n"

            text += "\n"

        if len(days) > 3:
            text += f"<i>... и ещё {len(days) - 3} дней</i>\n\n"

        text += "📄 Полный план доступен в PDF файле"

        keyboard = [
            [InlineKeyboardButton("🛒 Список покупок", callback_data=f"shopping_list_{meal_plan.id}")],
            [InlineKeyboardButton("🔄 Создать новый план", callback_data="meal_plan")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )


async def view_shopping_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Просмотр списка покупок"""
    query = update.callback_query
    await query.answer()

    plan_id = int(query.data.split("_")[-1])

    async with async_session_maker() as session:
        # Получаем список покупок
        result = await session.execute(
            select(User).where(User.telegram_id == update.effective_user.id)
        )
        user = result.scalar_one_or_none()

        meal_plan = await MealPlanService.get_meal_plan_by_id(session, plan_id)

        if not meal_plan:
            await query.edit_message_text(
                "❌ План питания не найден",
                reply_markup=back_to_menu_keyboard()
            )
            return

        # Проверяем есть ли список покупок
        if not meal_plan.shopping_lists or len(meal_plan.shopping_lists) == 0:
            # Создаем список покупок
            await query.edit_message_text("⏳ Создаю список покупок...")

            shopping_list = await ShoppingListService.create_shopping_list(
                session,
                meal_plan.id,
                search_prices=True
            )
        else:
            shopping_list = meal_plan.shopping_lists[0]

        items = await ShoppingListService.get_shopping_items(session, shopping_list.id)

        # Группируем по категориям
        categories = {}
        for item in items:
            cat = item.category or "Другое"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)

        # Формируем текст
        text = f"🛒 <b>Список покупок</b>\n\n"
        text += f"💰 Общая стоимость: ~{shopping_list.total_cost:.2f} ₽\n"
        text += f"📦 Позиций: {len(items)}\n\n"

        # Показываем первые 10 позиций
        shown = 0
        for category, cat_items in list(categories.items())[:3]:
            text += f"<b>{category}</b>\n"

            for item in cat_items[:3]:
                if shown >= 10:
                    break

                price_text = f" (~{item.estimated_price:.2f} ₽)" if item.estimated_price else ""
                text += f"• {item.product_name} - {item.quantity} {item.unit}{price_text}\n"
                shown += 1

            text += "\n"

        if len(items) > 10:
            text += f"<i>... и ещё {len(items) - 10} позиций</i>\n\n"

        text += "📄 Полный список доступен в PDF файле"

        # Отправляем PDF если есть
        if shopping_list.pdf_path:
            try:
                with open(shopping_list.pdf_path, 'rb') as pdf_file:
                    await context.bot.send_document(
                        chat_id=update.effective_chat.id,
                        document=InputFile(pdf_file, filename="Список_покупок.pdf"),
                        caption=f"🛒 Список покупок (~{shopping_list.total_cost:.2f} ₽)"
                    )
            except Exception as e:
                logger.error(f"Error sending PDF: {e}")

        keyboard = [
            [InlineKeyboardButton("📄 Просмотреть план", callback_data=f"view_plan_{meal_plan.id}")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )


async def cancel_meal_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена создания плана"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "❌ Создание плана питания отменено",
            reply_markup=back_to_menu_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ Создание плана питания отменено",
            reply_markup=back_to_menu_keyboard()
        )

    return ConversationHandler.END
