"""
Сервис для работы с данными о самочувствии и AI-анализа паттернов
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.wellness_log import WellnessLog
from app.models.meal import Meal, MealFood
from app.models.user import User
from app.services.claude_ai import ClaudeAIService
from app.services.micronutrient_service import MicronutrientService


class WellnessService:
    """Сервис для анализа самочувствия и корреляций с питанием"""

    def __init__(self):
        self.claude_service = ClaudeAIService()
        self.micronutrient_service = MicronutrientService()

    @staticmethod
    async def create_wellness_log(
        session: AsyncSession,
        user_id: int,
        meal_id: Optional[int] = None,
        sleep_hours: Optional[float] = None,
        sleep_quality: Optional[int] = None,
        energy_level: Optional[int] = None,
        mood: Optional[int] = None,
        digestive_comfort: Optional[int] = None,
        mental_clarity: Optional[int] = None,
        hunger_level: Optional[int] = None,
        stress_level: Optional[int] = None,
        physical_symptoms: Optional[List[str]] = None,
        notes: Optional[str] = None,
        time_after_meal_minutes: Optional[int] = None
    ) -> WellnessLog:
        """
        Создает запись о самочувствии

        Args:
            session: Async сессия БД
            user_id: ID пользователя
            meal_id: ID приема пищи (если связано с едой)
            sleep_hours: Часы сна
            sleep_quality: Качество сна (1-10)
            energy_level: Уровень энергии (1-10)
            mood: Настроение (1-10)
            digestive_comfort: Комфорт пищеварения (1-10)
            mental_clarity: Ясность ума (1-10)
            hunger_level: Уровень голода (1-10)
            stress_level: Уровень стресса (1-10)
            physical_symptoms: Список физических симптомов
            notes: Заметки
            time_after_meal_minutes: Время после еды (минут)

        Returns:
            WellnessLog: Созданная запись
        """
        wellness_log = WellnessLog(
            user_id=user_id,
            meal_id=meal_id,
            log_datetime=datetime.now(),
            sleep_hours=sleep_hours,
            sleep_quality=sleep_quality,
            energy_level=energy_level,
            mood=mood,
            digestive_comfort=digestive_comfort,
            mental_clarity=mental_clarity,
            hunger_level=hunger_level,
            stress_level=stress_level,
            physical_symptoms=physical_symptoms or [],
            notes=notes,
            time_after_meal_minutes=time_after_meal_minutes
        )

        session.add(wellness_log)
        await session.commit()
        await session.refresh(wellness_log)

        logger.info(f"Created wellness log for user {user_id}, meal {meal_id}")
        return wellness_log

    @staticmethod
    async def get_wellness_logs_for_period(
        session: AsyncSession,
        user_id: int,
        days: int = 7
    ) -> List[WellnessLog]:
        """
        Получает записи о самочувствии за период

        Args:
            session: Async сессия БД
            user_id: ID пользователя
            days: Количество дней для анализа

        Returns:
            List[WellnessLog]: Список записей
        """
        start_date = datetime.now() - timedelta(days=days)

        result = await session.execute(
            select(WellnessLog)
            .where(
                and_(
                    WellnessLog.user_id == user_id,
                    WellnessLog.log_datetime >= start_date
                )
            )
            .order_by(desc(WellnessLog.log_datetime))
        )

        return result.scalars().all()

    async def analyze_wellness_patterns(
        self,
        session: AsyncSession,
        user_id: int,
        days: int = 14
    ) -> Dict:
        """
        Анализирует паттерны самочувствия с помощью AI

        Args:
            session: Async сессия БД
            user_id: ID пользователя
            days: Количество дней для анализа

        Returns:
            Dict: Результаты анализа с инсайтами и рекомендациями
        """
        try:
            # Получаем данные о самочувствии
            wellness_logs = await self.get_wellness_logs_for_period(session, user_id, days)

            if not wellness_logs:
                return {
                    "status": "no_data",
                    "message": "Недостаточно данных для анализа"
                }

            # Получаем данные о питании для корреляции
            start_date = datetime.now() - timedelta(days=days)
            meals_result = await session.execute(
                select(Meal)
                .where(
                    and_(
                        Meal.user_id == user_id,
                        Meal.meal_date >= start_date.date()
                    )
                )
                .order_by(Meal.meal_time)
            )
            meals = meals_result.scalars().all()

            # Получаем информацию о пользователе
            user_result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()

            # Формируем данные для AI анализа
            wellness_data = []
            for log in wellness_logs:
                log_data = {
                    "date": log.log_datetime.strftime("%Y-%m-%d %H:%M"),
                    "wellness_score": log.get_wellness_score(),
                    "energy": log.energy_level,
                    "mood": log.mood,
                    "digestive_comfort": log.digestive_comfort,
                    "mental_clarity": log.mental_clarity,
                    "stress": log.stress_level,
                    "sleep_hours": log.sleep_hours,
                    "sleep_quality": log.sleep_quality,
                    "symptoms": log.physical_symptoms,
                    "notes": log.notes
                }

                # Добавляем информацию о связанном приеме пищи
                if log.meal_id:
                    meal = next((m for m in meals if m.id == log.meal_id), None)
                    if meal:
                        log_data["meal"] = {
                            "type": meal.meal_type.value,
                            "time": meal.meal_time.strftime("%H:%M"),
                            "calories": meal.total_calories,
                            "proteins": meal.total_proteins,
                            "fats": meal.total_fats,
                            "carbs": meal.total_carbs,
                            "time_after_meal": log.time_after_meal_minutes
                        }

                wellness_data.append(log_data)

            # Рассчитываем средние микронутриенты за период
            start_date = datetime.now().date() - timedelta(days=days)
            end_date = datetime.now().date()
            avg_micronutrients = await self.micronutrient_service.calculate_period_average(
                session, user_id, start_date, end_date
            )

            # Строим промпт для AI
            prompt = self._build_wellness_analysis_prompt(
                wellness_data=wellness_data,
                user_gender=user.gender.value if user.gender else "unknown",
                user_age=datetime.now().year - user.birth_year if user.birth_year else None,
                avg_micronutrients=avg_micronutrients
            )

            # Отправляем запрос к Claude
            response = await self.claude_service.async_client.messages.create(
                model=self.claude_service.model,
                max_tokens=2000,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Парсим ответ
            response_text = response.content[0].text

            # Пытаемся извлечь JSON
            import json
            import re

            # Ищем JSON в ответе
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis_result = json.loads(json_match.group())
            else:
                # Если JSON не найден, возвращаем текстовый ответ
                analysis_result = {
                    "status": "success",
                    "text_analysis": response_text
                }

            logger.info(f"Wellness pattern analysis completed for user {user_id}")
            return analysis_result

        except Exception as e:
            logger.error("Error analyzing wellness patterns: {}", repr(e))
            return {
                "status": "error",
                "message": f"Ошибка при анализе: {str(e)}"
            }

    def _build_wellness_analysis_prompt(
        self,
        wellness_data: List[Dict],
        user_gender: str,
        user_age: Optional[int],
        avg_micronutrients: Dict
    ) -> str:
        """
        Строит промпт для AI анализа паттернов самочувствия

        Args:
            wellness_data: Данные о самочувствии
            user_gender: Пол пользователя
            user_age: Возраст пользователя
            avg_micronutrients: Средние микронутриенты

        Returns:
            str: Промпт для AI
        """
        import json

        prompt = f"""Ты - эксперт по анализу взаимосвязи питания и самочувствия.

Проанализируй данные о самочувствии пользователя и найди ПАТТЕРНЫ и КОРРЕЛЯЦИИ.

ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ:
- Пол: {user_gender}
- Возраст: {user_age or "не указан"}

ДАННЫЕ О САМОЧУВСТВИИ ЗА ПЕРИОД:
{json.dumps(wellness_data, ensure_ascii=False, indent=2)}

СРЕДНИЕ МИКРОНУТРИЕНТЫ ЗА ПЕРИОД:
{json.dumps(avg_micronutrients, ensure_ascii=False, indent=2)}

ЗАДАЧИ АНАЛИЗА:

1. ПАТТЕРНЫ САМОЧУВСТВИЯ:
   - Какие показатели самочувствия наиболее проблемные?
   - Есть ли тренды улучшения или ухудшения?
   - Какие симптомы повторяются?

2. КОРРЕЛЯЦИЯ С ПИТАНИЕМ:
   - Как питание влияет на энергию, настроение, пищеварение?
   - Есть ли связь между макронутриентами и самочувствием?
   - Влияет ли время приема пищи на самочувствие?

3. КОРРЕЛЯЦИЯ С МИКРОНУТРИЕНТАМИ:
   - Какие дефициты микронутриентов могут объяснять симптомы?
   - Например:
     * Низкая энергия + дефицит железа/B12 = возможная анемия
     * Плохой сон + дефицит магния = проблемы с расслаблением
     * Плохое настроение + дефицит витамина D = сезонная депрессия
     * Проблемы с пищеварением + низкая клетчатка = запоры

4. РЕКОМЕНДАЦИИ:
   - Конкретные продукты для улучшения показателей
   - Изменения в режиме питания
   - На какие микронутриенты обратить внимание

ФОРМАТ ОТВЕТА (строго JSON):
{{
  "overall_wellness_score": <средний балл 0-10>,
  "key_issues": [
    {{
      "issue": "название проблемы",
      "severity": "low/medium/high",
      "description": "описание"
    }}
  ],
  "correlations": [
    {{
      "pattern": "описание паттерна",
      "correlation_with": "питание/микронутриенты/сон",
      "confidence": "low/medium/high",
      "explanation": "объяснение связи"
    }}
  ],
  "micronutrient_insights": [
    {{
      "nutrient": "название микронутриента",
      "current_level": "дефицит/норма/избыток",
      "impact_on_wellness": "описание влияния",
      "recommendation": "рекомендация"
    }}
  ],
  "recommendations": [
    {{
      "category": "питание/режим/образ_жизни",
      "priority": "high/medium/low",
      "action": "конкретное действие",
      "expected_benefit": "ожидаемый эффект"
    }}
  ],
  "foods_to_increase": ["список продуктов"],
  "foods_to_decrease": ["список продуктов"],
  "summary": "краткое резюме анализа на русском языке"
}}

ВАЖНО:
- Будь конкретным и практичным
- Указывай научно обоснованные связи
- Учитывай индивидуальные особенности (пол, возраст)
- Если данных недостаточно для выводов, укажи это"""

        return prompt

    async def get_meal_correlation_insights(
        self,
        session: AsyncSession,
        meal_id: int
    ) -> Dict:
        """
        Получает инсайты о влиянии конкретного приема пищи на самочувствие

        Args:
            session: Async сессия БД
            meal_id: ID приема пищи

        Returns:
            Dict: Инсайты о влиянии еды
        """
        try:
            # Получаем записи о самочувствии для этого приема пищи
            result = await session.execute(
                select(WellnessLog)
                .where(WellnessLog.meal_id == meal_id)
                .order_by(WellnessLog.log_datetime)
            )
            wellness_logs = result.scalars().all()

            if not wellness_logs:
                return {
                    "status": "no_data",
                    "message": "Нет данных о самочувствии после этого приема пищи"
                }

            # Формируем статистику
            log = wellness_logs[0]  # Берем первую запись

            insights = {
                "wellness_score": log.get_wellness_score(),
                "time_after_meal": log.time_after_meal_minutes,
                "energy_level": log.energy_level,
                "digestive_comfort": log.digestive_comfort,
                "mood": log.mood,
                "physical_symptoms": log.physical_symptoms,
                "notes": log.notes
            }

            return insights

        except Exception as e:
            logger.error("Error getting meal correlation insights: {}", repr(e))
            return {
                "status": "error",
                "message": str(e)
            }
