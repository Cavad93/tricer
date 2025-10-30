"""
Сервис для генерации AI-поддержки при изменении веса
"""
from typing import Optional, List
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.meal import Meal
from app.services.claude_ai import ClaudeAIService
from loguru import logger


class WeightSupportService:
    """Сервис для генерации персонализированных сообщений при изменении веса"""

    @staticmethod
    async def generate_weight_change_message(
        user: User,
        old_weight: float,
        new_weight: float,
        session: AsyncSession
    ) -> str:
        """
        Генерирует персонализированное сообщение от AI при изменении веса

        Args:
            user: Объект пользователя
            old_weight: Предыдущий вес
            new_weight: Новый вес
            session: Сессия БД

        Returns:
            Персонализированное сообщение от AI
        """
        try:
            weight_diff = new_weight - old_weight

            # Получаем последние приемы пищи (последние 7 дней)
            week_ago = date.today() - timedelta(days=7)
            result = await session.execute(
                select(Meal)
                .options(selectinload(Meal.foods))
                .where(Meal.user_id == user.id, Meal.meal_date >= week_ago)
                .order_by(desc(Meal.meal_time))
                .limit(21)  # ~3 приема в день * 7 дней
            )
            recent_meals = result.scalars().all()

            # Формируем контекст о питании
            meals_summary = []
            for meal in recent_meals:
                foods_list = [f.name for f in meal.foods]
                meals_summary.append({
                    "date": meal.meal_date.strftime("%d.%m"),
                    "type": meal.meal_type.value if meal.meal_type else "прием пищи",
                    "calories": meal.calories,
                    "foods": foods_list[:5]  # Первые 5 продуктов
                })

            # Определяем направление изменения
            if abs(weight_diff) < 0.1:
                change_type = "stable"
            elif weight_diff < 0:
                change_type = "loss"
            else:
                change_type = "gain"

            # Готовим контекст для AI
            from app.services.nutrition_calc import NutritionCalculator
            bmi = NutritionCalculator.calculate_bmi(new_weight, user.height)
            min_healthy, max_healthy = NutritionCalculator.get_healthy_weight_range(user.height)

            # Формируем промпт для AI
            prompt = f"""
Пользователь обновил свой вес. Сгенерируй короткое персонализированное сообщение (2-3 предложения).

КОНТЕКСТ:
- Имя: {user.preferred_name or user.first_name}
- Предыдущий вес: {old_weight} кг
- Новый вес: {new_weight} кг
- Изменение: {weight_diff:+.1f} кг
- Целевой вес: {user.target_weight} кг
- Цель: {user.goal.value if user.goal else 'не указана'}
- ИМТ: {bmi:.1f}
- Здоровый диапазон веса: {min_healthy}-{max_healthy} кг

НЕДАВНЕЕ ПИТАНИЕ (последние 7 дней):
"""

            # Добавляем информацию о питании
            if meals_summary:
                for meal in meals_summary[:10]:  # Последние 10 приемов
                    prompt += f"- {meal['date']}, {meal['type']}: {meal['calories']} ккал, блюда: {', '.join(meal['foods'][:3])}\n"
            else:
                prompt += "- Нет данных о приемах пищи\n"

            # Инструкции в зависимости от изменения веса
            if change_type == "loss":
                prompt += """

ЗАДАЧА: Похвали пользователя за снижение веса!
- Используй эмодзи (👏, 🎉, 💪, ⭐)
- Подчеркни прогресс к цели
- Если цель еще не достигнута - мотивируй продолжать
- Если рацион был сбалансированным - отметь это
- Будь воодушевляющим и позитивным

Формат: 2-3 предложения, начни с эмодзи похвалы."""

            elif change_type == "gain":
                prompt += """

ЗАДАЧА: Поддержи пользователя при наборе веса!
- Используй эмодзи поддержки (🤗, 💚, 🌱)
- Объясни, что это нормально и часть процесса
- Проанализируй рацион - возможно, это мышечная масса или задержка жидкости
- Дай мягкую рекомендацию или ободри
- НЕ пугай и НЕ критикуй
- Объясни тактику: как можно вернуться к снижению веса (если это цель)

Формат: 2-3 предложения, начни с эмодзи поддержки."""

            else:  # stable
                prompt += """

ЗАДАЧА: Отметь стабильность веса!
- Используй эмодзи (⚖️, 👍)
- Если цель - поддержание, похвали за баланс
- Если цель - снижение/набор, мягко напомни о цели
- Будь позитивным

Формат: 2 предложения, начни с эмодзи."""

            # Генерируем сообщение через AI
            ai_response = await ClaudeAIService.chat(
                user_id=user.id,
                message=prompt,
                session=session,
                system_override="Ты поддерживающий AI-нутрициолог. Генерируй короткие персонализированные сообщения."
            )

            return ai_response.strip()

        except Exception as e:
            logger.error("Error generating weight change message: %s", str(e))
            # Fallback сообщения
            weight_diff = new_weight - old_weight

            if abs(weight_diff) < 0.1:
                return "⚖️ Вес стабилен! Продолжай в том же духе."
            elif weight_diff < 0:
                return f"👏 Отличная работа! Ты сбросил {abs(weight_diff):.1f} кг. Продолжай двигаться к своей цели!"
            else:
                return f"🤗 Не переживай! Небольшие колебания веса - это нормально. Главное - общий тренд и твое самочувствие."
