"""
Сервис для работы с Anthropic Claude API
"""
import anthropic
from anthropic import Anthropic, AsyncAnthropic
import base64
import json
from typing import Dict, List, Optional
from loguru import logger

from app.config import settings


class ClaudeAIService:
    """Сервис для интеграции с Claude API"""

    def __init__(self):
        """Инициализация клиента Claude"""
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.async_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL

    async def analyze_food_photo(
        self,
        image_bytes: bytes,
        additional_context: str = ""
    ) -> Dict:
        """
        Распознавание еды по фото через Claude Vision API

        Args:
            image_bytes: Изображение в байтах
            additional_context: Дополнительный контекст для анализа

        Returns:
            Словарь с информацией о блюде
        """
        try:
            # Конвертация изображения в base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            # Промпт для анализа
            prompt = f"""ПЕРВАЯ ПРОВЕРКА - Безопасность контента:
Перед анализом еды проверь, содержит ли изображение:
- Несъедобные предметы (фекалии, мусор, отходы и т.д.)
- Неэтичный или шокирующий контент (труп, насилие и т.д.)
- Любой контент, явно не связанный с едой и не подходящий для анализа питания

Если изображение содержит неподходящий контент, верни:
{{
  "inappropriate_content": true,
  "reason": "краткая причина (не съедобно/неэтично/и т.д.)"
}}

Если контент подходящий (это еда или блюда), проанализируй фото как профессиональный диетолог и определи:

ОСОБЕННО ВАЖНО - Упакованные продукты:
- Если на фото еда В УПАКОВКЕ (мороженое, шоколад, йогурт, чипсы, батончики, напитки в бутылках/банках и т.д.)
- Читай информацию на этикетке! Бренд, название продукта, вес, КБЖУ
- Верни флаг "is_packaged": true и "needs_confirmation": true
- Это означает что нужно уточнить у пользователя - он УЖЕ съел это или ПЛАНИРУЕТ съесть
- Примеры упакованных продуктов: мороженое "Пломбир", шоколадка "Сникерс", йогурт "Активиа", сок в пакете, чипсы "Лейс"

Если еда НЕ в упаковке (на тарелке, в миске, яблоко на столе и т.д.):
- "is_packaged": false, "needs_confirmation": false
- Пользователь скорее всего УЖЕ съел это или сейчас ест

1. Название блюда (на русском)
2. Список основных ингредиентов
3. Примерный размер порции:
   - В граммах (используй визуальные подсказки: размер тарелки, столовых приборов, руки)
   - Описание порции понятным языком (например: "1 средняя тарелка", "200г куриной грудки", "горсть орехов")
4. Способ приготовления (вареное/жареное/запеченное/сырое/тушеное)
5. Пищевая ценность на указанную порцию:
   - Калории (ккал) - учитывай способ приготовления и добавленные жиры/масла
   - Белки (г)
   - Жиры (г)
   - Углеводы (г)
6. Основные микронутриенты (примерная оценка):
   - Витамины: A, B1, B2, B3, B6, B9, B12, C, D, E (в мкг или мг)
   - Минералы: Железо, Кальций, Магний, Калий, Цинк (в мг)
   ВАЖНО: Это приблизительная оценка на основе типичного состава продуктов
7. Уверенность в распознавании (0.0-1.0)

{additional_context}

КРИТИЧЕСКИ ВАЖНО для точности:
- Оценивай вес, сравнивая с размером тарелки (обычно диаметр 20-25см)
- Учитывай плотность продуктов (жидкое vs твердое)
- Если видны столовые приборы/руки - используй их как масштаб
- Если на фото несколько блюд, опиши каждое отдельно
- Для калорийности учитывай способ приготовления (жареное +30-50% калорий от масла)

Формат ответа строго JSON (если контент подходящий):
{{
  "inappropriate_content": false,
  "is_packaged": true/false,
  "needs_confirmation": true/false,
  "package_info": {{
    "brand": "Название бренда" (если упакован),
    "product_name": "Название продукта с этикетки" (если упакован),
    "weight_grams": 100 (вес с упаковки)
  }},
  "dishes": [
    {{
      "name": "Название блюда",
      "ingredients": ["ингредиент1", "ингредиент2"],
      "portion_size_grams": 250,
      "portion_description": "1 средняя тарелка" или "200г куриной грудки",
      "cooking_method": "жареное",
      "nutrition": {{
        "calories": 450,
        "proteins": 30,
        "fats": 15,
        "carbs": 45
      }},
      "micronutrients": {{
        "vitamin_a": 120.0,
        "vitamin_b1": 0.3,
        "vitamin_b2": 0.4,
        "vitamin_b3": 5.0,
        "vitamin_b6": 0.5,
        "vitamin_b9": 50.0,
        "vitamin_b12": 1.5,
        "vitamin_c": 15.0,
        "vitamin_d": 2.0,
        "vitamin_e": 3.0,
        "iron": 3.5,
        "calcium": 80.0,
        "magnesium": 45.0,
        "potassium": 350.0,
        "zinc": 2.5
      }},
      "confidence": 0.85
    }}
  ],
  "total_nutrition": {{
    "calories": 450,
    "proteins": 30,
    "fats": 15,
    "carbs": 45
  }},
  "total_micronutrients": {{
    "vitamin_a": 120.0,
    "vitamin_b1": 0.3,
    "vitamin_b2": 0.4,
    "vitamin_b3": 5.0,
    "vitamin_b6": 0.5,
    "vitamin_b9": 50.0,
    "vitamin_b12": 1.5,
    "vitamin_c": 15.0,
    "vitamin_d": 2.0,
    "vitamin_e": 3.0,
    "iron": 3.5,
    "calcium": 80.0,
    "magnesium": 45.0,
    "potassium": 350.0,
    "zinc": 2.5
  }}
}}

ВАЖНО о микронутриентах:
- Указывай только основные (топ-10), остальные можно опустить
- Если данных нет - поставь 0
- Это приблизительная оценка на основе типичного состава
- Единицы: витамины A,D,E в мкг; группа B в мг; минералы в мг"""

            logger.info("Sending request to Claude API for food recognition")

            # Отправка запроса к Claude API (асинхронно)
            response = await self.async_client.messages.create(
                model=self.model,
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

            # Парсинг ответа
            content = response.content[0].text

            # Извлечение JSON из ответа
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            result = json.loads(content.strip())

            logger.info(f"Food recognition successful: {result['dishes'][0]['name']}")

            return result

        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response from Claude: {}", repr(e))
            logger.error(f"Response content: {content}")
            raise Exception("Failed to parse food recognition response")

        except Exception as e:
            logger.error("Error in Claude API food recognition: {}", repr(e))
            raise

    async def chat(
        self,
        user_message: str,
        conversation_history: List[Dict],
        user_context: Dict
    ) -> str:
        """
        AI-чат с пользователем

        Args:
            user_message: Сообщение пользователя
            conversation_history: История разговора
            user_context: Контекст пользователя (профиль, статистика)

        Returns:
            Ответ ассистента
        """
        try:
            # Импортируем системные промпты для медицинской безопасности
            from app.bot.texts import AI_SYSTEM_PROMPT_BASE, AI_SYSTEM_PROMPT_NO_DIAGNOSIS

            # System prompt с ПОЛНЫМ контекстом пользователя
            preferred_name = user_context.get('preferred_name', 'друг')

            # Формируем информацию о медицинских данных
            medical_info = ""
            chronic_conditions = user_context.get('chronic_conditions', [])
            removed_organs = user_context.get('removed_organs', [])
            medical_restrictions = user_context.get('medical_restrictions', [])
            allergies = user_context.get('allergies', [])

            if chronic_conditions or removed_organs or medical_restrictions or allergies:
                medical_info = "\nМЕДИЦИНСКИЕ ДАННЫЕ (учитывай ОБЯЗАТЕЛЬНО!):\n"
                if chronic_conditions:
                    medical_info += f"- Хронические заболевания: {', '.join(chronic_conditions)}\n"
                if removed_organs:
                    medical_info += f"- Удаленные органы: {', '.join(removed_organs)}\n"
                if medical_restrictions:
                    medical_info += f"- Медицинские ограничения: {', '.join(medical_restrictions)}\n"
                if allergies:
                    medical_info += f"- Аллергии: {', '.join(allergies)}\n"
                if user_context.get('medical_notes'):
                    medical_info += f"- Примечания врача: {user_context.get('medical_notes')}\n"

            # Формируем информацию о недавних приемах пищи
            recent_meals_info = ""
            recent_meals = user_context.get('recent_meals', [])
            if recent_meals:
                recent_meals_info = "\nНЕДАВНИЕ ПРИЕМЫ ПИЩИ (реальные данные!):\n"
                for meal_text in recent_meals[:5]:
                    recent_meals_info += f"- {meal_text}\n"

            # Формируем информацию о самочувствии
            wellness_info = ""
            recent_wellness = user_context.get('recent_wellness', [])
            if recent_wellness:
                wellness_info = "\nИСТОРИЯ САМОЧУВСТВИЯ:\n"
                for wellness_text in recent_wellness:
                    wellness_info += f"- {wellness_text}\n"

            # Формируем информацию о плане питания
            plan_info = ""
            if user_context.get('has_active_plan'):
                plan_summary = user_context.get('today_plan_summary', 'план доступен в меню')
                plan_info = f"""\nПлан питания на сегодня:
{plan_summary}
"""

            # Формируем информацию об оставшихся калориях
            remaining_info = f"""
Оставшиеся калории/макросы на сегодня:
- Калории: {user_context.get('remaining_calories', 0)} ккал
- Белки: {user_context.get('remaining_proteins', 0)}г
- Жиры: {user_context.get('remaining_fats', 0)}г
- Углеводы: {user_context.get('remaining_carbs', 0)}г
"""

            # Формируем дополнительную информацию
            extra_info = ""
            if user_context.get('dislikes'):
                extra_info += f"\n- Не любит: {', '.join(user_context.get('dislikes', []))}"
            if user_context.get('budget_category'):
                extra_info += f"\n- Бюджет: {user_context.get('budget_category')}"
            if user_context.get('preferred_cooking_time_minutes'):
                extra_info += f"\n- Предпочитаемое время на готовку: {user_context.get('preferred_cooking_time_minutes')} мин"
            if user_context.get('city'):
                extra_info += f"\n- Город: {user_context.get('city')}"

            system_prompt = f"""{AI_SYSTEM_PROMPT_BASE}

{AI_SYSTEM_PROMPT_NO_DIAGNOSIS}

Ты - персональный AI-нутрициолог NutriAI с полным доступом к данным пользователя.

КРИТИЧЕСКИ ВАЖНО:
- У тебя есть ВСЯ информация о пользователе - НЕ задавай вопросы о том, что уже известно!
- НЕ фантазируй - используй ТОЛЬКО реальные данные из профиля ниже
- Если чего-то нет в профиле - можешь спросить, но сначала проверь все разделы

ВАЖНО: Обращайся к пользователю по имени "{preferred_name}" в своих ответах.

=== ПОЛНЫЙ ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ===

БАЗОВЫЕ ДАННЫЕ:
- Имя: {preferred_name}
- Возраст: {user_context.get('age', 'не указан')} лет
- Пол: {user_context.get('gender', 'не указан')}
- Рост: {user_context.get('height', '?')} см
- Текущий вес: {user_context.get('current_weight', '?')} кг
- Целевой вес: {user_context.get('target_weight', '?')} кг
- Цель: {user_context.get('goal', 'не указана')}
- Уровень активности: {user_context.get('activity_level', 'не указан')}

ЦЕЛЕВЫЕ ЗНАЧЕНИЯ:
- Целевые калории: {user_context.get('target_calories', '?')} ккал/день
- Целевые белки: {user_context.get('target_proteins', '?')}г
- Целевые жиры: {user_context.get('target_fats', '?')}г
- Целевые углеводы: {user_context.get('target_carbs', '?')}г

ПРЕДПОЧТЕНИЯ:
- Диета: {user_context.get('diet_type', 'всеядный')}{extra_info}
{medical_info}
СТАТИСТИКА СЕГОДНЯ (реальные данные из дневника):
- Потреблено калорий: {user_context.get('today_calories', 0)} / {user_context.get('target_calories', 0)} ккал
- Белки: {user_context.get('today_proteins', 0)}г / {user_context.get('target_proteins', 0)}г
- Жиры: {user_context.get('today_fats', 0)}г / {user_context.get('target_fats', 0)}г
- Углеводы: {user_context.get('today_carbs', 0)}г / {user_context.get('target_carbs', 0)}г
{remaining_info}{recent_meals_info}{wellness_info}{plan_info}
=== КОНЕЦ ПРОФИЛЯ ===

Твоя задача:
1. Давать научно обоснованные рекомендации по питанию
2. ОБЯЗАТЕЛЬНО учитывать медицинские данные и ограничения
3. Использовать реальные данные о питании и самочувствии для анализа
4. Быть поддерживающим, дружелюбным и мотивирующим
5. Объяснять сложные концепции простым языком
6. Давать конкретные, практичные советы
7. НЕ задавать вопросы о том, что УЖЕ ЕСТЬ в профиле выше
8. При серьезных вопросах здоровья обязательно рекомендовать консультацию врача

СПЕЦИАЛЬНАЯ ФУНКЦИЯ - КОРРЕКЦИЯ РАЦИОНА:
Когда пользователь:
- Превысил дневную норму калорий
- Отклонился от плана питания
- Просит помочь скорректировать оставшийся день
Ты должен:
1. Использовать психотерапевтический подход: выслушать, понять причины без осуждения
2. Проанализировать что уже съедено (см. "НЕДАВНИЕ ПРИЕМЫ ПИЩИ")
3. Предложить конкретные варианты блюд для оставшихся приемов пищи, которые:
   - Укладываются в оставшиеся калории ({user_context.get('remaining_calories', 0)} ккал)
   - Помогают достичь баланса макронутриентов
   - Соответствуют диете пользователя ({user_context.get('diet_type', 'всеядный')})
   - Учитывают аллергии и медицинские ограничения
4. Давать 2-3 конкретных варианта с КБЖУ
5. Подбодрить и мотивировать - один срыв не отменяет прогресс!

Стиль общения: дружелюбный, поддерживающий, эмпатичный, профессиональный.
Обращайся к пользователю по имени "{preferred_name}".
Используй эмодзи для наглядности и теплоты.
Формат: короткие абзацы, списки, конкретика."""

            # Добавляем текущее сообщение в историю
            messages = conversation_history + [
                {"role": "user", "content": user_message}
            ]

            logger.info(f"Sending chat request to Claude API")

            # Отправка запроса к Claude API (асинхронно)
            response = await self.async_client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=system_prompt,
                messages=messages
            )

            assistant_message = response.content[0].text

            logger.info("Chat response received successfully")

            return assistant_message

        except Exception as e:
            logger.error("Error in Claude chat: {}", repr(e))
            return "Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже."

    async def analyze_text(
        self,
        prompt: str,
        max_tokens: int = 2000
    ) -> str:
        """
        Анализ текста с помощью Claude (общий метод)

        Args:
            prompt: Промпт для анализа
            max_tokens: Максимальное количество токенов в ответе

        Returns:
            Ответ от Claude
        """
        try:
            logger.info(f"Отправка текстового анализа в Claude API")

            response = await self.async_client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            text_response = response.content[0].text
            logger.info("Текстовый анализ получен успешно")

            return text_response

        except Exception as e:
            logger.error("Ошибка в Claude text analysis: {}", repr(e))
            raise

    async def extract_medical_analysis_from_image(
        self,
        image_bytes: bytes
    ) -> str:
        """
        Извлечение текста медицинских анализов с изображения через Claude Vision API

        Args:
            image_bytes: Изображение в байтах

        Returns:
            Строка с извлеченными показателями анализов
        """
        try:
            logger.info("Starting medical analysis OCR with Claude Vision API")

            # Конвертация изображения в base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            # Промпт для извлечения данных медицинских анализов
            prompt = """Ты эксперт по распознаванию медицинских документов. Извлеки ВСЕ лабораторные показатели из изображения анализа.

**ЗАДАЧА:**
Извлеки из изображения все показатели анализа в структурированном виде.

**ЧТО ИСКАТЬ:**

🩸 **Общий анализ крови (ОАК):**
- Гемоглобин (Hb, HGB)
- Эритроциты (RBC)
- Лейкоциты (WBC)
- Тромбоциты (PLT)
- Гематокрит (HCT)
- MCV, MCH, MCHC (эритроцитарные индексы)
- Цветовой показатель (ЦП)
- СОЭ (ESR)

🧪 **Биохимический анализ крови:**
- Глюкоза (Glucose)
- Холестерин (Cholesterol)
- ЛПНП, ЛПВП (LDL, HDL)
- Триглицериды (Triglycerides)
- Общий белок (Total protein)
- Альбумин (Albumin)
- Мочевина (Urea)
- Креатинин (Creatinine)
- АЛТ, АСТ (ALT, AST)
- Билирубин (Bilirubin)
- Железо (Fe, Iron)
- Ферритин (Ferritin)
- Кальций (Ca, Calcium)
- Магний (Mg, Magnesium)
- Калий (K, Potassium)
- Натрий (Na, Sodium)
- Мочевая кислота (Uric acid)

💧 **Общий анализ мочи (ОАМ):**
- Цвет
- Прозрачность
- Плотность
- pH
- Белок (Protein)
- Глюкоза (Glucose)
- Кетоновые тела (Ketones)
- Билирубин
- Уробилиноген
- Эритроциты
- Лейкоциты
- Эпителий
- Бактерии

🧬 **Гормоны и витамины (если есть):**
- ТТГ, Т3, Т4 (щитовидная железа)
- Витамин D
- Витамин B12
- Фолиевая кислота
- И другие

**ФОРМАТ ВЫВОДА:**

Верни показатели в виде структурированного текста:

Название показателя: значение единица_измерения

Например:
Гемоглобин: 130 г/л
Эритроциты: 4.5 ×10¹²/л
Глюкоза: 5.2 ммоль/л
Холестерин общий: 5.8 ммоль/л

**ВАЖНО:**
- Извлекай ВСЕ показатели, которые видишь на изображении
- Сохраняй точные значения и единицы измерения
- Если показатель отмечен как выше/ниже нормы, укажи это
- Если видишь референсные значения (нормы), укажи их
- Игнорируй служебную информацию (имена, даты рождения, штрихкоды)

**ЕСЛИ ИЗОБРАЖЕНИЕ НЕ МЕДИЦИНСКИЙ АНАЛИЗ:**
Если это не медицинский анализ (например, фото еды, документ, текст), верни:
"ОШИБКА: На изображении не обнаружен медицинский анализ"

Начинай извлечение показателей:"""

            # Запрос к Claude Vision API
            response = await self.async_client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }]
            )

            # Извлекаем текст из ответа
            extracted_text = response.content[0].text

            logger.info(f"Medical analysis OCR completed, extracted {len(extracted_text)} characters")

            # Проверяем, что это действительно медицинский анализ
            if "ОШИБКА:" in extracted_text:
                logger.warning("Image is not a medical analysis")
                return extracted_text

            return extracted_text

        except Exception as e:
            logger.error("Error in medical analysis OCR: {}", repr(e), exc_info=True)
            raise

    async def detect_food_inquiry_intent(
        self,
        user_message: str,
        conversation_history: List[Dict] = None
    ) -> Dict:
        """
        Определить намерение пользователя узнать что поесть

        Args:
            user_message: Сообщение пользователя
            conversation_history: История разговора

        Returns:
            Словарь с результатом определения намерения
        """
        try:
            prompt = f"""Определи, спрашивает ли пользователь рекомендацию о том, что поесть/съесть.

Сообщение пользователя: "{user_message}"

Примеры вопросов о еде:
- "Что мне поесть?"
- "Что приготовить на ужин?"
- "Подскажи что съесть"
- "Какой завтрак посоветуешь?"
- "Чем перекусить?"
- "Что бы такого съесть?"

Верни JSON:
{{
    "is_food_inquiry": true/false,
    "confidence": "high/medium/low",
    "meal_type_mentioned": "завтрак/обед/ужин/перекус" или null
}}

Важно: Если пользователь просто обсуждает еду, но не просит рекомендацию - это НЕ food_inquiry."""

            response = await self.async_client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = response.content[0].text
            result = self.extract_json_from_response(response_text)

            if not result:
                return {
                    "is_food_inquiry": False,
                    "confidence": "low",
                    "meal_type_mentioned": None
                }

            return result

        except Exception as e:
            logger.error("Error detecting food inquiry intent: {}", repr(e))
            return {
                "is_food_inquiry": False,
                "confidence": "low",
                "meal_type_mentioned": None
            }

    async def generate_meal_recommendation(
        self,
        user_message: str,
        recommendation_context: Dict,
        conversation_history: List[Dict] = None
    ) -> str:
        """
        Генерация рекомендаций по питанию на основе контекста

        Args:
            user_message: Сообщение пользователя
            recommendation_context: Контекст для рекомендаций
            conversation_history: История разговора

        Returns:
            Текст с рекомендациями
        """
        try:
            # Формируем контекст для промпта
            daily_status = recommendation_context["daily_status"]
            remaining = recommendation_context["remaining"]
            meal_type = recommendation_context["meal_type"]
            current_time = recommendation_context["current_time"]
            user_prefs = recommendation_context["user_preferences"]
            medical = recommendation_context["medical_restrictions"]

            # Формируем информацию о плане
            has_plan = recommendation_context["has_plan"]
            plan_type = recommendation_context.get("plan_type")

            plan_info = ""
            if has_plan and plan_type == "permanent":
                plan_info = "\n⚠️ У пользователя УЖЕ ЕСТЬ план питания на сегодня. Напомни ему об этом и предложи посмотреть план через меню."
            elif has_plan and plan_type == "temporary":
                plan_info = "\n📋 У пользователя есть временные рекомендации на сегодня. Ты можешь их обновить или дать новые."

            # Формируем медицинские ограничения
            medical_info = ""
            if medical:
                medical_info = f"\n\n🏥 Медицинские ограничения:\n"
                for restriction_type, items in medical.items():
                    if items:
                        medical_info += f"- {restriction_type}: {', '.join(items)}\n"

            prompt = f"""Ты AI-нутрициолог помогающий с питанием. Пользователь спрашивает: "{user_message}"

📊 ТЕКУЩАЯ СИТУАЦИЯ:
⏰ Время: {current_time} (рекомендуемый прием пищи: {meal_type})
📈 Съедено сегодня: {daily_status['total_calories']} ккал ({remaining['calories_percent']}% от цели)
   - Белки: {daily_status['total_proteins']}г
   - Жиры: {daily_status['total_fats']}г
   - Углеводы: {daily_status['total_carbs']}г

💡 ОСТАЛОСЬ ДО ЦЕЛИ:
   - Калории: {remaining['remaining_calories']} ккал
   - Белки: {remaining['remaining_proteins']}г
   - Жиры: {remaining['remaining_fats']}г
   - Углеводы: {remaining['remaining_carbs']}г

{f"🎁 Бонус от активности: +{remaining['bonus_calories']} ккал" if remaining['bonus_calories'] > 0 else ""}

👤 ПРЕДПОЧТЕНИЯ ПОЛЬЗОВАТЕЛЯ:
- Тип питания: {user_prefs['diet_type']}
- Бюджет: {user_prefs['budget']}
- Время на готовку: {user_prefs['cooking_time']} минут (если указано)
{f"- Аллергии: {', '.join(user_prefs['allergies'])}" if user_prefs['allergies'] else ""}
{f"- Не любит: {', '.join(user_prefs['dislikes'])}" if user_prefs['dislikes'] else ""}
{medical_info}
{plan_info}

ТВОЯ ЗАДАЧА:
1. Предложи 2-3 конкретных варианта блюд на текущий прием пищи ({meal_type})
2. Для каждого блюда укажи примерные КБЖУ
3. Учти оставшиеся калории и макронутриенты
4. Учти предпочтения, аллергии и медицинские ограничения
5. Дай краткие рекомендации (1-2 предложения)

ФОРМАТ ОТВЕТА:
🍽️ **Рекомендации на {meal_type}:**

**Вариант 1: [Название блюда]**
📊 ~XXX ккал | Б: XXг | Ж: XXг | У: XXг
💭 [Краткое описание почему это подходит]

**Вариант 2: [Название блюда]**
...

💡 **Совет:** [Общая рекомендация на 1-2 предложения]

Будь дружелюбным и конкретным. Не перегружай текстом."""

            # Добавляем историю разговора если есть
            messages = []
            if conversation_history:
                messages.extend(conversation_history[-6:])  # Последние 3 обмена

            messages.append({
                "role": "user",
                "content": prompt
            })

            response = await self.async_client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=messages
            )

            recommendation_text = response.content[0].text

            logger.info(f"Generated meal recommendation, length: {len(recommendation_text)}")

            return recommendation_text

        except Exception as e:
            logger.error("Error generating meal recommendation: {}", repr(e), exc_info=True)
            raise

    @staticmethod
    def extract_json_from_response(response: str) -> Optional[Dict]:
        """
        Извлечение JSON из ответа Claude

        Args:
            response: Текст ответа от Claude

        Returns:
            Словарь с распарсенным JSON или None
        """
        try:
            # Пытаемся найти JSON в тексте
            import re

            # Ищем JSON блоки в markdown формате
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)

            # Ищем простой JSON блок
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)

            # Если не нашли - пытаемся парсить весь ответ
            return json.loads(response)

        except Exception as e:
            logger.warning("Не удалось извлечь JSON из ответа Claude: {}", repr(e))
            return None


# Создаем singleton экземпляр сервиса
claude_service = ClaudeAIService()
