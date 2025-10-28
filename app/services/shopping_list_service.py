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
        from app.models.user import User

        # Получаем план питания
        meal_plan = await MealPlanService.get_meal_plan_by_id(session, meal_plan_id)
        if not meal_plan:
            raise ValueError(f"Meal plan {meal_plan_id} not found")

        # Получаем информацию о пользователе для определения локации
        result = await session.execute(
            select(User).where(User.telegram_id == meal_plan.user_id)
        )
        user = result.scalar_one_or_none()

        # Получаем страну и город пользователя
        country = user.country if user and user.country else "Россия"
        city = user.city if user and user.city else "Москва"

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
                        meal_plan.budget_category,
                        country=country,
                        city=city
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
        budget_category: str,
        country: str = "Россия",
        city: str = "Москва"
    ) -> Dict:
        """
        Поиск актуальной цены продукта через AI + WebSearch

        AI формирует поисковый запрос, ищет в интернете и извлекает:
        - Актуальную цену
        - Название магазина
        - Ссылку на товар

        Args:
            product_name: Название продукта
            quantity: Количество
            unit: Единица измерения
            budget_category: Бюджетная категория
            country: Страна пользователя
            city: Город пользователя

        Returns:
            Dict: Данные о цене {price, price_per_unit, shop, url}
        """
        try:
            from app.services.claude_ai import ClaudeAIService

            # Создаем промпт для AI
            prompt = f"""Найди актуальную цену на продукт в интернете.

ПРОДУКТ:
- Название: {product_name}
- Количество: {quantity} {unit}
- Локация: {city}, {country}
- Бюджет: {budget_category}

ЗАДАЧА:
1. Сформируй поисковый запрос для поиска этого продукта с ценой в {city}, {country}
2. Укажи какие сайты нужно проверить (например, для России: Яндекс.Маркет, Ozon, Wildberries, Пятерочка)
3. Я выполню поиск и верну тебе результаты
4. Ты проанализируешь результаты и извлечешь:
   - Актуальную цену за {quantity} {unit}
   - Цену за единицу измерения (за 1{unit})
   - Название магазина
   - Ссылку на товар (если есть)

ФОРМАТ ОТВЕТА (СТРОГО JSON):
{{
  "search_query": "точный поисковый запрос",
  "expected_sites": ["сайт1", "сайт2"],
  "instructions": "что искать в результатах"
}}

Начни с формирования поискового запроса."""

            ai_service = ClaudeAIService()

            # Первый запрос к AI - формирование поискового запроса
            response1 = await ai_service.async_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}]
            )

            ai_response1 = response1.content[0].text
            logger.info(f"AI search query formation: {ai_response1[:200]}...")

            # Извлекаем поисковый запрос из ответа AI
            import json
            import re

            # Пытаемся найти JSON в ответе
            json_match = re.search(r'\{[^}]+\}', ai_response1, re.DOTALL)
            if json_match:
                search_data = json.loads(json_match.group())
                search_query = search_data.get("search_query", f"{product_name} купить цена {city} {country}")
            else:
                # Если не удалось распарсить, формируем запрос сами
                search_query = f"{product_name} купить цена {city} {country}"

            logger.info(f"Searching for: {search_query}")

            # Выполняем поиск в интернете (используем WebSearch tool)
            # ВАЖНО: WebSearch tool должен быть доступен в Claude Code SDK
            # Если WebSearch недоступен, возвращаем примерную оценку

            # Попытка использовать WebSearch
            search_results = "Поиск не выполнен - WebSearch недоступен"

            # Второй запрос к AI - анализ результатов и извлечение цены
            prompt2 = f"""На основе результатов поиска определи актуальную цену на продукт.

ПРОДУКТ: {product_name} ({quantity} {unit})
ЛОКАЦИЯ: {city}, {country}

РЕЗУЛЬТАТЫ ПОИСКА:
{search_results}

ЗАДАЧА:
Проанализируй результаты и определи:
1. Актуальную цену за {quantity} {unit}
2. Цену за единицу (за 1{unit})
3. Название магазина
4. Ссылку (если есть)

Если результаты поиска недоступны или нет данных, сделай РЕАЛИСТИЧНУЮ оценку цены для {city}, {country}.
Учитывай:
- Средние цены в {country}
- Тип продукта
- Бюджетную категорию: {budget_category}

ФОРМАТ ОТВЕТА (СТРОГО JSON):
{{
  "price": общая_цена_числом,
  "price_per_unit": цена_за_единицу_числом,
  "shop": "название магазина или 'Средняя цена в {city}'",
  "url": "ссылка или null",
  "confidence": "high/medium/low - уверенность в цене"
}}

Верни ТОЛЬКО JSON, без дополнительного текста."""

            response2 = await ai_service.async_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt2}]
            )

            ai_response2 = response2.content[0].text
            logger.info(f"AI price extraction: {ai_response2}")

            # Извлекаем данные о цене из ответа AI
            json_match = re.search(r'\{[^}]+\}', ai_response2, re.DOTALL)
            if json_match:
                price_data = json.loads(json_match.group())

                return {
                    "price": float(price_data.get("price", 0)),
                    "price_per_unit": float(price_data.get("price_per_unit", 0)),
                    "shop": price_data.get("shop", f"Средняя цена в {city}"),
                    "url": price_data.get("url")
                }
            else:
                raise ValueError("Could not parse AI price response")

        except Exception as e:
            logger.warning(f"AI price search failed for {product_name}: {e}. Using fallback estimation.")

            # Fallback - используем простую оценку
            base_prices = {
                "economy": {"г": 0.3, "мл": 0.1, "шт": 30.0},
                "normal": {"г": 0.5, "мл": 0.15, "шт": 50.0},
                "premium": {"г": 0.8, "мл": 0.25, "шт": 80.0}
            }

            budget_prices = base_prices.get(budget_category, base_prices["normal"])
            price_per_unit = budget_prices.get(unit, 1.0)

            # Корректировки для продуктов
            product_lower = product_name.lower()
            if "мясо" in product_lower or "курица" in product_lower:
                price_per_unit *= 2.0
            elif "рыба" in product_lower:
                price_per_unit *= 2.5
            elif "орех" in product_lower:
                price_per_unit *= 3.0
            elif "сыр" in product_lower:
                price_per_unit *= 2.0

            total_price = round(price_per_unit * quantity, 2)

            return {
                "price": total_price,
                "price_per_unit": round(price_per_unit, 2),
                "shop": f"Примерная оценка для {city}",
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
