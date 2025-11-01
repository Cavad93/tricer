"""
Сервис для анализа корреляций между питанием и самочувствием
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger
import numpy as np
from scipy import stats
from collections import defaultdict

from app.models.insight_fact import InsightFact
from app.models.wellness_log import WellnessLog
from app.models.meal import Meal, MealFood
from app.models.user import User
from app.services.claude_ai import ClaudeAIService
from app.services.web_search_service import WebSearchService


class CorrelationAnalysisService:
    """Сервис для анализа корреляций между едой и самочувствием"""

    def __init__(self):
        self.claude_service = ClaudeAIService()
        self.min_sample_size = 10  # Минимум 10 наблюдений
        self.min_confidence = 0.95  # 95% уверенность
        self.min_correlation = 0.6  # Минимальный коэффициент корреляции

    async def analyze_user_correlations(
        self,
        session: AsyncSession,
        user_id: int,
        days_back: int = 90
    ) -> List[InsightFact]:
        """
        Анализирует корреляции для пользователя за указанный период

        Args:
            session: Сессия БД
            user_id: ID пользователя
            days_back: Сколько дней назад анализировать

        Returns:
            Список новых найденных фактов
        """
        try:
            logger.info(f"Starting correlation analysis for user {user_id}")

            # Получаем данные
            start_date = datetime.now() - timedelta(days=days_back)

            # Получаем все приемы пищи с wellness logs
            meals_result = await session.execute(
                select(Meal)
                .options(selectinload(Meal.foods))
                .where(
                    and_(
                        Meal.user_id == user_id,
                        Meal.meal_date >= start_date.date()
                    )
                )
                .order_by(Meal.meal_time)
            )
            meals = list(meals_result.scalars().all())

            # Получаем все wellness logs
            wellness_result = await session.execute(
                select(WellnessLog)
                .where(
                    and_(
                        WellnessLog.user_id == user_id,
                        WellnessLog.log_datetime >= start_date
                    )
                )
                .order_by(WellnessLog.log_datetime)
            )
            wellness_logs = list(wellness_result.scalars().all())

            if not meals or not wellness_logs:
                logger.info(f"Insufficient data for user {user_id}: {len(meals)} meals, {len(wellness_logs)} wellness logs")
                return []

            # Группируем данные по продуктам
            food_wellness_pairs = await self._build_food_wellness_pairs(session, meals, wellness_logs)

            # Анализируем корреляции
            new_facts = []
            for food_name, data in food_wellness_pairs.items():
                if len(data['observations']) < self.min_sample_size:
                    continue

                # Анализируем каждую метрику wellness
                for metric in ['energy_level', 'mood', 'digestive_comfort', 'mental_clarity', 'stress_level']:
                    fact = await self._analyze_food_metric_correlation(
                        session,
                        user_id,
                        food_name,
                        metric,
                        data['observations']
                    )

                    if fact:
                        new_facts.append(fact)

            logger.info(f"Found {len(new_facts)} new correlation facts for user {user_id}")
            return new_facts

        except Exception as e:
            logger.error(f"Error analyzing correlations for user {user_id}: {repr(e)}", exc_info=True)
            return []

    async def _build_food_wellness_pairs(
        self,
        session: AsyncSession,
        meals: List[Meal],
        wellness_logs: List[WellnessLog]
    ) -> Dict[str, Dict]:
        """
        Строит пары "продукт-самочувствие" для анализа

        Returns:
            Dict[food_name, {
                'observations': List[{
                    'wellness_log': WellnessLog,
                    'meal': Meal,
                    'portion_size': float
                }],
                'category': str
            }]
        """
        food_data = defaultdict(lambda: {'observations': [], 'category': None})

        # Для каждого wellness log ищем связанный прием пищи
        for wlog in wellness_logs:
            if not wlog.meal_id:
                continue

            # Находим meal
            meal = next((m for m in meals if m.id == wlog.meal_id), None)
            if not meal:
                continue

            # Для каждого продукта в meal создаем наблюдение
            for meal_food in meal.foods:
                food_name = self._normalize_food_name(meal_food.name)

                food_data[food_name]['observations'].append({
                    'wellness_log': wlog,
                    'meal': meal,
                    'meal_food': meal_food,
                    'portion_size': meal_food.portion_size
                })

                # Сохраняем категорию (можно улучшить логику определения категории)
                if not food_data[food_name]['category']:
                    food_data[food_name]['category'] = self._categorize_food(meal_food.name)

        return dict(food_data)

    def _normalize_food_name(self, food_name: str) -> str:
        """
        Нормализует название продукта для группировки похожих продуктов
        Например: "Яблоко", "Яблоко зеленое", "Яблоко красное" -> "Яблоко"
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

        # Возвращаем с заглавной буквы
        return normalized.capitalize()

    def _categorize_food(self, food_name: str) -> str:
        """Определяет категорию продукта"""
        food_lower = food_name.lower()

        # Простая категоризация (можно улучшить)
        if any(word in food_lower for word in ['молоко', 'творог', 'сыр', 'йогурт', 'кефир']):
            return 'dairy'
        elif any(word in food_lower for word in ['мясо', 'курица', 'говядина', 'свинина', 'рыба']):
            return 'protein'
        elif any(word in food_lower for word in ['яблоко', 'банан', 'апельсин', 'ягод', 'фрукт']):
            return 'fruit'
        elif any(word in food_lower for word in ['овощ', 'салат', 'помидор', 'огурец', 'капуста']):
            return 'vegetable'
        elif any(word in food_lower for word in ['хлеб', 'каша', 'рис', 'макарон', 'крупа']):
            return 'grain'
        elif any(word in food_lower for word in ['сладк', 'шоколад', 'торт', 'печенье', 'конфет']):
            return 'sweet'
        else:
            return 'other'

    async def _analyze_food_metric_correlation(
        self,
        session: AsyncSession,
        user_id: int,
        food_name: str,
        metric: str,
        observations: List[Dict]
    ) -> Optional[InsightFact]:
        """
        Анализирует корреляцию между конкретным продуктом и метрикой самочувствия

        Returns:
            InsightFact если найдена значимая корреляция, иначе None
        """
        try:
            # Извлекаем значения метрики
            metric_values = []
            for obs in observations:
                wlog = obs['wellness_log']
                value = getattr(wlog, metric, None)
                if value is not None:
                    metric_values.append(value)

            if len(metric_values) < self.min_sample_size:
                return None

            # Вычисляем статистику
            mean_value = np.mean(metric_values)
            std_value = np.std(metric_values)

            # Сравниваем с общим средним для этой метрики у пользователя
            # Получаем все wellness logs пользователя для сравнения
            all_wellness = await session.execute(
                select(WellnessLog)
                .where(WellnessLog.user_id == user_id)
                .order_by(desc(WellnessLog.created_at))
                .limit(1000)
            )
            all_wellness_logs = list(all_wellness.scalars().all())

            all_metric_values = [
                getattr(wlog, metric)
                for wlog in all_wellness_logs
                if getattr(wlog, metric, None) is not None
            ]

            if len(all_metric_values) < self.min_sample_size:
                return None

            overall_mean = np.mean(all_metric_values)

            # Проводим t-test для проверки значимости различия
            # Проверяем, отличается ли среднее значение после употребления этого продукта
            # от общего среднего
            t_statistic, p_value = stats.ttest_1samp(metric_values, overall_mean)

            # Вычисляем уровень уверенности
            confidence = 1 - p_value

            # Проверяем критерии
            if confidence < self.min_confidence:
                return None

            # Вычисляем correlation coefficient (размер эффекта)
            # Используем Cohen's d для оценки размера эффекта
            cohens_d = (mean_value - overall_mean) / std_value if std_value > 0 else 0

            # Преобразуем Cohen's d в correlation coefficient (приблизительно)
            correlation = cohens_d / np.sqrt(cohens_d**2 + 4)

            if abs(correlation) < self.min_correlation:
                return None

            # Определяем направление влияния
            average_impact = mean_value - overall_mean
            if average_impact > 0.5:  # Улучшение больше чем на 0.5 балла
                impact_direction = "positive"
            elif average_impact < -0.5:  # Ухудшение больше чем на 0.5 балла
                impact_direction = "negative"
            else:
                return None  # Эффект слишком мал

            # Проверяем, не существует ли уже такой факт
            existing_fact = await session.execute(
                select(InsightFact).where(
                    and_(
                        InsightFact.user_id == user_id,
                        InsightFact.food_name == food_name,
                        InsightFact.wellness_metric == metric,
                        InsightFact.is_active == True
                    )
                )
            )
            if existing_fact.scalar_one_or_none():
                logger.debug(f"Fact already exists for {food_name} -> {metric}")
                return None

            # Получаем научное объяснение от AI
            scientific_explanation, sources = await self._get_scientific_explanation(
                food_name,
                metric,
                impact_direction,
                average_impact
            )

            # Создаем InsightFact
            fact = InsightFact(
                user_id=user_id,
                fact_type="food_wellness",
                food_name=food_name,
                food_category=observations[0].get('category'),
                wellness_metric=metric,
                correlation_coefficient=correlation,
                confidence_level=confidence,
                sample_size=len(metric_values),
                impact_direction=impact_direction,
                average_impact=average_impact,
                scientific_explanation=scientific_explanation,
                explanation_sources=sources,
                details={
                    "mean_value": float(mean_value),
                    "overall_mean": float(overall_mean),
                    "std_value": float(std_value),
                    "p_value": float(p_value),
                    "cohens_d": float(cohens_d)
                },
                is_verified=True,
                is_active=True,
                first_observed=min(obs['wellness_log'].log_datetime for obs in observations),
                first_detected=min(obs['wellness_log'].log_datetime for obs in observations),
                last_updated=datetime.now(),
                last_validated=datetime.now(),
                verified_at=datetime.now()
            )

            session.add(fact)
            await session.commit()
            await session.refresh(fact)

            logger.info(
                f"Created new insight fact: {food_name} -> {metric} "
                f"(correlation={correlation:.2f}, confidence={confidence:.2f}, n={len(metric_values)})"
            )

            return fact

        except Exception as e:
            logger.error(f"Error analyzing correlation for {food_name} -> {metric}: {repr(e)}", exc_info=True)
            return None

    async def _get_scientific_explanation(
        self,
        food_name: str,
        metric: str,
        impact_direction: str,
        average_impact: float
    ) -> Tuple[str, List[Dict]]:
        """
        Получает научное объяснение корреляции через AI и веб-поиск

        Returns:
            Tuple[explanation_text, sources]
        """
        try:
            # Названия метрик на русском для промпта
            metric_names = {
                "energy_level": "уровень энергии",
                "mood": "настроение",
                "digestive_comfort": "комфорт пищеварения",
                "mental_clarity": "ясность ума",
                "sleep_quality": "качество сна",
                "stress_level": "уровень стресса"
            }

            metric_display = metric_names.get(metric, metric)
            direction_text = "улучшает" if impact_direction == "positive" else "ухудшает"

            # Формируем запрос для веб-поиска
            search_query = f"{food_name} влияние на {metric_display} здоровье"

            # Ищем научные источники
            search_results = await WebSearchService.search_scientific_sources(search_query, max_results=3)

            # Формируем контекст из найденных источников
            sources_context = "\n\n".join([
                f"Источник {i+1}: {result.get('title', 'Без названия')}\n{result.get('snippet', '')}"
                for i, result in enumerate(search_results)
            ])

            # Создаем промпт для AI
            prompt = f"""Ты - эксперт по питанию и здоровью. Объясни научно, почему продукт "{food_name}" {direction_text} {metric_display}.

НАЙДЕННЫЕ НАУЧНЫЕ ИСТОЧНИКИ:
{sources_context if sources_context else "Источники не найдены, используй свои знания."}

СТАТИСТИКА:
- Средний эффект: {average_impact:+.1f} баллов по шкале 1-10
- Направление: {impact_direction}

ЗАДАЧА:
Предоставь краткое (2-3 предложения), научно обоснованное объяснение этой корреляции.
Упомяни конкретные механизмы (витамины, минералы, биоактивные вещества).

ВАЖНО:
- Будь точным и научным
- Не преувеличивай эффект
- Если данных недостаточно, честно скажи об этом
- Пиши на русском языке

ОТВЕТ (только объяснение, без дополнительного текста):"""

            # Отправляем запрос к Claude
            response = await self.claude_service.async_client.messages.create(
                model=self.claude_service.model,
                max_tokens=500,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            explanation = response.content[0].text.strip()

            # Формируем список источников
            sources = [
                {
                    "title": result.get('title'),
                    "url": result.get('url'),
                    "snippet": result.get('snippet')
                }
                for result in search_results
            ]

            return explanation, sources

        except Exception as e:
            logger.error(f"Error getting scientific explanation: {repr(e)}", exc_info=True)
            return "Требуется дополнительное исследование для объяснения этой корреляции.", []

    async def get_user_insights(
        self,
        session: AsyncSession,
        user_id: int,
        active_only: bool = True
    ) -> List[InsightFact]:
        """
        Получает все интересные факты пользователя

        Args:
            session: Сессия БД
            user_id: ID пользователя
            active_only: Только активные факты

        Returns:
            Список фактов
        """
        try:
            query = select(InsightFact).where(InsightFact.user_id == user_id)

            if active_only:
                query = query.where(InsightFact.is_active == True)

            query = query.order_by(desc(InsightFact.confidence_level))

            result = await session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"Error getting user insights: {repr(e)}", exc_info=True)
            return []

    async def revalidate_existing_facts(
        self,
        session: AsyncSession,
        user_id: int,
        days_back: int = 90
    ) -> Dict[str, int]:
        """
        Пересматривает существующие факты и деактивирует те, которые больше не подтверждаются

        Args:
            session: Сессия БД
            user_id: ID пользователя
            days_back: Сколько дней назад проверять

        Returns:
            Dict с статистикой: {"kept": X, "deactivated": Y}
        """
        try:
            stats = {"kept": 0, "deactivated": 0}

            # Получаем все активные факты
            existing_facts = await self.get_user_insights(session, user_id, active_only=True)

            if not existing_facts:
                return stats

            # Получаем данные
            start_date = datetime.now() - timedelta(days=days_back)

            meals_result = await session.execute(
                select(Meal)
                .options(selectinload(Meal.foods))
                .where(
                    and_(
                        Meal.user_id == user_id,
                        Meal.meal_date >= start_date.date()
                    )
                )
                .order_by(Meal.meal_time)
            )
            meals = list(meals_result.scalars().all())

            wellness_result = await session.execute(
                select(WellnessLog)
                .where(
                    and_(
                        WellnessLog.user_id == user_id,
                        WellnessLog.log_datetime >= start_date
                    )
                )
                .order_by(WellnessLog.log_datetime)
            )
            wellness_logs = list(wellness_result.scalars().all())

            # Строим пары
            food_wellness_pairs = await self._build_food_wellness_pairs(session, meals, wellness_logs)

            # Проверяем каждый факт
            for fact in existing_facts:
                # Ищем данные для этого продукта
                food_name_normalized = self._normalize_food_name(fact.food_name)

                # Ищем совпадение
                found_data = None
                for food_name, data in food_wellness_pairs.items():
                    if self._normalize_food_name(food_name) == food_name_normalized:
                        found_data = data
                        break

                if not found_data or len(found_data['observations']) < self.min_sample_size:
                    # Недостаточно данных - деактивируем
                    fact.is_active = False
                    fact.last_updated = datetime.now()
                    fact.last_validated = datetime.now()
                    stats["deactivated"] += 1
                    logger.info(f"Deactivated fact {fact.id}: insufficient data")
                    continue

                # Пересчитываем корреляцию
                metric_values = []
                for obs in found_data['observations']:
                    wlog = obs['wellness_log']
                    value = getattr(wlog, fact.wellness_metric, None)
                    if value is not None:
                        metric_values.append(value)

                if len(metric_values) < self.min_sample_size:
                    fact.is_active = False
                    fact.last_updated = datetime.now()
                    fact.last_validated = datetime.now()
                    stats["deactivated"] += 1
                    logger.info(f"Deactivated fact {fact.id}: insufficient metric data")
                    continue

                # Получаем общее среднее
                all_wellness = await session.execute(
                    select(WellnessLog)
                    .where(WellnessLog.user_id == user_id)
                    .order_by(desc(WellnessLog.created_at))
                    .limit(1000)
                )
                all_wellness_logs = list(all_wellness.scalars().all())

                all_metric_values = [
                    getattr(wlog, fact.wellness_metric)
                    for wlog in all_wellness_logs
                    if getattr(wlog, fact.wellness_metric, None) is not None
                ]

                if len(all_metric_values) < self.min_sample_size:
                    continue  # Оставляем как есть

                overall_mean = np.mean(all_metric_values)
                mean_value = np.mean(metric_values)

                # Проводим t-test
                t_statistic, p_value = stats.ttest_1samp(metric_values, overall_mean)
                confidence = 1 - p_value

                # Если больше не подтверждается - деактивируем
                if confidence < self.min_confidence:
                    fact.is_active = False
                    fact.last_updated = datetime.now()
                    fact.last_validated = datetime.now()
                    stats["deactivated"] += 1
                    logger.info(
                        f"Deactivated fact {fact.id}: confidence dropped to {confidence:.2f}"
                    )
                else:
                    # Обновляем статистику
                    fact.sample_size = len(metric_values)
                    fact.confidence_level = confidence
                    fact.average_impact = mean_value - overall_mean
                    fact.last_updated = datetime.now()
                    fact.last_validated = datetime.now()
                    stats["kept"] += 1

            await session.commit()
            logger.info(f"Revalidation complete for user {user_id}: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error revalidating facts: {repr(e)}", exc_info=True)
            return {"kept": 0, "deactivated": 0}

    async def analyze_all_users(
        self,
        session: AsyncSession,
        min_wellness_logs: int = 10
    ) -> Dict[str, int]:
        """
        Анализирует всех пользователей с достаточным количеством данных

        Args:
            session: Сессия БД
            min_wellness_logs: Минимум wellness logs для анализа

        Returns:
            Dict со статистикой: {"users_analyzed": X, "new_facts": Y, "deactivated": Z}
        """
        try:
            from app.models.user import User

            # Получаем всех пользователей с достаточным количеством wellness logs
            result = await session.execute(
                select(User.id)
                .join(WellnessLog, WellnessLog.user_id == User.id)
                .group_by(User.id)
                .having(func.count(WellnessLog.id) >= min_wellness_logs)
            )
            user_ids = [row[0] for row in result.all()]

            total_stats = {
                "users_analyzed": 0,
                "new_facts": 0,
                "facts_kept": 0,
                "facts_deactivated": 0
            }

            for user_id in user_ids:
                try:
                    # Пересматриваем существующие факты
                    revalidation_stats = await self.revalidate_existing_facts(
                        session, user_id, days_back=90
                    )
                    total_stats["facts_kept"] += revalidation_stats["kept"]
                    total_stats["facts_deactivated"] += revalidation_stats["deactivated"]

                    # Ищем новые корреляции
                    new_facts = await self.analyze_user_correlations(
                        session, user_id, days_back=90
                    )
                    total_stats["new_facts"] += len(new_facts)
                    total_stats["users_analyzed"] += 1

                    logger.info(
                        f"Analyzed user {user_id}: {len(new_facts)} new facts, "
                        f"{revalidation_stats['kept']} kept, {revalidation_stats['deactivated']} deactivated"
                    )

                except Exception as e:
                    logger.error(f"Error analyzing user {user_id}: {repr(e)}")
                    continue

            logger.info(f"Batch analysis complete: {total_stats}")
            return total_stats

        except Exception as e:
            logger.error(f"Error in analyze_all_users: {repr(e)}", exc_info=True)
            return {"users_analyzed": 0, "new_facts": 0, "facts_kept": 0, "facts_deactivated": 0}
