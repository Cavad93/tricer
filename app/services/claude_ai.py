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
            prompt = f"""Проанализируй фото еды и определи следующую информацию:

1. Название блюда (на русском)
2. Список основных ингредиентов
3. Примерный размер порции в граммах
4. Способ приготовления (вареное/жареное/запеченное/сырое)
5. Пищевая ценность на указанную порцию:
   - Калории (ккал)
   - Белки (г)
   - Жиры (г)
   - Углеводы (г)

{additional_context}

ВАЖНО: Будь максимально точным в оценке размера порции и калорийности.
Если на фото несколько блюд, опиши каждое отдельно.

Формат ответа строго JSON:
{{
  "dishes": [
    {{
      "name": "Название блюда",
      "ingredients": ["ингредиент1", "ингредиент2"],
      "portion_size_grams": 250,
      "cooking_method": "жареное",
      "nutrition": {{
        "calories": 450,
        "proteins": 30,
        "fats": 15,
        "carbs": 45
      }},
      "confidence": 0.9
    }}
  ],
  "total_nutrition": {{
    "calories": 450,
    "proteins": 30,
    "fats": 15,
    "carbs": 45
  }}
}}"""

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
            # System prompt с контекстом пользователя
            preferred_name = user_context.get('preferred_name', 'друг')
            system_prompt = f"""Ты - персональный AI-нутрициолог NutriAI.

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

Твоя задача:
1. Давать научно обоснованные рекомендации по питанию
2. Учитывать профиль и цели пользователя
3. Быть поддерживающим и мотивирующим
4. Объяснять сложные концепции простым языком
5. Давать конкретные, практичные советы
6. НЕ ставить медицинские диагнозы
7. При серьезных вопросах здоровья рекомендовать врача

Стиль общения: дружелюбный, эмпатичный, профессиональный.
Обращайся к пользователю по имени "{preferred_name}".
Используй эмодзи для наглядности.
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
