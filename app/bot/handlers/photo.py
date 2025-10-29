"""
Обработчик фото для распознавания еды
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger
import io
from datetime import datetime, date

from app.services.claude_ai import claude_service
from app.services.meal_service import MealService
from app.services.usage_service import UsageService
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

            # Распознавание через Claude API
            result = await claude_service.analyze_food_photo(
                image_bytes=image_bytes,
                additional_context=f"Пользователь придерживается диеты: {db_user.diet_type.value if db_user.diet_type else 'всеядный'}"
            )

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
                    "photo_file_id": photo.file_id
                }

                # Формируем текст с результатами
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

                # Спрашиваем намерение: будет есть или просто интересуется
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

                logger.info(f"Food recognition successful for user {user.id}: {len(dishes)} dish(es)")

                return FoodAddStates.ASKING_INTENTION

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
        logger.error(f"Error in photo recognition for user {user.id}: {e}")

        await processing_msg.edit_text(
            "❌ Произошла ошибка при обработке фото.\n\n"
            "Пожалуйста, попробуйте отправить фото заново.",
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
                foods_data.append({
                    "name": dish["name"],
                    "portion_size": dish["portion_size_grams"],
                    "portion_description": dish.get("portion_description"),
                    "calories": dish["nutrition"]["calories"],
                    "proteins": dish["nutrition"]["proteins"],
                    "fats": dish["nutrition"]["fats"],
                    "carbs": dish["nutrition"]["carbs"],
                    "ingredients": dish.get("ingredients", []),
                    "confidence_score": dish.get("confidence")
                })

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
                    logger.warning(f"Error checking plan deviation: {e}")

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
        logger.error(f"Error adding meal for user {user.id}: {e}")

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
