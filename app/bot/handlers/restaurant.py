"""
Обработчики для функции 'Ресторан' - анализ меню и рекомендации
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger
import io
from datetime import datetime, date

from app.services.claude_ai import claude_service
from app.services.meal_service import MealService
from app.bot.keyboards import back_to_menu_keyboard, main_menu_keyboard
from app.bot.states import RestaurantStates
from app.models.user import User
from app.models.meal_plan import MealPlan, PlanPeriod
from app.db.session import async_session_maker
from sqlalchemy import select, and_


async def restaurant_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало функции 'Ресторан'"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🍽 <b>Функция 'Ресторан'</b>\n\n"
        "Я помогу тебе выбрать блюдо из меню ресторана, которое впишется в твой рацион!\n\n"
        "📸 <b>Отправь фото меню ресторана</b>, и я проанализирую его с учетом:\n"
        "• Твоего текущего рациона на сегодня\n"
        "• Твоих целей и предпочтений\n"
        "• Твоего настроения\n\n"
        "<i>Фото должно содержать название блюд и их описание.</i>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
        ])
    )

    return RestaurantStates.ASKING_MOOD


async def restaurant_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик фото меню ресторана"""
    user = update.effective_user

    logger.info(f"User {user.id} sent restaurant menu photo")

    # Сначала спрашиваем настроение
    mood_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍰 Хочется сладкого", callback_data="mood_sweet")],
        [InlineKeyboardButton("🥩 Хочется сытного/жирного", callback_data="mood_hearty")],
        [InlineKeyboardButton("🥗 Хочется легкого/растительного", callback_data="mood_light")],
        [InlineKeyboardButton("🌶 Хочется острого", callback_data="mood_spicy")],
        [InlineKeyboardButton("🧘 Не важно, главное здоровое", callback_data="mood_healthy")],
        [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
    ])

    # Сохраняем фото в контексте
    photo = update.message.photo[-1]
    context.user_data["restaurant_menu_photo"] = photo.file_id

    await update.message.reply_text(
        "📸 Отлично! Фото меню получено.\n\n"
        "😊 <b>Какое у тебя настроение? Чего хочется?</b>",
        parse_mode='HTML',
        reply_markup=mood_keyboard
    )

    return RestaurantStates.ASKING_MEAL_TIME


async def handle_mood_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора настроения"""
    query = update.callback_query
    await query.answer()

    mood_map = {
        "mood_sweet": "🍰 сладкого",
        "mood_hearty": "🥩 сытного и жирного",
        "mood_light": "🥗 легкого и растительного",
        "mood_spicy": "🌶 острого",
        "mood_healthy": "🧘 здорового питания"
    }

    mood = query.data
    mood_text = mood_map.get(mood, "здорового питания")

    # Сохраняем настроение
    context.user_data["restaurant_mood"] = mood_text

    # Спрашиваем к какому приему пищи
    meal_time_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌅 Завтрак", callback_data="restaurant_meal_breakfast")],
        [InlineKeyboardButton("🌞 Обед", callback_data="restaurant_meal_lunch")],
        [InlineKeyboardButton("🌙 Ужин", callback_data="restaurant_meal_dinner")],
        [InlineKeyboardButton("🍎 Перекус", callback_data="restaurant_meal_snack")],
        [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
    ])

    await query.edit_message_text(
        f"✅ Понял, хочется {mood_text}!\n\n"
        "⏰ <b>К какому приему пищи это относится?</b>",
        parse_mode='HTML',
        reply_markup=meal_time_keyboard
    )

    return RestaurantStates.ANALYZING_MENU


async def analyze_menu_and_recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализ меню и генерация рекомендаций"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    meal_type_map = {
        "restaurant_meal_breakfast": "завтрак",
        "restaurant_meal_lunch": "обед",
        "restaurant_meal_dinner": "ужин",
        "restaurant_meal_snack": "перекус"
    }

    meal_type_text = meal_type_map.get(query.data, "прием пищи")

    # Показываем прогресс
    processing_msg = await query.edit_message_text(
        "🔍 Анализирую меню...\n\n"
        "Это может занять до минуты. Подожди, пожалуйста."
    )

    try:
        async with async_session_maker() as session:
            # Получаем пользователя
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

            # Получаем текущий прогресс за день
            progress = await MealService.get_nutrition_progress(
                session=session,
                user_id=db_user.id,
                target_date=date.today()
            )

            # Получаем активный план питания
            active_plan_result = await session.execute(
                select(MealPlan).where(and_(
                    MealPlan.user_id == db_user.telegram_id,
                    MealPlan.is_active == 1
                ))
            )
            active_plan = active_plan_result.scalar_one_or_none()

            # Скачиваем фото меню
            photo_file_id = context.user_data.get("restaurant_menu_photo")
            if not photo_file_id:
                await processing_msg.edit_text(
                    "❌ Фото меню не найдено. Попробуй еще раз.",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            file = await context.bot.get_file(photo_file_id)
            image_bytes_io = io.BytesIO()
            await file.download_to_memory(image_bytes_io)
            image_bytes = image_bytes_io.getvalue()

            # Формируем промпт для AI
            mood = context.user_data.get("restaurant_mood", "здорового питания")

            current = progress["current"]
            target = progress["target"]
            remaining = progress["remaining"]

            prompt = f"""Проанализируй меню ресторана на фото и порекомендуй 2-3 блюда для пользователя.

ВАЖНАЯ ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:
- Тип приема пищи: {meal_type_text}
- Настроение/желание: {mood}
- Целевые калории на день: {target['calories']} ккал
- Уже потреблено сегодня: {current['calories']} ккал
- Осталось на сегодня: {remaining['calories']} ккал
- Осталось белков: {remaining['proteins']:.0f}г
- Осталось жиров: {remaining['fats']:.0f}г
- Осталось углеводов: {remaining['carbs']:.0f}г
- Тип диеты: {db_user.diet_type.value if db_user.diet_type else 'всеядный'}
- Аллергии: {', '.join(db_user.allergies) if db_user.allergies else 'нет'}

ЗАДАЧА:
1. Изучи меню на фото и извлеки названия блюд
2. Выбери 2-3 блюда, которые:
   - Соответствуют настроению/желанию пользователя ({mood})
   - Подходят для {meal_type_text}
   - Впишутся в оставшийся дневной лимит калорий
   - Помогут достичь баланса БЖУ
   - Соответствуют типу диеты и не содержат аллергены
3. Для каждого блюда укажи:
   - Название блюда (как в меню)
   - Примерные КБЖУ
   - Почему это подходит (с учетом настроения и рациона)

ФОРМАТ ОТВЕТА - строго JSON:
{{
  "recommendations": [
    {{
      "number": 1,
      "name": "Название блюда",
      "calories": 450,
      "proteins": 30,
      "fats": 15,
      "carbs": 45,
      "explanation": "Короткое объяснение почему подходит"
    }},
    {{
      "number": 2,
      "name": "Название блюда",
      "calories": 350,
      "proteins": 25,
      "fats": 12,
      "carbs": 35,
      "explanation": "Короткое объяснение"
    }},
    {{
      "number": 3,
      "name": "Название блюда (опционально)",
      "calories": 400,
      "proteins": 28,
      "fats": 14,
      "carbs": 40,
      "explanation": "Короткое объяснение"
    }}
  ],
  "general_advice": "Общий совет с учетом текущего прогресса"
}}

ВАЖНО:
- Верни только валидный JSON, без markdown форматирования
- Минимум 2 рекомендации, максимум 3
- Используй дружелюбный тон в объяснениях
- Учитывай настроение пользователя
- Будь честным: если в меню нет хороших вариантов, скажи об этом в general_advice
- Не ставь диагнозы, используй фразы "может помочь", "поможет сбалансировать"
"""

            # Отправляем запрос к Claude
            from anthropic import AsyncAnthropic
            from app.config import settings

            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            import base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            response = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=2000,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ]
            )

            recommendations_text = response.content[0].text

            # Парсим JSON ответ
            import json
            import re

            # Пытаемся извлечь JSON из ответа (на случай если Claude добавил markdown)
            json_match = re.search(r'\{[\s\S]*\}', recommendations_text)
            if json_match:
                recommendations_json = json.loads(json_match.group())
            else:
                recommendations_json = json.loads(recommendations_text)

            # Формируем текст для пользователя
            final_text = f"🍽 <b>Рекомендации для {meal_type_text}:</b>\n\n"

            for rec in recommendations_json.get("recommendations", []):
                final_text += (
                    f"<b>{rec['number']}. {rec['name']}</b>\n"
                    f"~ {rec['calories']} ккал | Б: {rec['proteins']}г | "
                    f"Ж: {rec['fats']}г | У: {rec['carbs']}г\n\n"
                    f"💡 {rec['explanation']}\n\n"
                )

            if recommendations_json.get("general_advice"):
                final_text += f"---\n📊 {recommendations_json['general_advice']}"

            await processing_msg.edit_text(
                final_text,
                parse_mode='HTML',
                reply_markup=main_menu_keyboard()
            )

            # Сохраняем рекомендации для последующего использования
            context.user_data["restaurant_recommendations"] = recommendations_json
            context.user_data["restaurant_meal_type"] = meal_type
            context.user_data["restaurant_message_id"] = processing_msg.message_id
            context.user_data["restaurant_chat_id"] = query.message.chat_id

            # Планируем отложенное уточнение через 5 минут (300 секунд)
            context.job_queue.run_once(
                restaurant_followup_callback,
                when=300,
                data={
                    "chat_id": query.message.chat_id,
                    "user_id": user.id,
                    "telegram_id": user.id
                },
                name=f"restaurant_followup_{user.id}"
            )

            logger.info(f"Restaurant recommendations provided for user {user.id}, followup scheduled in 5 minutes")

            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error analyzing restaurant menu for user {user.id}: {e}", exc_info=True)

        await processing_msg.edit_text(
            "❌ Произошла ошибка при анализе меню.\n\n"
            "Пожалуйста, попробуй еще раз.",
            reply_markup=back_to_menu_keyboard()
        )

        return ConversationHandler.END


async def restaurant_followup_callback(context: ContextTypes.DEFAULT_TYPE):
    """Отложенный callback для уточнения использования рекомендаций (через 5 минут)"""
    job_data = context.job.data
    chat_id = job_data.get("chat_id")
    telegram_id = job_data.get("telegram_id")

    # Проверяем есть ли сохраненные рекомендации
    if "restaurant_recommendations" not in context.application.user_data.get(telegram_id, {}):
        logger.info(f"No restaurant recommendations found for user {telegram_id}, skipping followup")
        return

    # Создаем кнопки для ответа
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = [
        [InlineKeyboardButton("✅ Да, воспользовался", callback_data="restaurant_used_yes")],
        [InlineKeyboardButton("❌ Нет, выбрал другое", callback_data="restaurant_used_no")]
    ]

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "👋 Привет!\n\n"
            "Я тут подумал... Воспользовался ли ты моими рекомендациями из ресторана?\n"
            "Если да, я могу добавить выбранное блюдо в твой дневник питания!"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    logger.info(f"Restaurant followup sent to user {telegram_id}")


async def handle_restaurant_used_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ответа пользователя о том, воспользовался ли он рекомендациями"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    response = query.data.replace("restaurant_used_", "")

    if response == "no":
        # Пользователь выбрал что-то другое
        await query.edit_message_text(
            "Понял! Главное, чтобы было вкусно и полезно 😊\n\n"
            "Если хочешь добавить то, что ты съел, просто отправь фото блюда через 📸 Добавить еду.",
            reply_markup=main_menu_keyboard()
        )

        # Очищаем сохраненные рекомендации
        context.user_data.pop("restaurant_recommendations", None)
        context.user_data.pop("restaurant_meal_type", None)

        return

    # Пользователь воспользовался рекомендациями
    recommendations = context.user_data.get("restaurant_recommendations", {}).get("recommendations", [])

    if not recommendations:
        await query.edit_message_text(
            "❌ К сожалению, я не нашел сохраненные рекомендации.\n\n"
            "Но ты можешь добавить еду вручную через 📸 Добавить еду!",
            reply_markup=main_menu_keyboard()
        )
        return

    # Показываем варианты для выбора
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    text = "Отлично! Что именно ты выбрал?\n\n"

    keyboard = []
    for rec in recommendations:
        # Формируем краткое описание для кнопки
        button_text = f"{rec['number']}. {rec['name'][:30]}..."
        # Детальное описание в тексте
        text += (
            f"<b>{rec['number']}. {rec['name']}</b>\n"
            f"~ {rec['calories']} ккал | Б: {rec['proteins']}г | "
            f"Ж: {rec['fats']}г | У: {rec['carbs']}г\n\n"
        )
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"restaurant_dish_{rec['number']}")])

    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])

    await query.edit_message_text(
        text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_restaurant_dish_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавление выбранного блюда из ресторана в дневник"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Получаем номер выбранного блюда
    dish_number = int(query.data.replace("restaurant_dish_", ""))

    # Получаем рекомендации
    recommendations = context.user_data.get("restaurant_recommendations", {}).get("recommendations", [])
    meal_type = context.user_data.get("restaurant_meal_type")

    # Находим выбранное блюдо
    selected_dish = None
    for rec in recommendations:
        if rec["number"] == dish_number:
            selected_dish = rec
            break

    if not selected_dish or not meal_type:
        await query.edit_message_text(
            "❌ Не удалось найти информацию о блюде.\n\n"
            "Попробуй добавить еду вручную через 📸 Добавить еду!",
            reply_markup=main_menu_keyboard()
        )
        return

    # Добавляем блюдо в дневник
    from datetime import date, datetime
    from app.models.user import User
    from app.services.meal_service import MealService
    from sqlalchemy import select

    await query.edit_message_text("⏳ Добавляю блюдо в дневник...", parse_mode='HTML')

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
                    reply_markup=main_menu_keyboard()
                )
                return

            # Формируем данные о еде
            foods_data = [{
                "name": selected_dish["name"],
                "portion_description": "1 порция",
                "calories": selected_dish["calories"],
                "proteins": selected_dish["proteins"],
                "fats": selected_dish["fats"],
                "carbs": selected_dish["carbs"]
            }]

            # Создаем прием пищи
            meal = await MealService.create_meal_with_foods(
                session=session,
                user_id=db_user.id,
                meal_type=meal_type,
                meal_date=date.today(),
                meal_time=datetime.now(),
                foods_data=foods_data
            )

            # Получаем прогресс за день
            progress = await MealService.get_nutrition_progress(
                session=session,
                user_id=db_user.id,
                target_date=date.today()
            )

            from app.models.meal import MealType
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
                f"🍽 *{selected_dish['name']}*\n"
                f"~ {selected_dish['calories']} ккал | Б: {selected_dish['proteins']}г | "
                f"Ж: {selected_dish['fats']}г | У: {selected_dish['carbs']}г\n\n"
                f"📊 *Прогресс за сегодня:*\n"
                f"🔥 Калории: {current['calories']}/{target['calories']} ккал "
                f"(осталось {remaining['calories']})\n"
                f"🥩 Белки: {current['proteins']:.0f}/{target['proteins']}г\n"
                f"🧈 Жиры: {current['fats']:.0f}/{target['fats']}г\n"
                f"🍞 Углеводы: {current['carbs']:.0f}/{target['carbs']}г\n\n"
            )

            # Предупреждения
            if current['calories'] > target['calories']:
                success_text += "⚠️ Ты превысил дневную норму калорий\n"
            elif remaining['calories'] < 300:
                success_text += f"💡 Осталось всего {remaining['calories']} ккал на сегодня\n"

            success_text += "\n🎉 Приятного аппетита!"

            await query.edit_message_text(
                success_text,
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )

            # Очищаем контекст
            context.user_data.pop("restaurant_recommendations", None)
            context.user_data.pop("restaurant_meal_type", None)

            logger.info(f"Restaurant dish added to diary for user {user.id}, meal_id: {meal.id}")

    except Exception as e:
        logger.error(f"Error adding restaurant dish for user {user.id}: {e}", exc_info=True)

        await query.edit_message_text(
            "❌ Ошибка при добавлении в дневник.\nПопробуй позже.",
            reply_markup=back_to_menu_keyboard()
        )


async def cancel_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена функции 'Ресторан'"""
    query = update.callback_query
    await query.answer()

    context.user_data.pop("restaurant_menu_photo", None)
    context.user_data.pop("restaurant_mood", None)

    await query.edit_message_text(
        "❌ Функция 'Ресторан' отменена",
        reply_markup=main_menu_keyboard()
    )

    return ConversationHandler.END
