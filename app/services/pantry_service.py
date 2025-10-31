"""
Сервис для управления продуктами дома (кладовая/холодильник)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date, timedelta
from loguru import logger

from app.models.pantry import UserPantry, PantryUsageLog
from app.models.meal import Meal, MealFood
from app.models.meal_plan import PlannedMeal


class PantryService:
    """Сервис для управления продуктами дома"""

    @staticmethod
    async def add_product(
        session: AsyncSession,
        user_id: int,
        product_name: str,
        quantity: float,
        unit: str = "г",
        category: str = None,
        expiration_date: datetime = None,
        is_perishable: bool = False,
        source: str = "manual",
        notes: str = None
    ) -> UserPantry:
        """Добавить продукт в кладовую"""
        try:
            pantry_item = UserPantry(
                user_id=user_id,
                product_name=product_name,
                category=category,
                quantity=quantity,
                unit=unit,
                initial_quantity=quantity,
                expiration_date=expiration_date,
                is_perishable=is_perishable,
                source=source,
                notes=notes
            )

            session.add(pantry_item)
            await session.commit()
            await session.refresh(pantry_item)

            logger.info(f"Added product {product_name} for user {user_id}")
            return pantry_item

        except Exception as e:
            await session.rollback()
            logger.error("Error adding product for user {}: {}", user_id, repr(e))
            raise

    @staticmethod
    async def get_user_pantry(
        session: AsyncSession,
        user_id: int,
        include_empty: bool = False
    ) -> List[UserPantry]:
        """Получить все продукты пользователя"""
        query = select(UserPantry).where(UserPantry.user_id == user_id)

        if not include_empty:
            query = query.where(UserPantry.quantity > 0)

        query = query.order_by(UserPantry.category, UserPantry.product_name)

        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def update_product_quantity(
        session: AsyncSession,
        pantry_item_id: int,
        new_quantity: float,
        user_id: int = None
    ) -> bool:
        """Обновить количество продукта"""
        try:
            query = select(UserPantry).where(UserPantry.id == pantry_item_id)
            if user_id:
                query = query.where(UserPantry.user_id == user_id)

            result = await session.execute(query)
            item = result.scalar_one_or_none()

            if not item:
                return False

            item.quantity = new_quantity
            item.updated_at = datetime.now()

            await session.commit()
            logger.info(f"Updated quantity for product {item.product_name} to {new_quantity}")
            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error updating product quantity: {}", repr(e))
            return False

    @staticmethod
    async def deduct_product(
        session: AsyncSession,
        pantry_item_id: int,
        quantity_used: float,
        user_id: int = None,
        meal_id: int = None,
        planned_meal_id: int = None,
        usage_type: str = "manual"
    ) -> bool:
        """Вычесть использованное количество продукта"""
        try:
            query = select(UserPantry).where(UserPantry.id == pantry_item_id)
            if user_id:
                query = query.where(UserPantry.user_id == user_id)

            result = await session.execute(query)
            item = result.scalar_one_or_none()

            if not item:
                return False

            # Вычитаем количество
            new_quantity = max(0, item.quantity - quantity_used)
            item.quantity = new_quantity
            item.last_used_date = datetime.now()
            item.times_used += 1

            # Логируем использование
            usage_log = PantryUsageLog(
                pantry_item_id=pantry_item_id,
                meal_id=meal_id,
                planned_meal_id=planned_meal_id,
                quantity_used=quantity_used,
                unit=item.unit,
                usage_type=usage_type
            )
            session.add(usage_log)

            await session.commit()
            logger.info(f"Deducted {quantity_used}{item.unit} of {item.product_name}")
            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error deducting product: {}", repr(e))
            return False

    @staticmethod
    async def deduct_ingredients_from_meal(
        session: AsyncSession,
        user_id: int,
        meal_id: int
    ) -> Dict[str, int]:
        """
        Вычесть ингредиенты из кладовой на основе съеденного блюда из рациона

        Returns:
            Dict с результатами: {"found": 5, "deducted": 3, "not_found": 2}
        """
        try:
            # Получаем блюдо
            result = await session.execute(
                select(Meal).where(Meal.id == meal_id, Meal.user_id == user_id)
            )
            meal = result.scalar_one_or_none()

            if not meal:
                return {"error": "Meal not found"}

            # Загружаем продукты блюда
            await session.refresh(meal, ["foods"])

            stats = {"found": 0, "deducted": 0, "not_found": 0}

            for food in meal.foods:
                # Пытаемся найти ингредиенты в ingredients (если есть)
                if hasattr(food, 'ingredients') and food.ingredients:
                    for ingredient in food.ingredients:
                        stats["found"] += 1

                        # Ищем продукт в кладовой
                        ingredient_name = ingredient.get("name", "")
                        quantity = ingredient.get("quantity", 0)

                        pantry_result = await session.execute(
                            select(UserPantry).where(
                                and_(
                                    UserPantry.user_id == user_id,
                                    func.lower(UserPantry.product_name).like(f"%{ingredient_name.lower()}%"),
                                    UserPantry.quantity > 0
                                )
                            )
                        )
                        pantry_item = pantry_result.first()

                        if pantry_item:
                            pantry_item = pantry_item[0]
                            # Вычитаем
                            success = await PantryService.deduct_product(
                                session,
                                pantry_item.id,
                                quantity,
                                meal_id=meal_id,
                                usage_type="from_plan"
                            )
                            if success:
                                stats["deducted"] += 1
                        else:
                            stats["not_found"] += 1

            return stats

        except Exception as e:
            logger.error("Error deducting ingredients from meal {}: {}", meal_id, repr(e))
            return {"error": str(e)}

    @staticmethod
    async def check_products_for_plan(
        session: AsyncSession,
        user_id: int,
        planned_meals: List[PlannedMeal]
    ) -> Dict:
        """
        Проверить наличие продуктов для плана питания

        Returns:
            Dict с информацией: {
                "has_all": bool,
                "missing": [список недостающих продуктов],
                "low_stock": [список продуктов с низким запасом]
            }
        """
        try:
            # Получаем все продукты пользователя
            pantry_items = await PantryService.get_user_pantry(session, user_id)

            # Создаем словарь для быстрого поиска
            pantry_dict = {}
            for item in pantry_items:
                key = item.product_name.lower()
                pantry_dict[key] = item

            missing = []
            low_stock = []

            # Собираем все ингредиенты из плана
            all_ingredients = {}  # {название: количество}

            for planned_meal in planned_meals:
                if hasattr(planned_meal, 'ingredients') and planned_meal.ingredients:
                    for ingredient in planned_meal.ingredients:
                        name = ingredient.get("name", "").lower()
                        quantity = ingredient.get("quantity", 0)

                        if name in all_ingredients:
                            all_ingredients[name] += quantity
                        else:
                            all_ingredients[name] = quantity

            # Проверяем наличие
            for ingredient_name, required_qty in all_ingredients.items():
                found = False

                # Ищем в кладовой (частичное совпадение)
                for pantry_key, pantry_item in pantry_dict.items():
                    if ingredient_name in pantry_key or pantry_key in ingredient_name:
                        found = True

                        if pantry_item.quantity < required_qty:
                            low_stock.append({
                                "name": ingredient_name,
                                "required": required_qty,
                                "available": pantry_item.quantity,
                                "unit": pantry_item.unit
                            })
                        break

                if not found:
                    missing.append({
                        "name": ingredient_name,
                        "required": required_qty
                    })

            return {
                "has_all": len(missing) == 0 and len(low_stock) == 0,
                "missing": missing,
                "low_stock": low_stock
            }

        except Exception as e:
            logger.error("Error checking products for plan: {}", repr(e))
            return {"error": str(e)}

    @staticmethod
    async def estimate_days_supply(
        session: AsyncSession,
        user_id: int
    ) -> int:
        """
        Оценить на сколько дней хватит продуктов

        Простая эвристика на основе среднего потребления
        """
        try:
            pantry_items = await PantryService.get_user_pantry(session, user_id)

            if not pantry_items:
                return 0

            # Упрощенная оценка: считаем что в среднем нужно ~2кг продуктов в день
            total_weight_kg = 0

            for item in pantry_items:
                # Конвертируем в кг
                if item.unit in ["г", "g"]:
                    total_weight_kg += item.quantity / 1000
                elif item.unit in ["кг", "kg"]:
                    total_weight_kg += item.quantity
                elif item.unit in ["л", "l", "мл", "ml"]:
                    # Примерно 1л = 1кг для большинства жидкостей
                    total_weight_kg += item.quantity / 1000 if item.unit in ["мл", "ml"] else item.quantity

            # Грубая оценка: 2 кг в день
            estimated_days = int(total_weight_kg / 2)

            return max(1, estimated_days)  # Минимум 1 день

        except Exception as e:
            logger.error("Error estimating days supply: {}", repr(e))
            return 0

    @staticmethod
    async def delete_product(
        session: AsyncSession,
        pantry_item_id: int,
        user_id: int
    ) -> bool:
        """Удалить продукт из кладовой"""
        try:
            result = await session.execute(
                select(UserPantry).where(
                    and_(
                        UserPantry.id == pantry_item_id,
                        UserPantry.user_id == user_id
                    )
                )
            )
            item = result.scalar_one_or_none()

            if not item:
                return False

            await session.delete(item)
            await session.commit()

            logger.info(f"Deleted product {item.product_name} for user {user_id}")
            return True

        except Exception as e:
            await session.rollback()
            logger.error("Error deleting product: {}", repr(e))
            return False
