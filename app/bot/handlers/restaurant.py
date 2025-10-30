"""
Обработчики для функции 'Ресторан' - анализ меню и рекомендации
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import TimedOut, NetworkError, RetryAfter
from loguru import logger
import io
import json
import re
import asyncio
from datetime import datetime, date
from difflib import SequenceMatcher

from app.services.claude_ai import claude_service
from app.services.meal_service import MealService
from app.bot.keyboards import back_to_menu_keyboard, main_menu_keyboard
from app.bot.states import RestaurantStates
from app.models.user import User
from app.models.meal_plan import MealPlan, PlanPeriod
from app.db.session import async_session_maker
from sqlalchemy import select, and_


def safe_parse_json(text: str, context_name: str = "response") -> dict:
    """
    Надёжный парсинг JSON с множественными стратегиями очистки

    Args:
        text: Текст для парсинга
        context_name: Название контекста для логирования

    Returns:
        Распарсенный JSON как словарь

    Raises:
        json.JSONDecodeError: Если все стратегии парсинга неудачны
    """

    # Стратегия 1: Прямой парсинг
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Стратегия 2: Извлечение JSON из markdown блоков
    # Ищем ```json ... ``` или ``` ... ```
    code_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # Стратегия 3: Извлечение первого JSON объекта
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        json_str = json_match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Стратегия 4: Очистка trailing commas
            # Удаляем запятые перед закрывающими скобками
            cleaned = re.sub(r',(\s*[}\]])', r'\1', json_str)
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                pass

            # Стратегия 5: Исправление неэкранированных переносов строк внутри строковых значений
            # Заменяем неэкранированные \n внутри строк на пробелы
            try:
                # Удаляем все переносы строк и возвраты каретки внутри JSON
                # Это безопасно, т.к. они не должны быть в JSON без экранирования
                fixed = cleaned.replace('\n', ' ').replace('\r', ' ')
                # Удаляем множественные пробелы
                fixed = re.sub(r'\s+', ' ', fixed)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            # Стратегия 6: Усечение обрезанного JSON
            # Если JSON обрезан на середине (достигнут max_tokens),
            # найдём последний полный объект и закроем структуру
            try:
                # Ищем последнее вхождение закрывающей фигурной скобки объекта
                # за которой может быть запятая или пробелы
                last_complete = fixed.rfind('}')
                if last_complete > 0:
                    # Обрезаем до последнего полного объекта
                    truncated = fixed[:last_complete + 1]

                    # Подсчитываем открытые структуры после обрезания
                    open_braces = truncated.count('{') - truncated.count('}')
                    open_brackets = truncated.count('[') - truncated.count(']')

                    # Закрываем все открытые массивы и объекты
                    truncated += ']' * open_brackets
                    truncated += '}' * open_braces

                    logger.warning(
                        f"JSON appears truncated in {context_name}. "
                        f"Attempting to recover by truncating to last complete object. "
                        f"Original length: {len(fixed)}, Truncated to: {len(truncated)}"
                    )

                    return json.loads(truncated)
            except json.JSONDecodeError:
                # Стратегия 7: Логируем проблемный JSON и выбрасываем ошибку
                logger.error(
                    f"Failed to parse JSON in {context_name}. "
                    f"Original error: {e}. "
                    f"Tried 6 different strategies, all failed. "
                    f"Problematic JSON - first 500 chars: {json_str[:500]}"
                )
                logger.error(
                    f"Problematic JSON - last 500 chars: {json_str[-500:]}"
                )
                raise

    # Если ничего не сработало
    logger.error(f"No JSON found in {context_name}. Text (first 500 chars): {text[:500]}")
    raise json.JSONDecodeError(
        f"No valid JSON found in {context_name}",
        text,
        0
    )


def validate_recommendations_against_menu(recommendations: list, menu_dishes: list, similarity_threshold: float = 0.85) -> dict:
    """
    Валидирует рекомендации AI против реального меню ресторана.

    Args:
        recommendations: Список рекомендованных блюд от AI
        menu_dishes: Список блюд извлеченных из меню
        similarity_threshold: Порог схожести для нечеткого сравнения (0.0-1.0)

    Returns:
        dict с ключами:
            - is_valid: bool - все ли рекомендации валидны
            - invalid_dishes: list - список названий невалидных блюд
            - details: list - детальная информация о каждой проверке
    """
    menu_dish_names = [dish["name"].lower().strip() for dish in menu_dishes]

    invalid_dishes = []
    validation_details = []

    for rec in recommendations:
        rec_name = rec.get("name", "").lower().strip()

        # Проверяем точное совпадение
        exact_match = rec_name in menu_dish_names

        if exact_match:
            validation_details.append({
                "recommended": rec.get("name"),
                "status": "valid",
                "match_type": "exact",
                "confidence": 1.0
            })
            continue

        # Проверяем нечеткое совпадение (для учета опечаток и вариаций)
        best_match = None
        best_similarity = 0.0

        for menu_dish_name in menu_dish_names:
            similarity = SequenceMatcher(None, rec_name, menu_dish_name).ratio()
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = menu_dish_name

        if best_similarity >= similarity_threshold:
            validation_details.append({
                "recommended": rec.get("name"),
                "status": "valid",
                "match_type": "fuzzy",
                "matched_with": best_match,
                "confidence": best_similarity
            })
        else:
            invalid_dishes.append(rec.get("name"))
            validation_details.append({
                "recommended": rec.get("name"),
                "status": "invalid",
                "best_match": best_match if best_match else None,
                "best_similarity": best_similarity
            })

    is_valid = len(invalid_dishes) == 0

    return {
        "is_valid": is_valid,
        "invalid_dishes": invalid_dishes,
        "details": validation_details
    }


async def send_with_retry(coro, max_retries=4, initial_delay=2.0):
    """
    Выполняет Telegram API вызов с повторными попытками при ошибках сети

    Args:
        coro: Корутина для выполнения (например, message.reply_text(...))
        max_retries: Максимальное количество попыток (default: 4)
        initial_delay: Начальная задержка в секундах (default: 2.0)

    Returns:
        Результат выполнения корутины

    Raises:
        Последнее исключение, если все попытки неудачны
    """
    last_exception = None
    delay = initial_delay

    for attempt in range(max_retries):
        try:
            return await coro
        except (TimedOut, NetworkError) as e:
            last_exception = e
            if attempt < max_retries - 1:  # Не ждём после последней попытки
                logger.warning("Network error on attempt {}/{}: {}. Retrying in {}s...", attempt + 1, max_retries, repr(e), delay)
                await asyncio.sleep(delay)
                delay *= 2  # Экспоненциальная задержка (2s, 4s, 8s, 16s)
            else:
                logger.error("All {} attempts failed. Last error: {}", max_retries, repr(e))
        except RetryAfter as e:
            # Telegram просит подождать определённое время
            logger.warning(f"Rate limited. Waiting {e.retry_after}s as requested by Telegram...")
            await asyncio.sleep(e.retry_after)
            return await coro  # Повторяем после ожидания
        except Exception as e:
            # Другие ошибки не повторяем
            logger.error("Non-retryable error: {}: {}", type(e).__name__, repr(e))
            raise

    # Если все попытки неудачны, выбрасываем последнее исключение
    raise last_exception


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

    # Отправляем ответ с повторными попытками при ошибках сети
    await send_with_retry(
        update.message.reply_text(
            "📸 Отлично! Фото меню получено.\n\n"
            "😊 <b>Какое у тебя настроение? Чего хочется?</b>",
            parse_mode='HTML',
            reply_markup=mood_keyboard
        )
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

    # Извлекаем meal_type из callback_data (например "restaurant_meal_lunch" -> "lunch")
    meal_type = query.data.replace("restaurant_meal_", "")

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

            # Инициализируем Claude API клиент
            from anthropic import AsyncAnthropic
            from app.config import settings
            import base64

            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            # ЭТАП 1: Сначала извлекаем список всех блюд из меню
            extraction_prompt = """Проанализируй фото меню ресторана и извлеки СПИСОК ВСЕХ блюд.

ЗАДАЧА:
Просто перечисли все блюда которые видишь в меню с их кратким описанием (если есть).

ФОРМАТ ОТВЕТА - строго JSON:
{
  "dishes": [
    {"name": "Название блюда 1", "description": "краткое описание из меню если есть"},
    {"name": "Название блюда 2", "description": "краткое описание"},
    {"name": "Название блюда 3", "description": "краткое описание"}
  ]
}

ВАЖНО:
- Извлеки ВСЕ блюда из меню
- Используй точные названия как в меню
- Если нет описания - поставь пустую строку
- Верни только валидный JSON"""

            # Запрос на извлечение блюд
            # max_tokens увеличен до 4000 для больших меню
            extraction_response = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=4000,
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
                                "text": extraction_prompt
                            }
                        ]
                    }
                ]
            )

            extraction_text = extraction_response.content[0].text

            # Парсим список блюд с помощью надёжного парсера
            logger.info(f"Parsing dish extraction response (length: {len(extraction_text)})")
            dishes_data = safe_parse_json(extraction_text, context_name="dish extraction")

            dish_names = [d["name"] for d in dishes_data.get("dishes", [])]

            logger.info(f"Extracted {len(dish_names)} dishes from menu")

            # ЭТАП 2: Ищем реальные данные о пищевой ценности в интернете
            from app.services.web_search_service import WebSearchService

            await send_with_retry(
                processing_msg.edit_text(
                    "🔍 Ищу данные о пищевой ценности блюд в интернете...\n\n"
                    "Это займет несколько секунд."
                )
            )

            web_search_results = await WebSearchService.search_multiple_dishes(dish_names[:10])  # Ограничиваем первыми 10 блюдами
            web_data_text = WebSearchService.format_search_results_for_prompt(web_search_results)

            logger.info(f"Web search completed for {len(web_search_results)} dishes")

            # ЭТАП 3: Запрашиваем рекомендации с валидацией и повторными попытками
            max_validation_attempts = 3
            recommendations_json = None
            validation_result = None

            for attempt in range(max_validation_attempts):
                # Формируем промпт с учетом предыдущих ошибок
                correction_note = ""
                if attempt > 0 and validation_result:
                    # Создаем список доступных блюд
                    available_dishes = "\n".join([f"  • {dish['name']}" for dish in dishes_data.get("dishes", [])])
                    correction_note = f"""
🚫 КРИТИЧЕСКАЯ ОШИБКА! В предыдущем ответе ты рекомендовал блюда, которых НЕТ в меню:
{', '.join([f'"{dish}"' for dish in validation_result['invalid_dishes']])}

Это НЕДОПУСТИМО! Ты ОБЯЗАН выбирать ТОЛЬКО из этого списка:
{available_dishes}

Перечитай список выше и выбери блюда СТРОГО из него. НЕ придумывай новые названия!
"""

                # Формируем список названий блюд для явного указания в промпте
                dish_names_list = "\n".join([f"• {dish['name']}" for dish in dishes_data.get("dishes", [])])

                prompt = f"""{correction_note}
На основе меню ресторана порекомендуй 2-3 блюда для пользователя.

⚠️ СПИСОК БЛЮД КОТОРЫЕ ЕСТЬ В МЕНЮ (выбирай ТОЛЬКО из этого списка):
{dish_names_list}

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

БЛЮДА В МЕНЮ (детальная информация):
{json.dumps(dishes_data, ensure_ascii=False, indent=2)}

{web_data_text}

ЗАДАЧА:
1. Выбери 2-3 блюда СТРОГО ИЗ СПИСКА БЛЮД ВЫШЕ, которые:
   - Соответствуют настроению/желанию пользователя ({mood})
   - Подходят для {meal_type_text}
   - Впишутся в оставшийся дневной лимит калорий
   - Помогут достичь баланса БЖУ
   - Соответствуют типу диеты и не содержат аллергены

2. Для каждого блюда укажи:
   - Название блюда ТОЧНО КАК В МЕНЮ (копируй из списка выше!)
   - КБЖУ (ИСПОЛЬЗУЙ РЕАЛЬНЫЕ ДАННЫЕ из интернета выше! Если данных нет - дай приблизительную оценку с пометкой)
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
      "data_source": "web_search" или "estimate",
      "explanation": "Короткое объяснение почему подходит"
    }},
    {{
      "number": 2,
      "name": "Название блюда",
      "calories": 350,
      "proteins": 25,
      "fats": 12,
      "carbs": 35,
      "data_source": "web_search" или "estimate",
      "explanation": "Короткое объяснение"
    }},
    {{
      "number": 3,
      "name": "Название блюда (опционально)",
      "calories": 400,
      "proteins": 28,
      "fats": 14,
      "carbs": 40,
      "data_source": "web_search" или "estimate",
      "explanation": "Короткое объяснение"
    }}
  ],
  "general_advice": "Общий совет с учетом текущего прогресса"
}}

КРИТИЧЕСКИ ВАЖНО:
- КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО придумывать или добавлять блюда, которых НЕТ в списке выше!
- РЕКОМЕНДУЙ ТОЛЬКО блюда из раздела "БЛЮДА В МЕНЮ" выше
- ИСПОЛЬЗУЙ ТОЧНЫЕ названия блюд - копируй их из списка dishes выше
- ИСПОЛЬЗУЙ РЕАЛЬНЫЕ ДАННЫЕ из веб-поиска выше! Не придумывай цифры!
- Если для блюда найдены данные - обязательно используй их
- Если данных нет - укажи data_source: "estimate" и дай приблизительную оценку
- Верни только валидный JSON, без markdown форматирования
- Минимум 2 рекомендации, максимум 3
- Используй дружелюбный тон в объяснениях
- Учитывай настроение пользователя
"""

                # Отправляем запрос к Claude на финальные рекомендации
                response = await client.messages.create(
                    model=settings.CLAUDE_MODEL,
                    max_tokens=2000,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )

                recommendations_text = response.content[0].text

                # Парсим JSON ответ с помощью надёжного парсера
                logger.info(f"Parsing recommendations response, attempt {attempt + 1} (length: {len(recommendations_text)})")
                recommendations_json = safe_parse_json(recommendations_text, context_name="recommendations")

                # ВАЛИДАЦИЯ: проверяем что все рекомендованные блюда есть в меню
                validation_result = validate_recommendations_against_menu(
                    recommendations=recommendations_json.get("recommendations", []),
                    menu_dishes=dishes_data.get("dishes", []),
                    similarity_threshold=0.92  # Повышен порог до 92% для строгости
                )

                logger.info(
                    f"Validation attempt {attempt + 1}: "
                    f"valid={validation_result['is_valid']}, "
                    f"invalid_dishes={validation_result['invalid_dishes']}"
                )

                # Если валидация успешна - выходим из цикла
                if validation_result['is_valid']:
                    logger.info(f"✅ All recommendations validated successfully on attempt {attempt + 1}")
                    break
                else:
                    logger.warning(
                        f"❌ Validation failed on attempt {attempt + 1}. "
                        f"Invalid dishes: {validation_result['invalid_dishes']}"
                    )

                    # Если это последняя попытка - логируем детали
                    if attempt == max_validation_attempts - 1:
                        logger.error(
                            f"All {max_validation_attempts} validation attempts failed. "
                            f"Details: {json.dumps(validation_result['details'], ensure_ascii=False, indent=2)}"
                        )

            # Если после всех попыток валидация не прошла, используем последний результат
            # но логируем предупреждение
            if not validation_result['is_valid']:
                logger.error(
                    f"⚠️ Proceeding with invalid recommendations after {max_validation_attempts} attempts. "
                    f"User {user.id} may receive dishes not in menu!"
                )

            # Формируем текст для пользователя
            final_text = f"🍽 <b>Рекомендации для {meal_type_text}:</b>\n\n"

            for rec in recommendations_json.get("recommendations", []):
                # Добавляем индикатор источника данных
                data_source_indicator = ""
                if rec.get('data_source') == 'web_search':
                    data_source_indicator = " ✅"  # Галочка = данные из интернета
                elif rec.get('data_source') == 'estimate':
                    data_source_indicator = " ⚠️"  # Предупреждение = оценка

                final_text += (
                    f"<b>{rec['number']}. {rec['name']}</b>{data_source_indicator}\n"
                    f"~ {rec['calories']} ккал | Б: {rec['proteins']}г | "
                    f"Ж: {rec['fats']}г | У: {rec['carbs']}г\n\n"
                    f"💡 {rec['explanation']}\n\n"
                )

            if recommendations_json.get("general_advice"):
                final_text += f"---\n📊 {recommendations_json['general_advice']}\n\n"

            # Добавляем легенду
            final_text += "<i>✅ = данные из интернета | ⚠️ = приблизительная оценка</i>\n\n"
            final_text += "👇 <b>Выбери действие:</b>"

            # Создаем кнопки для выбора блюда
            keyboard = []
            for rec in recommendations_json.get("recommendations", []):
                # Обрезаем название если слишком длинное
                dish_name = rec['name'][:35] + "..." if len(rec['name']) > 35 else rec['name']
                button_text = f"{rec['number']}. {dish_name}"
                # Используем restaurant_dish_ чтобы использовать существующий обработчик
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"restaurant_dish_{rec['number']}")])

            # Кнопки дополнительных действий
            keyboard.append([InlineKeyboardButton("🔄 Поищи ещё варианты", callback_data="restaurant_search_more")])
            keyboard.append([InlineKeyboardButton("✍️ Выберу сам", callback_data="restaurant_manual_input")])
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])

            await send_with_retry(
                processing_msg.edit_text(
                    final_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            )

            # Сохраняем рекомендации и данные для последующего использования
            context.user_data["restaurant_recommendations"] = recommendations_json
            context.user_data["restaurant_meal_type"] = meal_type
            context.user_data["restaurant_dishes_data"] = dishes_data  # Сохраняем список блюд из меню
            context.user_data["restaurant_mood"] = mood
            context.user_data["restaurant_web_search_results"] = web_search_results

            logger.info(f"Restaurant recommendations provided for user {user.id} with selection buttons")

            # НЕ завершаем разговор, ждем выбора пользователя
            return RestaurantStates.ANALYZING_MENU

    except json.JSONDecodeError as e:
        logger.error(
            f"JSON parsing error for user {user.id}: {e}. "
            f"This usually means Claude AI returned invalid JSON format.",
            exc_info=True
        )

        try:
            await send_with_retry(
                processing_msg.edit_text(
                    "❌ Не удалось обработать ответ AI.\n\n"
                    "Это редкая ошибка форматирования данных. "
                    "Пожалуйста, попробуй отправить фото меню ещё раз.\n\n"
                    "<i>Если ошибка повторяется, попробуй сфотографировать меню с другого ракурса.</i>",
                    parse_mode='HTML',
                    reply_markup=back_to_menu_keyboard()
                )
            )
        except Exception as send_error:
            logger.error(f"Failed to send JSON error message to user {user.id}: {send_error}")

        return ConversationHandler.END

    except Exception as e:
        logger.error("Error analyzing restaurant menu for user {}: {}", user.id, repr(e), exc_info=True)

        try:
            await send_with_retry(
                processing_msg.edit_text(
                    "❌ Произошла ошибка при анализе меню.\n\n"
                    "Пожалуйста, попробуй еще раз.",
                    reply_markup=back_to_menu_keyboard()
                )
            )
        except Exception as send_error:
            logger.error(f"Failed to send error message to user {user.id}: {send_error}")

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
    keyboard = [
        [InlineKeyboardButton("✅ Да, воспользовался", callback_data="restaurant_used_yes")],
        [InlineKeyboardButton("❌ Нет, выбрал другое", callback_data="restaurant_used_no")]
    ]

    try:
        await send_with_retry(
            context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "👋 Привет!\n\n"
                    "Я тут подумал... Воспользовался ли ты моими рекомендациями из ресторана?\n"
                    "Если да, я могу добавить выбранное блюдо в твой дневник питания!"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        )
        logger.info(f"Restaurant followup sent to user {telegram_id}")
    except Exception as e:
        logger.error("Failed to send restaurant followup to user {}: {}", telegram_id, repr(e))


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
                "portion_size": 1,  # Одна порция
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
        logger.error("Error adding restaurant dish for user {}: {}", user.id, repr(e), exc_info=True)

        await query.edit_message_text(
            "❌ Ошибка при добавлении в дневник.\nПопробуй позже.",
            reply_markup=back_to_menu_keyboard()
        )


async def handle_restaurant_search_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повторный поиск рекомендаций блюд"""
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Получаем сохраненные данные
    dishes_data = context.user_data.get("restaurant_dishes_data")
    meal_type = context.user_data.get("restaurant_meal_type")
    mood = context.user_data.get("restaurant_mood")
    web_search_results = context.user_data.get("restaurant_web_search_results", [])

    if not dishes_data or not meal_type:
        await query.edit_message_text(
            "❌ Данные меню не найдены. Попробуй загрузить фото меню заново.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    # Показываем сообщение о поиске
    processing_msg = await query.edit_message_text(
        "🔍 Ищу другие подходящие варианты...\n\nПодожди немного."
    )

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await processing_msg.edit_text(
                    "❌ Пользователь не найден.",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Получаем прогресс
            progress = await MealService.get_nutrition_progress(
                session=session,
                user_id=db_user.id,
                target_date=date.today()
            )

            current = progress["current"]
            target = progress["target"]
            remaining = progress["remaining"]

            # Определяем meal_type_text
            meal_type_map = {
                "breakfast": "завтрак",
                "lunch": "обед",
                "dinner": "ужин",
                "snack": "перекус"
            }
            meal_type_text = meal_type_map.get(meal_type, "прием пищи")

            # Формируем промпт с просьбой найти ДРУГИЕ блюда
            from anthropic import AsyncAnthropic
            from app.config import settings
            from app.services.web_search_service import WebSearchService

            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            web_data_text = WebSearchService.format_search_results_for_prompt(web_search_results)

            # Получаем предыдущие рекомендации чтобы не повторяться
            previous_recs = context.user_data.get("restaurant_recommendations", {}).get("recommendations", [])
            previous_names = [rec.get("name", "") for rec in previous_recs]
            previous_note = f"\n\nВАЖНО: НЕ рекомендуй следующие блюда (они уже были предложены):\n{', '.join(previous_names)}" if previous_names else ""

            dish_names_list = "\n".join([f"• {dish['name']}" for dish in dishes_data.get("dishes", [])])

            prompt = f"""На основе меню ресторана порекомендуй 2-3 ДРУГИХ блюда для пользователя.
{previous_note}

⚠️ СПИСОК БЛЮД КОТОРЫЕ ЕСТЬ В МЕНЮ (выбирай ТОЛЬКО из этого списка):
{dish_names_list}

ВАЖНАЯ ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:
- Тип приема пищи: {meal_type_text}
- Настроение/желание: {mood}
- Целевые калории на день: {target['calories']} ккал
- Уже потреблено сегодня: {current['calories']} ккал
- Осталось на сегодня: {remaining['calories']} ккал
- Осталось белков: {remaining['proteins']:.0f}г
- Осталось жиров: {remaining['fats']:.0f}г
- Осталось углеводов: {remaining['carbs']:.0f}г

БЛЮДА В МЕНЮ (детальная информация):
{json.dumps(dishes_data, ensure_ascii=False, indent=2)}

{web_data_text}

ЗАДАЧА:
Выбери 2-3 ДРУГИХ блюда (не те что были предложены ранее!), которые:
- Соответствуют настроению/желанию ({mood})
- Подходят для {meal_type_text}
- Впишутся в оставшийся лимит калорий
- Помогут достичь баланса БЖУ

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
      "data_source": "web_search" или "estimate",
      "explanation": "Короткое объяснение"
    }}
  ],
  "general_advice": "Общий совет"
}}

КРИТИЧЕСКИ ВАЖНО:
- Выбирай ТОЛЬКО блюда из списка выше
- НЕ повторяй блюда которые уже были предложены
- Используй точные названия из меню
- Верни валидный JSON"""

            # Отправляем запрос к AI
            response = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            recommendations_text = response.content[0].text
            recommendations_json = safe_parse_json(recommendations_text, context_name="search_more_recommendations")

            # Валидация
            validation_result = validate_recommendations_against_menu(
                recommendations=recommendations_json.get("recommendations", []),
                menu_dishes=dishes_data.get("dishes", []),
                similarity_threshold=0.92
            )

            if not validation_result['is_valid']:
                logger.warning(f"Search more validation failed: {validation_result['invalid_dishes']}")

            # Формируем ответ
            final_text = f"🍽 <b>Другие рекомендации для {meal_type_text}:</b>\n\n"

            for rec in recommendations_json.get("recommendations", []):
                data_source_indicator = ""
                if rec.get('data_source') == 'web_search':
                    data_source_indicator = " ✅"
                elif rec.get('data_source') == 'estimate':
                    data_source_indicator = " ⚠️"

                final_text += (
                    f"<b>{rec['number']}. {rec['name']}</b>{data_source_indicator}\n"
                    f"~ {rec['calories']} ккал | Б: {rec['proteins']}г | "
                    f"Ж: {rec['fats']}г | У: {rec['carbs']}г\n\n"
                    f"💡 {rec['explanation']}\n\n"
                )

            if recommendations_json.get("general_advice"):
                final_text += f"---\n📊 {recommendations_json['general_advice']}\n\n"

            final_text += "<i>✅ = данные из интернета | ⚠️ = приблизительная оценка</i>\n\n"
            final_text += "👇 <b>Выбери действие:</b>"

            # Создаем кнопки
            keyboard = []
            for rec in recommendations_json.get("recommendations", []):
                dish_name = rec['name'][:35] + "..." if len(rec['name']) > 35 else rec['name']
                button_text = f"{rec['number']}. {dish_name}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=f"restaurant_dish_{rec['number']}")])

            keyboard.append([InlineKeyboardButton("🔄 Поищи ещё варианты", callback_data="restaurant_search_more")])
            keyboard.append([InlineKeyboardButton("✍️ Выберу сам", callback_data="restaurant_manual_input")])
            keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="main_menu")])

            await send_with_retry(
                processing_msg.edit_text(
                    final_text,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            )

            # Обновляем рекомендации
            context.user_data["restaurant_recommendations"] = recommendations_json

            logger.info(f"Search more recommendations provided for user {user.id}")

            return RestaurantStates.ANALYZING_MENU

    except Exception as e:
        logger.error("Error in search more for user {}: {}", user.id, repr(e), exc_info=True)
        await send_with_retry(
            processing_msg.edit_text(
                "❌ Произошла ошибка при поиске вариантов.\n\nПопробуй позже.",
                reply_markup=back_to_menu_keyboard()
            )
        )
        return ConversationHandler.END


async def handle_restaurant_manual_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переход к ручному вводу названия блюда"""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✍️ <b>Ручной ввод блюда</b>\n\n"
        "Напиши название блюда, которое ты выбрал из меню.\n"
        "Я проанализирую его КБЖУ и добавлю в твой дневник.\n\n"
        "<i>Например: \"Цезарь с курицей\" или \"Борщ\"</i>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
        ])
    )

    return RestaurantStates.WAITING_MANUAL_DISH_INPUT


async def handle_restaurant_manual_dish_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ручного ввода названия блюда"""
    user = update.effective_user
    dish_name = update.message.text.strip()

    if not dish_name:
        await update.message.reply_text(
            "❌ Пожалуйста, напиши название блюда.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Отмена", callback_data="main_menu")]
            ])
        )
        return RestaurantStates.WAITING_MANUAL_DISH_INPUT

    # Показываем прогресс
    processing_msg = await update.message.reply_text(
        f"🔍 Анализирую блюдо <b>«{dish_name}»</b>...\n\nПодожди немного.",
        parse_mode='HTML'
    )

    try:
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await processing_msg.edit_text(
                    "❌ Пользователь не найден.",
                    reply_markup=back_to_menu_keyboard()
                )
                return ConversationHandler.END

            # Запрашиваем КБЖУ у AI
            from anthropic import AsyncAnthropic
            from app.config import settings
            from app.services.web_search_service import WebSearchService

            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            # Ищем информацию о блюде в интернете
            web_search_results = await WebSearchService.search_multiple_dishes([dish_name])
            web_data_text = WebSearchService.format_search_results_for_prompt(web_search_results)

            prompt = f"""Проанализируй блюдо и определи его пищевую ценность.

БЛЮДО: {dish_name}

{web_data_text}

ЗАДАЧА:
Определи калорийность и БЖУ блюда. Используй данные из веб-поиска выше если есть, иначе дай приблизительную оценку.

ФОРМАТ ОТВЕТА - строго JSON:
{{
  "name": "{dish_name}",
  "calories": 450,
  "proteins": 30,
  "fats": 15,
  "carbs": 45,
  "data_source": "web_search" или "estimate",
  "portion_description": "1 порция"
}}

ВАЖНО:
- Используй реальные данные если они есть в веб-поиске
- Если данных нет - дай приблизительную оценку
- Верни валидный JSON"""

            response = await client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            analysis_text = response.content[0].text
            dish_data = safe_parse_json(analysis_text, context_name="manual_dish_analysis")

            # Получаем meal_type
            meal_type = context.user_data.get("restaurant_meal_type")
            if not meal_type:
                # Если не сохранен, спрашиваем
                await processing_msg.edit_text(
                    f"✅ <b>{dish_name}</b>\n"
                    f"~ {dish_data['calories']} ккал | Б: {dish_data['proteins']}г | "
                    f"Ж: {dish_data['fats']}г | У: {dish_data['carbs']}г\n\n"
                    "⏰ <b>К какому приему пищи это относится?</b>",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🌅 Завтрак", callback_data="manual_meal_breakfast")],
                        [InlineKeyboardButton("🌞 Обед", callback_data="manual_meal_lunch")],
                        [InlineKeyboardButton("🌙 Ужин", callback_data="manual_meal_dinner")],
                        [InlineKeyboardButton("🍎 Перекус", callback_data="manual_meal_snack")]
                    ])
                )
                # Сохраняем данные блюда
                context.user_data["manual_dish_data"] = dish_data
                return RestaurantStates.WAITING_MANUAL_DISH_INPUT

            # Добавляем в дневник
            from app.models.meal import MealType

            foods_data = [{
                "name": dish_data["name"],
                "portion_size": 1,
                "portion_description": dish_data.get("portion_description", "1 порция"),
                "calories": dish_data["calories"],
                "proteins": dish_data["proteins"],
                "fats": dish_data["fats"],
                "carbs": dish_data["carbs"]
            }]

            meal = await MealService.create_meal_with_foods(
                session=session,
                user_id=db_user.id,
                meal_type=meal_type,
                meal_date=date.today(),
                meal_time=datetime.now(),
                foods_data=foods_data
            )

            # Получаем прогресс
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

            data_source_text = "✅ данные из интернета" if dish_data.get("data_source") == "web_search" else "⚠️ приблизительная оценка"

            success_text = (
                f"✅ Добавлено в *{meal_type_names[meal_type]}*!\n\n"
                f"🍽 *{dish_data['name']}*\n"
                f"~ {dish_data['calories']} ккал | Б: {dish_data['proteins']}г | "
                f"Ж: {dish_data['fats']}г | У: {dish_data['carbs']}г\n"
                f"_{data_source_text}_\n\n"
                f"📊 *Прогресс за сегодня:*\n"
                f"🔥 Калории: {current['calories']}/{target['calories']} ккал "
                f"(осталось {remaining['calories']})\n"
                f"🥩 Белки: {current['proteins']:.0f}/{target['proteins']}г\n"
                f"🧈 Жиры: {current['fats']:.0f}/{target['fats']}г\n"
                f"🍞 Углеводы: {current['carbs']:.0f}/{target['carbs']}г\n\n"
            )

            if current['calories'] > target['calories']:
                success_text += "⚠️ Ты превысил дневную норму калорий\n"
            elif remaining['calories'] < 300:
                success_text += f"💡 Осталось всего {remaining['calories']} ккал на сегодня\n"

            success_text += "\n🎉 Приятного аппетита!"

            await processing_msg.edit_text(
                success_text,
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )

            # Очищаем контекст
            context.user_data.pop("restaurant_recommendations", None)
            context.user_data.pop("restaurant_meal_type", None)
            context.user_data.pop("manual_dish_data", None)

            logger.info(f"Manual dish '{dish_name}' added for user {user.id}, meal_id: {meal.id}")

            return ConversationHandler.END

    except Exception as e:
        logger.error("Error adding manual dish for user {}: {}", user.id, repr(e), exc_info=True)
        await send_with_retry(
            processing_msg.edit_text(
                "❌ Ошибка при добавлении блюда.\nПопробуй позже.",
                reply_markup=back_to_menu_keyboard()
            )
        )
        return ConversationHandler.END


async def cancel_restaurant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена функции 'Ресторан'"""
    query = update.callback_query
    await query.answer()

    context.user_data.pop("restaurant_menu_photo", None)
    context.user_data.pop("restaurant_mood", None)
    context.user_data.pop("restaurant_recommendations", None)
    context.user_data.pop("restaurant_meal_type", None)

    await query.edit_message_text(
        "❌ Функция 'Ресторан' отменена",
        reply_markup=main_menu_keyboard()
    )

    return ConversationHandler.END
