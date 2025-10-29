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
            logger.error(f"Failed to parse JSON response from Claude: {e}")
            logger.error(f"Response content: {content}")
            raise Exception("Failed to parse food recognition response")

        except Exception as e:
            logger.error(f"Error in Claude API food recognition: {e}")
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

            # System prompt с контекстом пользователя
            preferred_name = user_context.get('preferred_name', 'друг')

            # Формируем информацию о плане питания
            plan_info = ""
            if user_context.get('has_active_plan'):
                plan_summary = user_context.get('today_plan_summary', 'план доступен в меню')
                plan_info = f"""
План питания на сегодня:
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

            system_prompt = f"""{AI_SYSTEM_PROMPT_BASE}

{AI_SYSTEM_PROMPT_NO_DIAGNOSIS}

Ты - персональный AI-нутрициолог NutriAI.

ВАЖНО: Обращайся к пользователю по имени "{preferred_name}" в своих ответах.

Профиль пользователя:
- Имя: {preferred_name}
- Возраст: {user_context.get('age', 'не указан')}
- Пол: {user_context.get('gender', 'не указан')}
- Текущий вес: {user_context.get('current_weight', '?')} кг
- Целевой вес: {user_context.get('target_weight', '?')} кг
- Цель: {user_context.get('goal', 'не указана')}
- Уровень активности: {user_context.get('activity_level', 'не указан')}
- Целевые калории: {user_context.get('target_calories', '?')} ккал/день
- Диета: {user_context.get('diet_type', 'всеядный')}

Статистика сегодня:
- Потреблено калорий: {user_context.get('today_calories', 0)} / {user_context.get('target_calories', 0)} ккал
- Белки: {user_context.get('today_proteins', 0)}г
- Жиры: {user_context.get('today_fats', 0)}г
- Углеводы: {user_context.get('today_carbs', 0)}г

{remaining_info}
{plan_info}

Твоя задача:
1. Давать научно обоснованные рекомендации по питанию
2. Учитывать профиль и цели пользователя
3. Быть поддерживающим, дружелюбным и мотивирующим
4. Объяснять сложные концепции простым языком
5. Давать конкретные, практичные советы
6. Использовать формулировки: "могут быть признаки", "возможен дефицит", "рекомендую проконсультироваться"
7. При серьезных вопросах здоровья обязательно рекомендовать консультацию врача

СПЕЦИАЛЬНАЯ ФУНКЦИЯ - КОРРЕКЦИЯ РАЦИОНА:
Когда пользователь:
- Превысил дневную норму калорий
- Отклонился от плана питания
- Просит помочь скорректировать оставшийся день
Ты должен:
1. Использовать психотерапевтический подход: выслушать, понять причины без осуждения
2. Спросить что привело к отклонению (если уместно)
3. Предложить конкретные варианты блюд для оставшихся приемов пищи, которые:
   - Укладываются в оставшиеся калории ({user_context.get('remaining_calories', 0)} ккал)
   - Помогают достичь баланса макронутриентов
   - Соответствуют диете пользователя ({user_context.get('diet_type', 'всеядный')})
   - Учитывают аллергии
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
            logger.error(f"Error in Claude chat: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса. Попробуйте позже."


# Создаем singleton экземпляр сервиса
claude_service = ClaudeAIService()
