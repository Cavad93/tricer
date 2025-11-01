"""
Сервис для статистики и визуализации корреляций между питанием и самочувствием
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, date
import json
import csv
import io
from collections import defaultdict

from app.models.insight_fact import InsightFact
from app.models.wellness_log import WellnessLog
from app.models.meal import Meal, MealFood
from loguru import logger


class InsightStatisticsService:
    """Сервис для статистики и визуализации интересных фактов"""

    @staticmethod
    async def get_correlation_timeline(
        session: AsyncSession,
        user_id: int,
        food_name: str,
        wellness_metric: str,
        days_back: int = 90
    ) -> Dict:
        """
        Получить временную линию корреляции между продуктом и показателем самочувствия

        Args:
            session: Сессия БД
            user_id: ID пользователя
            food_name: Название продукта
            wellness_metric: Метрика самочувствия (energy_level, mood, etc.)
            days_back: Сколько дней назад смотреть

        Returns:
            Словарь с данными для построения графика
        """
        start_date = datetime.now() - timedelta(days=days_back)

        # Получаем все wellness logs с этим продуктом
        result = await session.execute(
            select(WellnessLog, Meal)
            .join(Meal, WellnessLog.meal_id == Meal.id)
            .join(MealFood, MealFood.meal_id == Meal.id)
            .where(
                and_(
                    WellnessLog.user_id == user_id,
                    WellnessLog.log_datetime >= start_date,
                    func.lower(MealFood.name).contains(food_name.lower())
                )
            )
            .order_by(WellnessLog.log_datetime)
        )
        logs_with_food = result.all()

        # Получаем все wellness logs БЕЗ этого продукта
        result_without = await session.execute(
            select(WellnessLog)
            .outerjoin(Meal, WellnessLog.meal_id == Meal.id)
            .outerjoin(MealFood, MealFood.meal_id == Meal.id)
            .where(
                and_(
                    WellnessLog.user_id == user_id,
                    WellnessLog.log_datetime >= start_date,
                    or_(
                        WellnessLog.meal_id.is_(None),
                        ~func.lower(MealFood.name).contains(food_name.lower())
                    )
                )
            )
            .order_by(WellnessLog.log_datetime)
        )
        logs_without_food = result_without.scalars().all()

        # Формируем данные для графика
        timeline_with = []
        timeline_without = []

        for wellness_log, meal in logs_with_food:
            metric_value = getattr(wellness_log, wellness_metric, None)
            if metric_value is not None:
                timeline_with.append({
                    "date": wellness_log.log_datetime.isoformat(),
                    "value": metric_value,
                    "meal_time": meal.meal_time.isoformat() if meal.meal_time else None
                })

        for wellness_log in logs_without_food:
            metric_value = getattr(wellness_log, wellness_metric, None)
            if metric_value is not None:
                timeline_without.append({
                    "date": wellness_log.log_datetime.isoformat(),
                    "value": metric_value
                })

        # Вычисляем средние значения
        avg_with = sum(d["value"] for d in timeline_with) / len(timeline_with) if timeline_with else 0
        avg_without = sum(d["value"] for d in timeline_without) / len(timeline_without) if timeline_without else 0

        return {
            "food_name": food_name,
            "wellness_metric": wellness_metric,
            "timeline_with_food": timeline_with,
            "timeline_without_food": timeline_without,
            "average_with_food": round(avg_with, 1),
            "average_without_food": round(avg_without, 1),
            "difference": round(avg_with - avg_without, 1),
            "sample_size_with": len(timeline_with),
            "sample_size_without": len(timeline_without)
        }

    @staticmethod
    async def get_fact_history(
        session: AsyncSession,
        user_id: int,
        food_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Получить историю изменений фактов о корреляциях

        Args:
            session: Сессия БД
            user_id: ID пользователя
            food_name: Фильтр по продукту (опционально)

        Returns:
            Список изменений фактов
        """
        query = select(InsightFact).where(InsightFact.user_id == user_id)

        if food_name:
            query = query.where(func.lower(InsightFact.food_name).contains(food_name.lower()))

        query = query.order_by(desc(InsightFact.updated_at))

        result = await session.execute(query)
        facts = result.scalars().all()

        history = []
        for fact in facts:
            history.append({
                "id": fact.id,
                "food_name": fact.food_name,
                "wellness_metric": fact.wellness_metric,
                "correlation_coefficient": fact.correlation_coefficient,
                "confidence_level": fact.confidence_level,
                "impact_direction": fact.impact_direction,
                "is_active": fact.is_active,
                "created_at": fact.created_at.isoformat(),
                "updated_at": fact.updated_at.isoformat(),
                "first_detected": fact.first_detected.isoformat() if fact.first_detected else None,
                "last_validated": fact.last_validated.isoformat() if fact.last_validated else None,
                "sample_size": fact.sample_size
            })

        return history

    @staticmethod
    async def get_summary_statistics(
        session: AsyncSession,
        user_id: int
    ) -> Dict:
        """
        Получить сводную статистику по всем фактам пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя

        Returns:
            Сводная статистика
        """
        result = await session.execute(
            select(InsightFact).where(InsightFact.user_id == user_id)
        )
        all_facts = result.scalars().all()

        active_facts = [f for f in all_facts if f.is_active]
        inactive_facts = [f for f in all_facts if not f.is_active]

        # Группировка по типу влияния
        positive_facts = [f for f in active_facts if f.impact_direction == "positive"]
        negative_facts = [f for f in active_facts if f.impact_direction == "negative"]
        neutral_facts = [f for f in active_facts if f.impact_direction == "neutral"]

        # Группировка по метрикам
        metrics_distribution = defaultdict(int)
        for fact in active_facts:
            metrics_distribution[fact.wellness_metric] += 1

        # Топ продуктов с наибольшим влиянием
        top_positive = sorted(
            positive_facts,
            key=lambda f: f.confidence_level,
            reverse=True
        )[:5]

        top_negative = sorted(
            negative_facts,
            key=lambda f: f.confidence_level,
            reverse=True
        )[:5]

        # Средняя достоверность
        avg_confidence = sum(f.confidence_level for f in active_facts) / len(active_facts) if active_facts else 0

        return {
            "total_facts": len(all_facts),
            "active_facts": len(active_facts),
            "inactive_facts": len(inactive_facts),
            "positive_facts": len(positive_facts),
            "negative_facts": len(negative_facts),
            "neutral_facts": len(neutral_facts),
            "metrics_distribution": dict(metrics_distribution),
            "top_positive_foods": [
                {
                    "food_name": f.food_name,
                    "metric": f.wellness_metric,
                    "confidence": f.confidence_level
                }
                for f in top_positive
            ],
            "top_negative_foods": [
                {
                    "food_name": f.food_name,
                    "metric": f.wellness_metric,
                    "confidence": f.confidence_level
                }
                for f in top_negative
            ],
            "average_confidence": avg_confidence
        }

    @staticmethod
    async def export_facts_to_json(
        session: AsyncSession,
        user_id: int,
        active_only: bool = False
    ) -> str:
        """
        Экспортировать факты в JSON формат

        Args:
            session: Сессия БД
            user_id: ID пользователя
            active_only: Только активные факты

        Returns:
            JSON строка с фактами
        """
        query = select(InsightFact).where(InsightFact.user_id == user_id)

        if active_only:
            query = query.where(InsightFact.is_active == True)

        query = query.order_by(desc(InsightFact.confidence_level))

        result = await session.execute(query)
        facts = result.scalars().all()

        export_data = {
            "export_date": datetime.now().isoformat(),
            "user_id": user_id,
            "total_facts": len(facts),
            "facts": []
        }

        for fact in facts:
            export_data["facts"].append({
                "food_name": fact.food_name,
                "wellness_metric": fact.wellness_metric,
                "impact_direction": fact.impact_direction,
                "correlation_coefficient": fact.correlation_coefficient,
                "confidence_level": fact.confidence_level,
                "sample_size": fact.sample_size,
                "scientific_explanation": fact.scientific_explanation,
                "is_active": fact.is_active,
                "created_at": fact.created_at.isoformat(),
                "updated_at": fact.updated_at.isoformat(),
                "first_detected": fact.first_detected.isoformat() if fact.first_detected else None,
                "last_validated": fact.last_validated.isoformat() if fact.last_validated else None
            })

        return json.dumps(export_data, ensure_ascii=False, indent=2)

    @staticmethod
    async def export_facts_to_csv(
        session: AsyncSession,
        user_id: int,
        active_only: bool = False
    ) -> str:
        """
        Экспортировать факты в CSV формат

        Args:
            session: Сессия БД
            user_id: ID пользователя
            active_only: Только активные факты

        Returns:
            CSV строка с фактами
        """
        query = select(InsightFact).where(InsightFact.user_id == user_id)

        if active_only:
            query = query.where(InsightFact.is_active == True)

        query = query.order_by(desc(InsightFact.confidence_level))

        result = await session.execute(query)
        facts = result.scalars().all()

        # Создаем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output)

        # Заголовки
        writer.writerow([
            "Продукт",
            "Метрика самочувствия",
            "Направление влияния",
            "Коэффициент корреляции",
            "Достоверность (%)",
            "Размер выборки",
            "Активен",
            "Дата создания",
            "Последняя проверка"
        ])

        # Данные
        for fact in facts:
            writer.writerow([
                fact.food_name,
                fact.wellness_metric,
                fact.impact_direction,
                round(fact.correlation_coefficient, 3),
                round(fact.confidence_level * 100, 1),
                fact.sample_size,
                "Да" if fact.is_active else "Нет",
                fact.created_at.strftime("%Y-%m-%d %H:%M") if fact.created_at else "",
                fact.last_validated.strftime("%Y-%m-%d %H:%M") if fact.last_validated else ""
            ])

        return output.getvalue()

    @staticmethod
    def generate_text_graph(
        data: List[Tuple[str, float]],
        max_width: int = 20,
        show_values: bool = True
    ) -> str:
        """
        Генерирует текстовый график (для Telegram)

        Args:
            data: Список кортежей (label, value)
            max_width: Максимальная ширина графика в символах
            show_values: Показывать значения

        Returns:
            Текстовый график
        """
        if not data:
            return "Нет данных для отображения"

        max_value = max(abs(v) for _, v in data)
        if max_value == 0:
            max_value = 1

        lines = []
        for label, value in data:
            # Вычисляем длину бара
            bar_length = int((abs(value) / max_value) * max_width)

            # Создаем бар
            if value >= 0:
                bar = "█" * bar_length
                line = f"{label}: {bar}"
            else:
                bar = "▓" * bar_length
                line = f"{label}: {bar}"

            # Добавляем значение
            if show_values:
                line += f" {value:.1f}"

            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    async def get_correlation_graph_text(
        session: AsyncSession,
        user_id: int,
        top_n: int = 10
    ) -> str:
        """
        Получить текстовый график топ корреляций

        Args:
            session: Сессия БД
            user_id: ID пользователя
            top_n: Количество топ фактов

        Returns:
            Текстовый график
        """
        result = await session.execute(
            select(InsightFact)
            .where(
                and_(
                    InsightFact.user_id == user_id,
                    InsightFact.is_active == True
                )
            )
            .order_by(desc(InsightFact.confidence_level))
            .limit(top_n)
        )
        facts = result.scalars().all()

        if not facts:
            return "📊 Пока недостаточно данных для графика корреляций"

        metric_names = {
            "energy_level": "Энергия",
            "mood": "Настроение",
            "digestive_comfort": "Пищеварение",
            "mental_clarity": "Ясность ума",
            "sleep_quality": "Сон",
            "stress_level": "Стресс"
        }

        graph_data = []
        for fact in facts:
            metric = metric_names.get(fact.wellness_metric, fact.wellness_metric)
            label = f"{fact.food_name[:15]} ({metric})"

            # Коэффициент корреляции от -1 до 1, конвертируем в влияние
            if fact.impact_direction == "positive":
                value = fact.correlation_coefficient * 10
            else:
                value = -fact.correlation_coefficient * 10

            graph_data.append((label, value))

        graph_text = InsightStatisticsService.generate_text_graph(
            graph_data,
            max_width=15,
            show_values=True
        )

        header = "📊 <b>Топ корреляций продуктов и самочувствия</b>\n\n"
        header += "✅ Положительное влияние | ❌ Отрицательное влияние\n\n"

        return header + f"<code>{graph_text}</code>"
