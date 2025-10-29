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

ФОРМАТ ОТВЕТА (текстом, не JSON):
🍽 **Рекомендую тебе:**

**1. [Название блюда]**
~ [Примерные калории] ккал | Б: [белки]г | Ж: [жиры]г | У: [углеводы]г

💡 [Короткое объяснение почему это подходит]

**2. [Название блюда]**
~ [Примерные калории] ккал | Б: [белки]г | Ж: [жиры]г | У: [углеводы]г

💡 [Короткое объяснение]

**3. [Название блюда]** (опционально, если есть хороший третий вариант)
~ [Примерные калории] ккал | Б: [белки]г | Ж: [жиры]г | У: [углеводы]г

💡 [Короткое объяснение]

---
📊 [Общий совет с учетом текущего прогресса]

ВАЖНО:
- Используй дружелюбный тон
- Учитывай настроение пользователя
- Будь честным: если в меню нет хороших вариантов для текущего рациона, скажи об этом
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

            recommendations = response.content[0].text

            # Показываем рекомендации
            final_text = f"🍽 <b>Рекомендации для {meal_type_text}:</b>\n\n{recommendations}"

            await processing_msg.edit_text(
                final_text,
                parse_mode='HTML',
                reply_markup=main_menu_keyboard()
            )

            # Очищаем контекст
            context.user_data.pop("restaurant_menu_photo", None)
            context.user_data.pop("restaurant_mood", None)

            logger.info(f"Restaurant recommendations provided for user {user.id}")

            return ConversationHandler.END

    except Exception as e:
        logger.error(f"Error analyzing restaurant menu for user {user.id}: {e}", exc_info=True)

        await processing_msg.edit_text(
            "❌ Произошла ошибка при анализе меню.\n\n"
            "Пожалуйста, попробуй еще раз.",
            reply_markup=back_to_menu_keyboard()
        )

        return ConversationHandler.END


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
