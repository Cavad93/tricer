"""
Обработчик текстового ввода еды (без фото)
"""
import re
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from loguru import logger
from sqlalchemy import select

from app.db.session import async_session_maker
from app.models.user import User
from app.models.meal import Meal, MealType
from app.services.claude_ai import get_claude_service
from app.bot.keyboards import back_to_menu_keyboard, main_menu_keyboard, meal_type_keyboard


async def handle_text_food_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик текстового ввода еды (например: 'Яичница', 'Гречка 200г')

    Логика:
    1. Если есть вес - анализирует и предлагает добавить
    2. Если нет веса - предлагает 3 варианта порций
    3. Спрашивает будет ли есть
    4. Если да - добавляет в дневник
    """
    user = update.effective_user
    message_text = update.message.text.strip()

    logger.info(f"User {user.id} entered food text: {message_text}")

    # Показываем индикатор "печатает..."
    await update.message.chat.send_action("typing")

    async with async_session_maker() as session:
        try:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await update.message.reply_text(
                    "❌ Пользователь не найден.\nИспользуйте /start для регистрации.",
                    reply_markup=back_to_menu_keyboard()
                )
                return

            # Анализируем ввод через Claude AI
            claude_service = get_claude_service()

            prompt = f"""Проанализируй пользовательский ввод о еде и извлеки информацию.

ВВОД ПОЛЬЗОВАТЕЛЯ: "{message_text}"

ЗАДАЧА:
1. Определи название блюда/продукта
2. Если указан вес - извлеки его
3. Если вес НЕ указан - предложи 3 типичных варианта порций
4. Посчитай калории и БЖУ

ФОРМАТ ОТВЕТА (JSON):
{{
    "dish_name": "название блюда",
    "has_weight": true/false,
    "weight_grams": число или null,
    "portions": [
        {{"name": "Маленькая порция", "grams": 100, "calories": 200, "proteins": 10, "fats": 15, "carbs": 5}},
        {{"name": "Средняя порция", "grams": 150, "calories": 300, "proteins": 15, "fats": 22, "carbs": 7}},
        {{"name": "Большая порция", "grams": 200, "calories": 400, "proteins": 20, "fats": 30, "carbs": 10}}
    ],
    "nutrition": {{
        "calories": число,
        "proteins": число,
        "fats": число,
        "carbs": число
    }}
}}

Примеры:
- "Яичница" → has_weight=false, 3 варианта порций
- "Гречка 200г" → has_weight=true, weight_grams=200, nutrition для 200г
"""

            analysis_json = await claude_service.analyze_text(
                prompt=prompt,
                system="Ты эксперт по питанию. Анализируешь пользовательский ввод о еде и возвращаешь ТОЛЬКО валидный JSON."
            )

            # Пытаемся извлечь JSON из ответа
            import json
            json_match = re.search(r'\{.*\}', analysis_json, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                raise ValueError("Failed to extract JSON from Claude response")

            dish_name = analysis.get("dish_name", message_text)
            has_weight = analysis.get("has_weight", False)

            # ⚠️ WELLNESS CHECK: Проверяем безопасность еды для хронических заболеваний
            wellness_warning = ""
            if db_user.chronic_conditions or db_user.removed_organs or db_user.medical_restrictions:
                wellness_check_prompt = f"""Проанализируй безопасность продукта "{dish_name}" для пользователя с такими ограничениями:

Хронические заболевания: {', '.join(db_user.chronic_conditions) if db_user.chronic_conditions else 'нет'}
Удалённые органы: {', '.join(db_user.removed_organs) if db_user.removed_organs else 'нет'}
Медицинские ограничения: {', '.join(db_user.medical_restrictions) if db_user.medical_restrictions else 'нет'}

ЗАДАЧА:
1. Определи, может ли этот продукт быть ОПАСЕН для данных состояний
2. Если ДА - объясни почему и предложи безопасную альтернативу
3. Если НЕТ - просто ответь "безопасно"

ФОРМАТ ОТВЕТА:
{{
    "is_dangerous": true/false,
    "reason": "краткое объяснение почему опасно (если is_dangerous=true)",
    "safe_alternatives": ["альтернатива1", "альтернатива2"] (если is_dangerous=true)
}}

Отвечай ТОЛЬКО валидным JSON."""

                try:
                    wellness_check_json = await claude_service.analyze_text(
                        prompt=wellness_check_prompt,
                        system="Ты медицинский эксперт по питанию. Анализируешь безопасность продуктов при различных заболеваниях."
                    )

                    wellness_json_match = re.search(r'\{.*\}', wellness_check_json, re.DOTALL)
                    if wellness_json_match:
                        import json
                        wellness_check = json.loads(wellness_json_match.group())

                        if wellness_check.get("is_dangerous"):
                            reason = wellness_check.get("reason", "")
                            alternatives = wellness_check.get("safe_alternatives", [])

                            wellness_warning = f"\n\n⚠️ <b>ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ:</b>\n{reason}\n"
                            if alternatives:
                                wellness_warning += f"\n💡 <b>Безопасные альтернативы:</b> {', '.join(alternatives)}\n"
                            wellness_warning += "\n<i>Конечное решение за тобой, но рекомендуем проконсультироваться с врачом.</i>"
                except Exception as e:
                    logger.warning(f"Wellness check failed for user {user.id}: {repr(e)}")
                    # Продолжаем работу даже если wellness check не удался

            if has_weight:
                # Если вес указан - показываем информацию и спрашиваем будет ли есть
                nutrition = analysis.get("nutrition", {})
                weight = analysis.get("weight_grams", 0)

                text = (
                    f"🍽 <b>{dish_name}</b>\n\n"
                    f"📊 <b>Порция: {weight}г</b>\n"
                    f"🔥 Калории: <b>{nutrition.get('calories', 0)} ккал</b>\n"
                    f"🥩 Белки: {nutrition.get('proteins', 0)}г\n"
                    f"🥑 Жиры: {nutrition.get('fats', 0)}г\n"
                    f"🍞 Углеводы: {nutrition.get('carbs', 0)}г"
                    f"{wellness_warning}\n\n"
                    f"❓ <b>Ты будешь это есть?</b>"
                )

                # Сохраняем данные в контекст
                context.user_data["text_food_data"] = {
                    "dish_name": dish_name,
                    "weight_grams": weight,
                    "nutrition": nutrition
                }

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Да, буду есть", callback_data="text_food_will_eat"),
                        InlineKeyboardButton("❌ Нет, просто узнать", callback_data="text_food_just_info")
                    ],
                    [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
                ])

                await update.message.reply_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )

            else:
                # Если вес НЕ указан - предлагаем варианты порций
                portions = analysis.get("portions", [])

                if not portions or len(portions) < 3:
                    # Fallback если Claude не вернул порции
                    await update.message.reply_text(
                        f"Пожалуйста, уточни вес порции.\n\n"
                        f"Например: <code>{dish_name} 200г</code>",
                        parse_mode='HTML',
                        reply_markup=back_to_menu_keyboard()
                    )
                    return

                text = (
                    f"🍽 <b>{dish_name}</b>"
                    f"{wellness_warning}\n\n"
                    f"Выбери размер порции:"
                )

                # Создаём кнопки для выбора порции
                keyboard = []
                for idx, portion in enumerate(portions):
                    button_text = (
                        f"{portion['name']} ({portion['grams']}г) - "
                        f"{portion['calories']} ккал"
                    )
                    keyboard.append([
                        InlineKeyboardButton(
                            button_text,
                            callback_data=f"text_food_portion_{idx}"
                        )
                    ])

                keyboard.append([InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")])

                # Сохраняем данные в контекст
                context.user_data["text_food_data"] = {
                    "dish_name": dish_name,
                    "portions": portions
                }

                await update.message.reply_text(
                    text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        except Exception as e:
            logger.error("Error in handle_text_food_input for user {}: {}", user.id, repr(e))

            await update.message.reply_text(
                "❌ Не удалось распознать еду.\n\n"
                "Попробуйте указать название и вес, например:\n"
                "• <code>Яичница из 3 яиц</code>\n"
                "• <code>Гречка 200г</code>\n"
                "• <code>Куриная грудка 150г</code>",
                parse_mode='HTML',
                reply_markup=back_to_menu_keyboard()
            )


async def handle_text_food_portion_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора порции из предложенных вариантов"""
    query = update.callback_query
    await query.answer()

    try:
        # Извлекаем индекс порции
        portion_idx = int(query.data.replace("text_food_portion_", ""))
        
        food_data = context.user_data.get("text_food_data", {})
        portions = food_data.get("portions", [])

        if portion_idx < 0 or portion_idx >= len(portions):
            await query.edit_message_text(
                "❌ Неверная порция",
                reply_markup=back_to_menu_keyboard()
            )
            return

        # Получаем выбранную порцию
        portion = portions[portion_idx]
        dish_name = food_data.get("dish_name", "Блюдо")

        # Обновляем данные в контексте
        context.user_data["text_food_data"] = {
            "dish_name": dish_name,
            "weight_grams": portion["grams"],
            "nutrition": {
                "calories": portion["calories"],
                "proteins": portion["proteins"],
                "fats": portion["fats"],
                "carbs": portion["carbs"]
            }
        }

        text = (
            f"🍽 <b>{dish_name}</b>\n\n"
            f"📊 <b>Порция: {portion['grams']}г</b>\n"
            f"🔥 Калории: <b>{portion['calories']} ккал</b>\n"
            f"🥩 Белки: {portion['proteins']}г\n"
            f"🥑 Жиры: {portion['fats']}г\n"
            f"🍞 Углеводы: {portion['carbs']}г\n\n"
            f"❓ <b>Ты будешь это есть?</b>"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Да, буду есть", callback_data="text_food_will_eat"),
                InlineKeyboardButton("❌ Нет, просто узнать", callback_data="text_food_just_info")
            ],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="main_menu")]
        ])

        await query.edit_message_text(
            text,
            parse_mode='HTML',
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error("Error in handle_text_food_portion_selection: {}", repr(e))
        await query.edit_message_text(
            "❌ Произошла ошибка",
            reply_markup=back_to_menu_keyboard()
        )


async def handle_text_food_will_eat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик когда пользователь будет есть - добавляем в дневник"""
    query = update.callback_query
    await query.answer()

    food_data = context.user_data.get("text_food_data", {})
    
    if not food_data:
        await query.edit_message_text(
            "❌ Данные о еде не найдены",
            reply_markup=back_to_menu_keyboard()
        )
        return

    # Спрашиваем тип приёма пищи
    text = (
        f"🍽 <b>{food_data.get('dish_name', 'Блюдо')}</b>\n\n"
        f"Выбери тип приёма пищи:"
    )

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=meal_type_keyboard()
    )


async def handle_text_food_just_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик когда пользователь просто хочет узнать информацию"""
    query = update.callback_query
    await query.answer()

    food_data = context.user_data.get("text_food_data", {})
    nutrition = food_data.get("nutrition", {})
    dish_name = food_data.get("dish_name", "блюдо")

    text = (
        f"✅ <b>Понял!</b>\n\n"
        f"Информация о <b>{dish_name}</b> сохранена. "
        f"Если захочешь добавить в дневник - просто отправь фото или напиши название!"
    )

    # Очищаем данные
    context.user_data.pop("text_food_data", None)

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=main_menu_keyboard()
    )


async def handle_text_food_meal_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора типа приёма пищи для текстовой еды"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    
    try:
        # Извлекаем тип приёма пищи
        meal_type_str = query.data.replace("meal_type_", "")
        meal_type = MealType(meal_type_str)

        food_data = context.user_data.get("text_food_data", {})
        
        if not food_data:
            await query.edit_message_text(
                "❌ Данные о еде не найдены",
                reply_markup=back_to_menu_keyboard()
            )
            return

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
                return

            nutrition = food_data.get("nutrition", {})
            
            # Создаём запись о приёме пищи
            meal = Meal(
                user_id=db_user.id,
                meal_type=meal_type,
                date=date.today(),
                name=food_data.get("dish_name", "Блюдо"),
                portion_size_grams=food_data.get("weight_grams", 0),
                calories=nutrition.get("calories", 0),
                proteins=nutrition.get("proteins", 0),
                fats=nutrition.get("fats", 0),
                carbs=nutrition.get("carbs", 0)
            )

            session.add(meal)
            await session.commit()

            meal_type_names = {
                "breakfast": "Завтрак",
                "lunch": "Обед",
                "dinner": "Ужин",
                "snack": "Перекус"
            }

            text = (
                f"✅ <b>Добавлено в дневник!</b>\n\n"
                f"🍽 {food_data.get('dish_name', 'Блюдо')}\n"
                f"🕐 {meal_type_names.get(meal_type_str, meal_type_str)}\n\n"
                f"📊 <b>Порция:</b> {food_data.get('weight_grams', 0)}г\n"
                f"🔥 <b>Калории:</b> {nutrition.get('calories', 0)} ккал\n"
                f"🥩 Белки: {nutrition.get('proteins', 0)}г\n"
                f"🥑 Жиры: {nutrition.get('fats', 0)}г\n"
                f"🍞 Углеводы: {nutrition.get('carbs', 0)}г"
            )

            # Очищаем данные
            context.user_data.pop("text_food_data", None)

            await query.edit_message_text(
                text,
                parse_mode='HTML',
                reply_markup=main_menu_keyboard()
            )

            logger.info(f"Text food added to diary for user {user.id}, meal_id: {meal.id}")

    except Exception as e:
        logger.error("Error in handle_text_food_meal_type for user {}: {}", user.id, repr(e))
        await query.edit_message_text(
            "❌ Ошибка при добавлении в дневник",
            reply_markup=back_to_menu_keyboard()
        )
