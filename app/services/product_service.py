"""
Сервис для работы с кэшем продуктов
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import func
from typing import Optional, List, Dict
from datetime import datetime
from loguru import logger

from app.models.product import Product


class ProductService:
    """
    Сервис для управления кэшем продуктов.

    Функции:
    - Поиск продукта в кэше по названию
    - Создание/обновление продукта
    - Получение статистики использования
    - Очистка неиспользуемых продуктов
    """

    @staticmethod
    async def find_by_name(
        session: AsyncSession,
        name: str
    ) -> Optional[Product]:
        """
        Найти продукт в кэше по названию.

        Args:
            session: Сессия БД
            name: Название продукта

        Returns:
            Product или None если не найден
        """
        try:
            name_hash = Product.generate_hash(name)

            result = await session.execute(
                select(Product).where(Product.name_hash == name_hash)
            )
            product = result.scalar_one_or_none()

            if product:
                # Обновить статистику использования
                product.usage_count += 1
                product.last_used_at = func.now()
                await session.commit()
                await session.refresh(product)

                logger.info(f"Product '{name}' found in cache (usage count: {product.usage_count})")

            return product

        except Exception as e:
            logger.error(f"Error finding product by name: {repr(e)}")
            await session.rollback()
            return None

    @staticmethod
    async def create_or_update(
        session: AsyncSession,
        name: str,
        calories: float,
        proteins: float,
        fats: float,
        carbs: float,
        micronutrients: Dict = None,
        source: str = "web_search",
        confidence: float = 1.0,
        category: str = None
    ) -> Product:
        """
        Создать новый продукт или обновить существующий в кэше.

        Args:
            session: Сессия БД
            name: Название продукта
            calories: Калории на 100г
            proteins: Белки на 100г (г)
            fats: Жиры на 100г (г)
            carbs: Углеводы на 100г (г)
            micronutrients: Словарь с микронутриентами
            source: Источник данных (web_search, ai_vision, user_input)
            confidence: Уверенность в данных (0.0-1.0)
            category: Категория продукта

        Returns:
            Созданный или обновленный Product
        """
        try:
            name_normalized = Product.normalize_name(name)
            name_hash = Product.generate_hash(name)

            # Проверить существование
            result = await session.execute(
                select(Product).where(Product.name_hash == name_hash)
            )
            product = result.scalar_one_or_none()

            if product:
                # Обновить существующий (если новые данные лучше)
                if confidence >= product.confidence:
                    product.calories = calories
                    product.proteins = proteins
                    product.fats = fats
                    product.carbs = carbs
                    product.micronutrients = micronutrients or {}
                    product.confidence = confidence
                    product.source = source
                    if category:
                        product.category = category

                product.usage_count += 1
                product.last_used_at = func.now()

                logger.info(f"Product '{name}' updated in cache (confidence: {confidence})")
            else:
                # Создать новый
                product = Product(
                    name=name,
                    name_normalized=name_normalized,
                    name_hash=name_hash,
                    calories=calories,
                    proteins=proteins,
                    fats=fats,
                    carbs=carbs,
                    micronutrients=micronutrients or {},
                    source=source,
                    confidence=confidence,
                    category=category,
                    usage_count=1
                )
                session.add(product)

                logger.info(f"Product '{name}' created in cache (source: {source})")

            await session.commit()
            await session.refresh(product)
            return product

        except Exception as e:
            logger.error(f"Error creating/updating product: {repr(e)}")
            await session.rollback()
            raise

    @staticmethod
    async def search_similar(
        session: AsyncSession,
        name: str,
        limit: int = 5
    ) -> List[Product]:
        """
        Найти похожие продукты по названию.

        Args:
            session: Сессия БД
            name: Название для поиска
            limit: Максимальное количество результатов

        Returns:
            Список похожих продуктов
        """
        try:
            name_normalized = Product.normalize_name(name)

            # Поиск по частичному совпадению normalized name
            result = await session.execute(
                select(Product)
                .where(Product.name_normalized.ilike(f"%{name_normalized}%"))
                .order_by(Product.usage_count.desc())
                .limit(limit)
            )
            products = result.scalars().all()

            logger.info(f"Found {len(products)} similar products for '{name}'")
            return products

        except Exception as e:
            logger.error(f"Error searching similar products: {repr(e)}")
            return []

    @staticmethod
    async def get_most_used(
        session: AsyncSession,
        limit: int = 100
    ) -> List[Product]:
        """
        Получить список наиболее используемых продуктов.

        Args:
            session: Сессия БД
            limit: Количество продуктов

        Returns:
            Список продуктов, отсортированных по usage_count
        """
        try:
            result = await session.execute(
                select(Product)
                .order_by(Product.usage_count.desc())
                .limit(limit)
            )
            return result.scalars().all()

        except Exception as e:
            logger.error(f"Error getting most used products: {repr(e)}")
            return []

    @staticmethod
    async def cleanup_unused(
        session: AsyncSession,
        min_usage_count: int = 1,
        days_inactive: int = 90
    ) -> int:
        """
        Удалить неиспользуемые продукты из кэша.

        Args:
            session: Сессия БД
            min_usage_count: Минимальное количество использований для сохранения
            days_inactive: Количество дней неактивности

        Returns:
            Количество удаленных продуктов
        """
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days_inactive)

            result = await session.execute(
                select(Product)
                .where(
                    Product.usage_count < min_usage_count,
                    Product.last_used_at < cutoff_date
                )
            )
            products_to_delete = result.scalars().all()

            count = len(products_to_delete)
            for product in products_to_delete:
                await session.delete(product)

            await session.commit()

            logger.info(f"Cleaned up {count} unused products from cache")
            return count

        except Exception as e:
            logger.error(f"Error cleaning up unused products: {repr(e)}")
            await session.rollback()
            return 0

    @staticmethod
    async def get_stats(session: AsyncSession) -> Dict:
        """
        Получить статистику по кэшу продуктов.

        Args:
            session: Сессия БД

        Returns:
            Словарь со статистикой
        """
        try:
            # Общее количество продуктов
            total_result = await session.execute(
                select(func.count(Product.id))
            )
            total_count = total_result.scalar()

            # Сумма использований
            usage_result = await session.execute(
                select(func.sum(Product.usage_count))
            )
            total_usage = usage_result.scalar() or 0

            # Продукты по источникам
            sources_result = await session.execute(
                select(Product.source, func.count(Product.id))
                .group_by(Product.source)
            )
            sources = dict(sources_result.all())

            # Средняя уверенность
            confidence_result = await session.execute(
                select(func.avg(Product.confidence))
            )
            avg_confidence = confidence_result.scalar() or 0

            stats = {
                "total_products": total_count,
                "total_usage": total_usage,
                "avg_usage_per_product": round(total_usage / total_count, 2) if total_count > 0 else 0,
                "by_source": sources,
                "avg_confidence": round(avg_confidence, 3) if avg_confidence else 0
            }

            logger.info(f"Product cache stats: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Error getting product stats: {repr(e)}")
            return {}
