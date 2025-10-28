"""
Сервис для создания списка покупок с поиском цен
"""
from collections import defaultdict
from typing import Dict, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.meal_plan import MealPlan
from app.models.shopping_list import ShoppingList, ShoppingItem
from app.services.meal_plan_service import MealPlanService


class ShoppingListService:
    """Сервис для создания и управления списками покупок"""

    # Категории продуктов
    CATEGORIES = {
        # Овощи
        "овощи": ["помидор", "огурец", "перец", "лук", "чеснок", "картофель", "морковь",
                  "капуста", "свекла", "кабачок", "баклажан", "редис", "салат", "зелень"],

        # Фрукты и ягоды
        "фрукты": ["яблок", "банан", "апельсин", "груш", "виноград", "киви", "лимон",
                   "манго", "ананас", "персик", "абрикос", "слив", "ягод", "клубник",
                   "малин", "черник", "смородин"],

        # Мясо и птица
        "мясо": ["говяд", "свинин", "курица", "индейка", "фарш", "грудка", "филе",
                 "бедр", "крыль", "котлет", "стейк", "ребр"],

        # Рыба и морепродукты
        "рыба": ["рыб", "лосось", "семга", "форель", "тунец", "треска", "скумбрия",
                 "креветк", "кальмар", "мидии", "осьминог"],

        # Молочные продукты
        "молочные": ["молоко", "кефир", "йогурт", "творог", "сметана", "сливки",
                     "масло сливочное", "сыр", "ряженк"],

        # Крупы и макароны
        "крупы": ["рис", "гречка", "овсян", "пшено", "перловк", "макарон", "спагетти",
                  "лапша", "вермишель"],

        # Хлеб и выпечка
        "хлеб": ["хлеб", "батон", "булка", "лаваш", "питта", "багет"],

        # Бакалея
        "бакалея": ["мука", "сахар", "соль", "перец", "специи", "приправ", "уксус",
                    "масло растительное", "масло оливковое"],

        # Яйца
        "яйца": ["яйц"],

        # Орехи и сухофрукты
        "орехи": ["орех", "миндаль", "кешью", "арахис", "фундук", "изюм", "курага", "чернослив"],

        # Бобовые
        "бобовые": ["фасоль", "горох", "чечевиц", "нут", "соя"],

        # Напитки
        "напитки": ["вода", "сок", "чай", "кофе", "компот"],

        # Заморозка
        "заморозка": ["замороженн"],

        # Консервы
        "консервы": ["консерв", "тушенк"],
    }

    @staticmethod
    async def create_shopping_list(
        session: AsyncSession,
        meal_plan_id: int,
        search_prices: bool = True
    ) -> ShoppingList:
        """
        Создать список покупок для плана питания

        Args:
            session: Сессия БД
            meal_plan_id: ID плана питания
            search_prices: Искать ли цены в интернете

        Returns:
            ShoppingList: Созданный список покупок
        """
        # Получаем план питания
        meal_plan = await MealPlanService.get_meal_plan_by_id(session, meal_plan_id)
        if not meal_plan:
            raise ValueError(f"Meal plan {meal_plan_id} not found")

        # Получаем все дни плана
        days = await MealPlanService.get_meal_plan_days(session, meal_plan_id)

        # Агрегируем ингредиенты
        aggregated_ingredients = await ShoppingListService._aggregate_ingredients(session, days)

        # Создаем список покупок
        shopping_list = ShoppingList(
            meal_plan_id=meal_plan_id,
            total_cost=0.0,
            currency="RUB"
        )

        session.add(shopping_list)
        await session.flush()

        total_cost = 0.0

        # Создаем элементы списка покупок
        for product_name, data in aggregated_ingredients.items():
            quantity = data["quantity"]
            unit = data["unit"]

            # Определяем категорию
            category = ShoppingListService._categorize_product(product_name)

            # Оценка цены
            estimated_price = 0.0
            price_per_unit = 0.0
            shop_name = None
            shop_url = None

            if search_prices:
                try:
                    price_data = await ShoppingListService._search_product_price(
                        product_name,
                        quantity,
                        unit,
                        meal_plan.budget_category
                    )
                    estimated_price = price_data.get("price", 0.0)
                    price_per_unit = price_data.get("price_per_unit", 0.0)
                    shop_name = price_data.get("shop", None)
                    shop_url = price_data.get("url", None)

                    total_cost += estimated_price

                except Exception as e:
                    logger.warning(f"Failed to search price for {product_name}: {e}")

            shopping_item = ShoppingItem(
                shopping_list_id=shopping_list.id,
                category=category,
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                estimated_price=estimated_price,
                price_per_unit=price_per_unit,
                shop_name=shop_name,
                shop_url=shop_url
            )

            session.add(shopping_item)

        # Обновляем общую стоимость
        shopping_list.total_cost = round(total_cost, 2)

        await session.commit()
        logger.info(f"Shopping list created for meal plan {meal_plan_id}: {shopping_list.id}")

        return shopping_list

    @staticmethod
    async def _aggregate_ingredients(session: AsyncSession, days: List) -> Dict[str, Dict]:
        """
        Агрегировать ингредиенты из всех дней плана

        Args:
            session: Сессия БД
            days: Список дней плана питания

        Returns:
            Dict: Агрегированные ингредиенты {name: {quantity, unit}}
        """
        ingredients_map = defaultdict(lambda: {"quantity": 0.0, "unit": ""})

        for day in days:
            meals = await MealPlanService.get_day_meals(session, day.id)

            for meal in meals:
                if not meal.ingredients:
                    continue

                for ingredient in meal.ingredients:
                    name = ingredient.get("name", "").strip()
                    quantity = float(ingredient.get("quantity", 0))
                    unit = ingredient.get("unit", "").strip()

                    if not name:
                        continue

                    # Нормализуем единицы измерения
                    normalized_unit, normalized_quantity = ShoppingListService._normalize_units(
                        quantity, unit
                    )

                    # Если у нас уже есть этот продукт
                    if name in ingredients_map:
                        # Проверяем совместимость единиц
                        existing_unit = ingredients_map[name]["unit"]

                        if existing_unit == normalized_unit:
                            # Просто суммируем
                            ingredients_map[name]["quantity"] += normalized_quantity
                        else:
                            # Пытаемся конвертировать
                            converted_qty = ShoppingListService._try_convert_units(
                                normalized_quantity,
                                normalized_unit,
                                existing_unit
                            )

                            if converted_qty is not None:
                                ingredients_map[name]["quantity"] += converted_qty
                            else:
                                # Не удалось конвертировать, создаем отдельную запись
                                new_name = f"{name} ({normalized_unit})"
                                ingredients_map[new_name] = {
                                    "quantity": normalized_quantity,
                                    "unit": normalized_unit
                                }
                    else:
                        ingredients_map[name] = {
                            "quantity": normalized_quantity,
                            "unit": normalized_unit
                        }

        # Округляем количества
        for name in ingredients_map:
            ingredients_map[name]["quantity"] = round(ingredients_map[name]["quantity"], 1)

        return dict(ingredients_map)

    @staticmethod
    def _normalize_units(quantity: float, unit: str) -> Tuple[str, float]:
        """Нормализовать единицы измерения"""
        unit_lower = unit.lower().strip()

        # Граммы
        if unit_lower in ["г", "гр", "грамм", "грамм"]:
            return "г", quantity

        # Килограммы -> граммы
        if unit_lower in ["кг", "килограмм", "килограммов"]:
            return "г", quantity * 1000

        # Миллилитры
        if unit_lower in ["мл", "миллилитр", "миллилитров"]:
            return "мл", quantity

        # Литры -> миллилитры
        if unit_lower in ["л", "литр", "литров", "литра"]:
            return "мл", quantity * 1000

        # Штуки
        if unit_lower in ["шт", "шт.", "штук", "штука", "штуки", "шт", "pc", "pcs"]:
            return "шт", quantity

        # Чайная ложка -> граммы (приблизительно)
        if unit_lower in ["ч.л.", "ч л", "чайн ложка", "чайная ложка"]:
            return "г", quantity * 5

        # Столовая ложка -> граммы (приблизительно)
        if unit_lower in ["ст.л.", "ст л", "столов ложка", "столовая ложка"]:
            return "г", quantity * 15

        # Стакан -> миллилитры
        if unit_lower in ["стакан", "стакана", "стаканов"]:
            return "мл", quantity * 250

        # По умолчанию оставляем как есть
        return unit, quantity

    @staticmethod
    def _try_convert_units(quantity: float, from_unit: str, to_unit: str) -> float:
        """Попытка конвертировать между единицами измерения"""
        # Граммы <-> граммы
        if from_unit == "г" and to_unit == "г":
            return quantity

        # Миллилитры <-> миллилитры
        if from_unit == "мл" and to_unit == "мл":
            return quantity

        # Штуки <-> штуки
        if from_unit == "шт" and to_unit == "шт":
            return quantity

        # Не можем конвертировать
        return None

    @staticmethod
    def _categorize_product(product_name: str) -> str:
        """Определить категорию продукта"""
        product_lower = product_name.lower()

        for category, keywords in ShoppingListService.CATEGORIES.items():
            for keyword in keywords:
                if keyword in product_lower:
                    return category.capitalize()

        return "Другое"

    @staticmethod
    async def _search_product_price(
        product_name: str,
        quantity: float,
        unit: str,
        budget_category: str
    ) -> Dict:
        """
        Поиск цены продукта в интернете (ЗАГЛУШКА - требует WebSearch tool)

        В реальной реализации здесь будет использоваться WebSearch tool из Claude Code SDK
        для поиска цен на Яндекс.Маркете, Ozon, Wildberries и т.д.

        Args:
            product_name: Название продукта
            quantity: Количество
            unit: Единица измерения
            budget_category: Бюджетная категория

        Returns:
            Dict: Данные о цене {price, price_per_unit, shop, url}
        """
        # TODO: Реализовать поиск через WebSearch tool
        # Пока возвращаем примерные цены на основе бюджетной категории

        # Базовые цены за единицу (в рублях)
        base_prices = {
            "economy": {
                "г": 0.3,      # 300₽ за кг
                "мл": 0.1,     # 100₽ за литр
                "шт": 30.0,    # 30₽ за штуку
            },
            "normal": {
                "г": 0.5,      # 500₽ за кг
                "мл": 0.15,    # 150₽ за литр
                "шт": 50.0,    # 50₽ за штуку
            },
            "premium": {
                "г": 0.8,      # 800₽ за кг
                "мл": 0.25,    # 250₽ за литр
                "шт": 80.0,    # 80₽ за штуку
            }
        }

        # Корректировки для конкретных категорий продуктов
        price_multipliers = {
            "мясо": 2.0,
            "рыба": 2.5,
            "орех": 3.0,
            "сыр": 2.0,
            "масло": 1.5,
            "специи": 5.0,
        }

        # Определяем базовую цену
        budget_prices = base_prices.get(budget_category, base_prices["normal"])
        price_per_unit = budget_prices.get(unit, 1.0)

        # Применяем множители для конкретных продуктов
        product_lower = product_name.lower()
        for keyword, multiplier in price_multipliers.items():
            if keyword in product_lower:
                price_per_unit *= multiplier
                break

        # Рассчитываем общую цену
        total_price = round(price_per_unit * quantity, 2)

        return {
            "price": total_price,
            "price_per_unit": round(price_per_unit, 2),
            "shop": "Примерная оценка",
            "url": None
        }

    @staticmethod
    async def get_shopping_list(
        session: AsyncSession,
        shopping_list_id: int
    ) -> ShoppingList:
        """Получить список покупок по ID"""
        result = await session.execute(
            select(ShoppingList).where(ShoppingList.id == shopping_list_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_shopping_items(
        session: AsyncSession,
        shopping_list_id: int
    ) -> List[ShoppingItem]:
        """Получить все позиции списка покупок"""
        result = await session.execute(
            select(ShoppingItem)
            .where(ShoppingItem.shopping_list_id == shopping_list_id)
            .order_by(ShoppingItem.category, ShoppingItem.product_name)
        )
        return result.scalars().all()
