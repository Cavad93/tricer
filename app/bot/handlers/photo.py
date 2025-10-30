"""
Обработчик фото для распознавания еды
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger
import io
from datetime import datetime, date

from app.services.claude_ai import get_claude_service
from app.services.scheduler_service import get_scheduler
from app.services.meal_service import MealService
from app.services.usage_service import UsageService
from app.services.food_correction_service import FoodCorrectionService
from app.bot.keyboards import meal_type_keyboard, back_to_menu_keyboard, main_menu_keyboard
from app.bot.states import FoodAddStates
from app.models.meal import MealType
from app.models.user import User
from app.db.session import async_session_maker
from sqlalchemy import select


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик фото еды - распознавание и предложение добавить в дневник
    """
    user = update.effective_user

    logger.info(f"User {user.id} sent a photo for food recognition")

    # Уведомление пользователя
    processing_msg = await update.message.reply_text(
        "🔍 Анализирую фото...\nЭто может занять несколько секунд."
    )

    try:
        # Проверка лимитов
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await processing_msg.edit_text(
                    "❌ Пользователь не найден.\nИспользуйте /start для регистрации.",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Проверяем лимит на распознавание фото
            # TODO: implement photo limit check via UsageService

            # Скачивание фото
            photo = update.message.photo[-1]  # Самое большое разрешение
            file = await context.bot.get_file(photo.file_id)
            image_bytes_io = io.BytesIO()
            await file.download_to_memory(image_bytes_io)
            image_bytes = image_bytes_io.getvalue()

            logger.info(f"Photo downloaded, size: {len(image_bytes)} bytes")

            # Вычисляем hash фото для поиска существующих коррекций
            photo_hash = FoodCorrectionService.calculate_photo_hash(image_bytes)
            logger.info(f"Photo hash: {photo_hash[:10]}...")

            # Сохраняем hash в контекст для последующего использования
            context.user_data["photo_hash"] = photo_hash
            context.user_data["photo_bytes"] = image_bytes  # Сохраняем на случай если потребуется

            # Проверяем есть ли сохраненная коррекция для этого фото
            existing_correction = await FoodCorrectionService.find_correction_by_hash(
                session=session,
                user_id=db_user.id,
                photo_hash=photo_hash
            )

            # Если коррекция найдена - используем её данные
            if existing_correction:
                logger.info(f"Found existing correction for user {user.id}, using it")
                result = existing_correction.corrected_data
                # Увеличиваем счетчик использования
                await FoodCorrectionService.increment_usage(session, existing_correction.id)
                # Сохраняем ID коррекции для дальнейшего использования
                context.user_data["correction_id"] = existing_correction.id
                # Добавляем флаг что это из коррекции
                context.user_data["from_correction"] = True
            else:
                # Распознавание через Claude API
                logger.info(f"No correction found, using AI recognition")
                result = await get_claude_service().analyze_food_photo(
                    image_bytes=image_bytes,
                    additional_context=f"Пользователь придерживается диеты: {db_user.diet_type.value if db_user.diet_type else 'всеядный'}"
                )
                # Сохраняем оригинальное распознавание для потенциальной коррекции
                context.user_data["original_recognition"] = result
                context.user_data["from_correction"] = False

            # Проверка на неподходящий контент
            if result and result.get("inappropriate_content", False):
                reason = result.get("reason", "неподходящий контент")
                warning_text = (
                    "⚠️ *Обнаружен неподходящий контент*\n\n"
                    f"Причина: {reason}\n\n"
                    "⛔️ *Это не смешно и не корректно.*\n\n"
                    "Я создан, чтобы помогать с питанием и здоровьем. "
                    "Если у тебя есть проблемы, с которыми нужна помощь, "
                    "пожалуйста, обратись к специалисту:\n\n"
                    "🆘 *Экстренная психологическая помощь:*\n"
                    "• Телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно)\n"
                    "• Служба поддержки: 8-495-989-50-50\n\n"
                    "💚 Береги себя. Если что-то беспокоит - обратись за помощью к профессионалам."
                )

                await processing_msg.edit_text(
                    warning_text,
                    parse_mode="Markdown",
                    reply_markup=back_to_menu_keyboard()
                )

                logger.warning(f"Inappropriate content detected for user {user.id}: {reason}")
                return ConversationHandler.END

            # Формирование ответа
            if result and "dishes" in result and len(result["dishes"]) > 0:
                dishes = result["dishes"]

                # Сохраняем результат в контекст для последующего добавления
                context.user_data["recognized_food"] = {
                    "dishes": dishes,
                    "total_nutrition": result.get("total_nutrition", {}),
                    "photo_file_id": photo.file_id,
                    "is_packaged": result.get("is_packaged", False),
                    "package_info": result.get("package_info", {})
                }

                # ПРОВЕРКА: Если продукт в упаковке - уточняем намерение
                if result.get("is_packaged") and result.get("needs_confirmation"):
                    package_info = result.get("package_info", {})
                    product_name = package_info.get("product_name", dishes[0]["name"])
                    brand = package_info.get("brand", "")
                    weight = package_info.get("weight_grams", dishes[0].get("portion_size_grams", 0))

                    response_text = "📦 *Распознан упакованный продукт!*\n\n"
                    if brand:
                        response_text += f"🏷 Бренд: {brand}\n"
                    response_text += f"📝 Продукт: {product_name}\n"
                    if weight:
                        response_text += f"⚖️ Вес: {weight}г\n"
                    response_text += f"\n🔥 {dishes[0]['nutrition']['calories']} ккал | "
                    response_text += f"Б: {dishes[0]['nutrition']['proteins']}г | "
                    response_text += f"Ж: {dishes[0]['nutrition']['fats']}г | "
                    response_text += f"У: {dishes[0]['nutrition']['carbs']}г\n\n"
                    response_text += "❓ *Уточни, пожалуйста:*\n"
                    response_text += "Ты уже съел это или только планируешь?"

                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                    intent_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Уже съел, добавить в дневник", callback_data="intention_eat")],
                        [InlineKeyboardButton("ℹ️ Просто узнать информацию", callback_data="intention_info")],
                        [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
                    ])

                    await processing_msg.edit_text(
                        response_text,
                        parse_mode="Markdown",
                        reply_markup=intent_keyboard
                    )

                    logger.info(f"Packaged product detected for user {user.id}, asking for intent")
                    return FoodAddStates.ASKING_FOOD_INTENTION

                # Формируем текст с результатами (для неупакованных продуктов)
                response_text = "✅ *Распознано!*\n\n"

                for i, dish in enumerate(dishes, 1):
                    nutrition = dish["nutrition"]
                    portion_desc = dish.get("portion_description", f"~{dish['portion_size_grams']}г")

                    response_text += (
                        f"{'🍽' if i == 1 else '➕'} *{dish['name']}*\n"
                        f"Порция: {portion_desc}\n"
                        f"🔥 {nutrition['calories']} ккал | "
                        f"🥩 Б: {nutrition['proteins']}г | "
                        f"🧈 Ж: {nutrition['fats']}г | "
                        f"🍞 У: {nutrition['carbs']}г\n"
                    )

                    if dish.get("confidence", 1.0) < 0.7:
                        response_text += "⚠️ Низкая уверенность\n"

                    response_text += "\n"

                # Итого если несколько блюд
                if len(dishes) > 1:
                    total = result.get("total_nutrition", {})
                    response_text += (
                        f"📊 *Всего:*\n"
                        f"🔥 {total.get('calories', 0)} ккал | "
                        f"Б: {total.get('proteins', 0)}г | "
                        f"Ж: {total.get('fats', 0)}г | "
                        f"У: {total.get('carbs', 0)}г\n\n"
                    )

                # Добавляем информацию если данные из коррекции
                if context.user_data.get("from_correction"):
                    response_text += "♻️ _Использованы данные из предыдущей коррекции_\n\n"

                # Спрашиваем подтверждение: распознано верно?
                response_text += "✅ *Всё распознано верно?*"

                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                verification_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Да, всё верно", callback_data="verification_correct")],
                    [InlineKeyboardButton("✏️ Нужны уточнения", callback_data="verification_incorrect")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
                ])

                await processing_msg.edit_text(
                    response_text,
                    parse_mode="Markdown",
                    reply_markup=verification_keyboard
                )

                logger.info(f"Food recognition successful for user {user.id}: {len(dishes)} dish(es)")

                return FoodAddStates.ASKING_VERIFICATION

            else:
                await processing_msg.edit_text(
                    "❌ Не удалось распознать еду на фото.\n\n"
                    "Попробуйте:\n"
                    "• Сделать фото при лучшем освещении\n"
                    "• Сфотографировать блюдо ближе\n"
                    "• Убрать лишние предметы из кадра",
                    reply_markup=back_to_menu_keyboard()
                )

                logger.warning(f"Failed to recognize food for user {user.id}")
                return ConversationHandler.END

    except Exception as e:
        logger.error("Error in photo recognition for user {}: {}", user.id, repr(e))

        await processing_msg.edit_text(
            "❌ Произошла ошибка при обработке фото.\n\n"
            "Пожалуйста, попробуйте отправить фото заново.",
            reply_markup=back_to_menu_keyboard()
        )

        return ConversationHandler.END


async def handle_verification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ответа на вопрос 'Распознано верно?'"""
    query = update.callback_query
    await query.answer()

    verification = query.data.replace("verification_", "")

    if verification == "correct":
        # Пользователь подтвердил - переходим к вопросу о намерении
        recognized_food = context.user_data.get("recognized_food")
        if recognized_food:
            dishes = recognized_food["dishes"]

            # Формируем краткий текст
            response_text = "✅ *Отлично!*\n\n"

            for i, dish in enumerate(dishes, 1):
                nutrition = dish["nutrition"]
                response_text += (
                    f"{'🍽' if i == 1 else '➕'} *{dish['name']}*\n"
                    f"🔥 {nutrition['calories']} ккал\n\n"
                )

            response_text += "🤔 *Ты собираешься это съесть или просто интересуешься?*"

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            intention_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🍽 Буду есть", callback_data="intention_eat")],
                [InlineKeyboardButton("👀 Просто узнать", callback_data="intention_info")],
                [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
            ])

            await query.edit_message_text(
                response_text,
                parse_mode="Markdown",
                reply_markup=intention_keyboard
            )

            return FoodAddStates.ASKING_INTENTION

    elif verification == "incorrect":
        # Пользователь хочет уточнить - запрашиваем текстовое описание
        await query.edit_message_text(
            "✏️ *Хорошо, давай уточним!*\n\n"
            "Напиши, что именно на фото и в каком количестве.\n"
            "Например: _\"Куриная грудка 200г и салат Цезарь\"_\n\n"
            "📝 Чем подробнее опишешь - тем точнее я распознаю в следующий раз!",
            parse_mode="Markdown"
        )

        return FoodAddStates.ASKING_CLARIFICATION

    return ConversationHandler.END


async def handle_clarification(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстового уточнения от пользователя"""
    user = update.effective_user
    clarification_text = update.message.text

    logger.info(f"User {user.id} provided clarification: {clarification_text[:50]}...")

    # Отправляем уточнение AI для перераспознавания
    processing_msg = await update.message.reply_text(
        "🔄 Учитываю твоё уточнение и перераспознаю..."
    )

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await processing_msg.edit_text(
                    "❌ Пользователь не найден",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Получаем сохраненное фото
            photo_bytes = context.user_data.get("photo_bytes")
            photo_hash = context.user_data.get("photo_hash")

            if not photo_bytes or not photo_hash:
                await processing_msg.edit_text(
                    "❌ Фото не найдено. Попробуй отправить его заново.",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Перераспознаем с учетом уточнения пользователя
            result = await get_claude_service().analyze_food_photo(
                image_bytes=photo_bytes,
                additional_context=f"Пользователь уточнил: {clarification_text}\n"
                                   f"Пользователь придерживается диеты: {db_user.diet_type.value if db_user.diet_type else 'всеядный'}"
            )

            if result and "dishes" in result and len(result["dishes"]) > 0:
                dishes = result["dishes"]

                # Сохраняем коррекцию в базу данных
                original_recognition = context.user_data.get("original_recognition", {})
                await FoodCorrectionService.save_correction(
                    session=session,
                    user_id=db_user.id,
                    photo_hash=photo_hash,
                    original_recognition=original_recognition,
                    corrected_data=result,
                    user_clarification=clarification_text
                )

                # Обновляем recognized_food в контексте
                context.user_data["recognized_food"] = {
                    "dishes": dishes,
                    "total_nutrition": result.get("total_nutrition", {}),
                    "photo_file_id": context.user_data.get("recognized_food", {}).get("photo_file_id")
                }

                # Показываем обновленный результат
                response_text = "✅ *Обновленное распознавание:*\n\n"

                for i, dish in enumerate(dishes, 1):
                    nutrition = dish["nutrition"]
                    portion_desc = dish.get("portion_description", f"~{dish['portion_size_grams']}г")

                    response_text += (
                        f"{'🍽' if i == 1 else '➕'} *{dish['name']}*\n"
                        f"Порция: {portion_desc}\n"
                        f"🔥 {nutrition['calories']} ккал | "
                        f"🥩 Б: {nutrition['proteins']}г | "
                        f"🧈 Ж: {nutrition['fats']}г | "
                        f"🍞 У: {nutrition['carbs']}г\n\n"
                    )

                response_text += "💾 _Сохранил твою коррекцию. В следующий раз распознаю точнее!_\n\n"
                response_text += "🤔 *Ты собираешься это съесть или просто интересуешься?*"

                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                intention_keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🍽 Буду есть", callback_data="intention_eat")],
                    [InlineKeyboardButton("👀 Просто узнать", callback_data="intention_info")],
                    [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
                ])

                await processing_msg.edit_text(
                    response_text,
                    parse_mode="Markdown",
                    reply_markup=intention_keyboard
                )

                logger.info(f"Saved correction for user {user.id}, photo_hash: {photo_hash[:10]}...")

                return FoodAddStates.ASKING_INTENTION

            else:
                await processing_msg.edit_text(
                    "❌ Не удалось перераспознать с уточнением.\n\n"
                    "Попробуй отправить фото еще раз.",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

    except Exception as e:
        logger.error("Error in clarification handler: {}", repr(e), exc_info=True)
        await processing_msg.edit_text(
            "❌ Произошла ошибка при обработке уточнения.",
            reply_markup=back_to_menu_keyboard()
        )
        return ConversationHandler.END


async def handle_food_intention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора намерения - есть или просто узнать"""
    query = update.callback_query
    await query.answer()

    intention = query.data.replace("intention_", "")

    if intention == "info":
        # Пользователь просто хотел узнать - показываем финальное сообщение
        recognized_food = context.user_data.get("recognized_food")
        if recognized_food:
            dishes = recognized_food["dishes"]

            response_text = "✅ *Вот информация о блюде:*\n\n"

            for i, dish in enumerate(dishes, 1):
                nutrition = dish["nutrition"]
                portion_desc = dish.get("portion_description", f"~{dish['portion_size_grams']}г")

                response_text += (
                    f"{'🍽' if i == 1 else '➕'} *{dish['name']}*\n"
                    f"Порция: {portion_desc}\n"
                    f"🔥 {nutrition['calories']} ккал | "
                    f"🥩 Б: {nutrition['proteins']}г | "
                    f"🧈 Ж: {nutrition['fats']}г | "
                    f"🍞 У: {nutrition['carbs']}г\n\n"
                )

            response_text += "💡 Если захочешь добавить еду в дневник, просто отправь фото еще раз!"

            await query.edit_message_text(
                response_text,
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )

            # Очищаем контекст
            context.user_data.pop("recognized_food", None)

            logger.info(f"User {update.effective_user.id} checked food info only, not adding to diary")

            return ConversationHandler.END

    elif intention == "eat":
        # Пользователь будет есть - переходим к выбору типа приема пищи
        recognized_food = context.user_data.get("recognized_food")
        if not recognized_food:
            await query.edit_message_text(
                "❌ Данные о еде потеряны. Отправьте фото заново.",
                reply_markup=back_to_menu_keyboard()
            )
            return ConversationHandler.END

        # Формируем текст напоминания
        dishes = recognized_food["dishes"]
        response_text = "✅ *Отлично! Добавляю в дневник.*\n\n"

        for i, dish in enumerate(dishes, 1):
            nutrition = dish["nutrition"]
            response_text += (
                f"{'🍽' if i == 1 else '➕'} {dish['name']}\n"
                f"🔥 {nutrition['calories']} ккал\n"
            )

        response_text += "\n📝 *Выбери тип приема пищи:*"

        await query.edit_message_text(
            response_text,
            parse_mode="Markdown",
            reply_markup=meal_type_keyboard()
        )

        logger.info(f"User {update.effective_user.id} will eat the food, showing meal type selection")

        return FoodAddStates.WAITING_MEAL_TYPE


async def meal_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выбора типа приема пищи - добавление в дневник
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    meal_type_str = query.data.replace("meal_type_", "")

    # Маппинг строки в enum
    meal_type_map = {
        "breakfast": MealType.BREAKFAST,
        "lunch": MealType.LUNCH,
        "dinner": MealType.DINNER,
        "snack": MealType.SNACK
    }

    meal_type = meal_type_map.get(meal_type_str)
    if not meal_type:
        await query.edit_message_text(
            "❌ Неверный тип приема пищи",
            reply_markup=back_to_menu_keyboard()
        )
        return ConversationHandler.END

    # Получаем распознанную еду из контекста
    recognized_food = context.user_data.get("recognized_food")
    if not recognized_food:
        await query.edit_message_text(
            "❌ Данные о еде потеряны. Отправьте фото заново.",
            reply_markup=back_to_menu_keyboard()
        )
        return ConversationHandler.END

    # Сохраняем в дневник
    try:
        async with async_session_maker() as session:
            # Получаем пользователя
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

            # Подготавливаем данные о блюдах
            foods_data = []
            for dish in recognized_food["dishes"]:
                food_data = {
                    "name": dish["name"],
                    "portion_size": dish["portion_size_grams"],
                    "portion_description": dish.get("portion_description"),
                    "calories": dish["nutrition"]["calories"],
                    "proteins": dish["nutrition"]["proteins"],
                    "fats": dish["nutrition"]["fats"],
                    "carbs": dish["nutrition"]["carbs"],
                    "ingredients": dish.get("ingredients", []),
                    "confidence_score": dish.get("confidence")
                }

                # Добавляем микронутриенты если есть
                if "micronutrients" in dish and dish["micronutrients"]:
                    food_data["micronutrients"] = dish["micronutrients"]

                foods_data.append(food_data)

            # Создаем прием пищи
            meal = await MealService.create_meal_with_foods(
                session=session,
                user_id=db_user.id,
                meal_type=meal_type,
                meal_date=date.today(),
                meal_time=datetime.now(),
                foods_data=foods_data,
                photo_url=recognized_food.get("photo_file_id")  # Сохраняем file_id фото
            )

            # Планируем wellness опрос через 30 минут после еды
            try:
                scheduler = get_scheduler()
                if scheduler:
                    scheduler.schedule_wellness_survey(
                        telegram_id=update.effective_user.id,
                        meal_id=meal.id,
                        delay_minutes=30
                    )
                    logger.info(f"Scheduled wellness survey for user {update.effective_user.id}, meal {meal.id}")
            except Exception as e:
                logger.warning("Failed to schedule wellness survey: {}", repr(e))

            # Обновляем суточные микронутриенты если есть данные
            if recognized_food.get("total_micronutrients"):
                from app.services.micronutrient_service import MicronutrientService
                try:
                    await MicronutrientService.update_daily_micronutrients(
                        db=session,
                        user_id=db_user.id,
                        meal_date=date.today(),
                        micronutrients_delta=recognized_food["total_micronutrients"]
                    )
                    logger.info(f"Updated daily micronutrients for user {db_user.id}")
                except Exception as e:
                    logger.warning("Failed to update micronutrients: {}", repr(e))

            # Получаем прогресс за день
            progress = await MealService.get_nutrition_progress(
                session=session,
                user_id=db_user.id,
                target_date=date.today()
            )

            # Проверяем наличие активного плана и отклонения от него
            from app.models.meal_plan import MealPlan
            from sqlalchemy import and_
            from app.bot.texts import FriendlyPhrases

            result_plan = await session.execute(
                select(MealPlan).where(
                    and_(
                        MealPlan.user_id == db_user.id,
                        MealPlan.is_active == True,
                        MealPlan.start_date <= date.today(),
                        MealPlan.end_date >= date.today()
                    )
                ).limit(1)
            )
            active_plan = result_plan.scalar_one_or_none()

            # Формируем сообщение об успехе
            meal_type_names = {
                MealType.BREAKFAST: "Завтрак",
                MealType.LUNCH: "Обед",
                MealType.DINNER: "Ужин",
                MealType.SNACK: "Перекус"
            }

            current = progress["current"]
            target = progress["target"]
            remaining = progress["remaining"]

            success_text = (
                f"✅ Добавлено в *{meal_type_names[meal_type]}*!\n\n"
                f"📊 *Прогресс за сегодня:*\n"
                f"🔥 Калории: {current['calories']}/{target['calories']} ккал "
                f"(осталось {remaining['calories']})\n"
                f"🥩 Белки: {current['proteins']:.0f}/{target['proteins']}г "
                f"(осталось {remaining['proteins']:.0f}г)\n"
                f"🧈 Жиры: {current['fats']:.0f}/{target['fats']}г\n"
                f"🍞 Углеводы: {current['carbs']:.0f}/{target['carbs']}г\n\n"
            )

            # Психотерапевтический подход и проверка отклонений от плана
            deviation_detected = False
            if active_plan and active_plan.plan_data:
                # Проверяем отклонение от запланированного
                try:
                    plan_data = active_plan.plan_data
                    today = date.today()

                    # Ищем запланированное блюдо для этого приема пищи
                    planned_meal = None
                    if active_plan.period == "day":
                        meals = plan_data.get("meals", [])
                    else:
                        days = plan_data.get("days", [])
                        current_day = None
                        for day in days:
                            if day.get("date") == today.isoformat():
                                current_day = day
                                break
                        meals = current_day.get("meals", []) if current_day else []

                    for plan_meal in meals:
                        if plan_meal.get("type") == meal_type.value:
                            planned_meal = plan_meal
                            break

                    if planned_meal:
                        # Получаем калории добавленного блюда
                        added_calories = sum(food["calories"] for food in foods_data)
                        planned_calories = planned_meal.get("total_nutrition", {}).get("calories", 0)

                        # Если отклонение больше 30% - это значительное отклонение
                        if planned_calories > 0:
                            deviation_percent = abs(added_calories - planned_calories) / planned_calories
                            if deviation_percent > 0.3:
                                deviation_detected = True
                except Exception as e:
                    logger.warning("Error checking plan deviation: {}", repr(e))

            # Предупреждения и психотерапевтический подход
            if current['calories'] > target['calories']:
                # Превышение дневной нормы - используем поддерживающий подход
                overage = current['calories'] - target['calories']
                success_text += (
                    f"💭 *Ты превысил дневную норму на {overage} ккал*\n\n"
                    f"{FriendlyPhrases.get_support_on_deviation()}\n\n"
                )

                # Предлагаем корректировку плана
                if active_plan:
                    success_text += (
                        "💡 *Могу помочь скорректировать оставшиеся приемы пищи на сегодня, "
                        "чтобы минимизировать превышение.*\n"
                        "Напиши мне в AI-чат, если хочешь обсудить план на оставшийся день.\n\n"
                    )
            elif deviation_detected:
                # Отклонение от плана без превышения - мягкий подход
                success_text += (
                    f"💭 *Заметил, что ты съел что-то другое, не по плану*\n\n"
                    f"Это абсолютно нормально! Жизнь непредсказуема, и важно уметь адаптироваться. "
                    f"{FriendlyPhrases.get_support_on_deviation()}\n\n"
                    f"Хорошая новость: у тебя осталось {remaining['calories']} ккал на сегодня. "
                    f"Этого достаточно для полноценных приемов пищи!\n\n"
                )
            elif remaining['calories'] < 300:
                success_text += f"💡 Осталось всего {remaining['calories']} ккал на сегодня\n"
            else:
                # Все идет по плану - поощрение
                success_text += f"{FriendlyPhrases.get_encouragement()}\n"

            await query.edit_message_text(
                success_text,
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )

            # Очищаем контекст
            context.user_data.pop("recognized_food", None)

            logger.info(f"Meal added successfully for user {user.id}, meal_id: {meal.id}")

            return ConversationHandler.END

    except Exception as e:
        logger.error("Error adding meal for user {}: {}", user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при добавлении в дневник.\nПопробуйте позже.",
            reply_markup=back_to_menu_keyboard()
        )

        return ConversationHandler.END


async def cancel_food_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена добавления еды"""
    query = update.callback_query
    await query.answer()

    context.user_data.pop("recognized_food", None)

    await query.edit_message_text(
        "❌ Добавление отменено",
        reply_markup=main_menu_keyboard()
    )

    return ConversationHandler.END
