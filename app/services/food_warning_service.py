"""
Сервис для предупреждений о негативных эффектах продуктов
"""
from typing import List, Dict, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.insight_fact import InsightFact


class FoodWarningService:
    """Сервис для получения предупреждений о продуктах"""

    @staticmethod
    async def get_food_warnings(
        session: AsyncSession,
        user_id: int,
        food_names: List[str]
    ) -> List[Dict]:
        """
        Получает предупреждения для списка продуктов на основе персональных фактов

        Args:
            session: Сессия БД
            user_id: ID пользователя
            food_names: Список названий продуктов

        Returns:
            List[Dict] с предупреждениями:
                - food_name: Название продукта
                - warning_type: "negative" или "positive"
                - metric: Метрика самочувствия
                - message: Сообщение для пользователя
                - confidence: Уровень уверенности
        """
        try:
            warnings = []

            # Нормализуем названия продуктов для сравнения
            normalized_names = [FoodWarningService._normalize_food_name(name) for name in food_names]

            # Получаем все активные факты пользователя
            result = await session.execute(
                select(InsightFact).where(
                    and_(
                        InsightFact.user_id == user_id,
                        InsightFact.is_active == True
                    )
                ).order_by(InsightFact.confidence_level.desc())
            )
            insights = list(result.scalars().all())

            # Проверяем каждый продукт против фактов
            for food_name, normalized in zip(food_names, normalized_names):
                for insight in insights:
                    # Сравниваем нормализованные названия
                    insight_normalized = FoodWarningService._normalize_food_name(insight.food_name or "")

                    # Проверяем совпадение (точное или частичное)
                    if (normalized == insight_normalized or
                        normalized in insight_normalized or
                        insight_normalized in normalized):

                        # Формируем предупреждение
                        metric_names = {
                            "energy_level": "уровень энергии",
                            "mood": "настроение",
                            "digestive_comfort": "пищеварение",
                            "mental_clarity": "ясность ума",
                            "sleep_quality": "качество сна",
                            "stress_level": "уровень стресса"
                        }

                        metric = metric_names.get(insight.wellness_metric, insight.wellness_metric)
                        confidence = int(insight.confidence_level * 100)

                        if insight.impact_direction == "negative":
                            emoji = "⚠️"
                            effect = "может негативно повлиять на"
                        else:
                            emoji = "✅"
                            effect = "положительно влияет на"

                        message = f"{emoji} {insight.food_name} {effect} ваш(е) {metric}"

                        if insight.average_impact:
                            impact_str = f"{insight.average_impact:+.1f}"
                            message += f" (обычно {impact_str} баллов)"

                        message += f"\nДостоверность: {confidence}%"

                        if insight.scientific_explanation:
                            message += f"\n💡 {insight.scientific_explanation}"

                        warnings.append({
                            "food_name": food_name,
                            "warning_type": insight.impact_direction,
                            "metric": insight.wellness_metric,
                            "message": message,
                            "confidence": confidence,
                            "sample_size": insight.sample_size
                        })

            return warnings

        except Exception as e:
            logger.error(f"Error getting food warnings: {repr(e)}", exc_info=True)
            return []

    @staticmethod
    def _normalize_food_name(food_name: str) -> str:
        """
        Нормализует название продукта для сравнения
        """
        # Убираем лишние пробелы, приводим к нижнему регистру
        normalized = food_name.strip().lower()

        # Убираем распространенные уточнения
        words_to_remove = [
            'свежий', 'свежее', 'свежая',
            'жареный', 'жареное', 'жареная',
            'вареный', 'вареное', 'вареная',
            'тушеный', 'тушеное', 'тушеная',
            'сырой', 'сырое', 'сырая',
            'красный', 'красное', 'красная',
            'зеленый', 'зеленое', 'зеленая',
            'белый', 'белое', 'белая'
        ]

        for word in words_to_remove:
            normalized = normalized.replace(word, '').strip()

        return normalized

    @staticmethod
    def format_warnings_for_user(warnings: List[Dict]) -> Optional[str]:
        """
        Форматирует предупреждения для показа пользователю

        Args:
            warnings: Список предупреждений

        Returns:
            Отформатированный текст или None если предупреждений нет
        """
        if not warnings:
            return None

        # Разделяем на негативные и позитивные
        negative_warnings = [w for w in warnings if w["warning_type"] == "negative"]
        positive_warnings = [w for w in warnings if w["warning_type"] == "positive"]

        text_parts = []

        if negative_warnings:
            text_parts.append("⚠️ <b>Предупреждения:</b>\n")
            for warning in negative_warnings:
                text_parts.append(f"• {warning['message']}\n")
            text_parts.append("\n")

        if positive_warnings:
            text_parts.append("✅ <b>Положительные эффекты:</b>\n")
            for warning in positive_warnings:
                text_parts.append(f"• {warning['message']}\n")

        if text_parts:
            return "".join(text_parts)

        return None
