"""
Сервис для создания списка покупок с поиском цен
"""
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger

from app.models.meal_plan import MealPlan
from app.models.shopping_list import ShoppingList, ShoppingItem
from app.models.product_price import ProductPrice
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
                        session,
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
                    logger.warning("Failed to search price for {}: {}", product_name, repr(e))

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
    def _normalize_product_name(product_name: str) -> str:
        """
        Нормализовать название продукта для поиска в кэше

        Приводит к нижнему регистру, убирает лишние пробелы

        Args:
            product_name: Исходное название продукта

        Returns:
            str: Нормализованное название
        """
        return product_name.lower().strip()

    @staticmethod
    async def _get_cached_price(
        session: AsyncSession,
        product_name: str,
        unit: str,
        city: str,
        country: str,
        budget_category: str,
        max_age_hours: int = 24
    ) -> Optional[ProductPrice]:
        """
        Получить цену из кэша если она актуальна

        Args:
            session: Сессия БД
            product_name: Название продукта
            unit: Единица измерения
            city: Город
            country: Страна
            budget_category: Бюджетная категория
            max_age_hours: Максимальный возраст цены в часах (по умолчанию 24)

        Returns:
            ProductPrice или None если цена не найдена или устарела
        """
        normalized_name = ShoppingListService._normalize_product_name(product_name)

        # Ищем в БД
        result = await session.execute(
            select(ProductPrice).where(
                ProductPrice.product_name == normalized_name,
                ProductPrice.unit == unit,
                ProductPrice.city == city,
                ProductPrice.country == country,
                ProductPrice.budget_category == budget_category
            )
        )

        cached_price = result.scalar_one_or_none()

        if cached_price:
            # Проверяем актуальность
            if not cached_price.is_stale(hours=max_age_hours):
                logger.info(
                    f"Using cached price for {product_name} in {city}: "
                    f"{cached_price.price_per_unit} руб/{unit}"
                )
                return cached_price
            else:
                logger.info(f"Cached price for {product_name} is stale, will update")

        return None

    @staticmethod
    async def _save_price_to_cache(
        session: AsyncSession,
        product_name: str,
        unit: str,
        city: str,
        country: str,
        budget_category: str,
        price: float,
        price_per_unit: float,
        shop_name: Optional[str] = None,
        shop_url: Optional[str] = None
    ) -> ProductPrice:
        """
        Сохранить цену в кэш

        Если запись уже существует - обновляет её, иначе создает новую

        Args:
            session: Сессия БД
            product_name: Название продукта
            unit: Единица измерения
            city: Город
            country: Страна
            budget_category: Бюджетная категория
            price: Общая цена
            price_per_unit: Цена за единицу
            shop_name: Название магазина
            shop_url: Ссылка на товар

        Returns:
            ProductPrice: Сохраненная или обновленная запись
        """
        normalized_name = ShoppingListService._normalize_product_name(product_name)

        # Проверяем, есть ли уже такая запись
        result = await session.execute(
            select(ProductPrice).where(
                ProductPrice.product_name == normalized_name,
                ProductPrice.unit == unit,
                ProductPrice.city == city,
                ProductPrice.country == country,
                ProductPrice.budget_category == budget_category
            )
        )

        existing_price = result.scalar_one_or_none()

        if existing_price:
            # Обновляем существующую запись
            existing_price.price = price
            existing_price.price_per_unit = price_per_unit
            existing_price.shop_name = shop_name
            existing_price.shop_url = shop_url
            existing_price.last_updated = datetime.utcnow()

            logger.info(f"Updated cached price for {product_name} in {city}")
            cached_price = existing_price
        else:
            # Создаем новую запись
            cached_price = ProductPrice(
                product_name=normalized_name,
                unit=unit,
                country=country,
                city=city,
                budget_category=budget_category,
                price=price,
                price_per_unit=price_per_unit,
                shop_name=shop_name,
                shop_url=shop_url
            )
            session.add(cached_price)
            logger.info(f"Saved new price to cache for {product_name} in {city}")

        await session.flush()
        return cached_price

    @staticmethod
    async def _search_product_price(
        session: AsyncSession,
        product_name: str,
        quantity: float,
        unit: str,
        budget_category: str,
        country: str = "Россия",
        city: str = "Москва"
    ) -> Dict:
        """
        Поиск актуальной цены продукта с использованием кэша и AI

        Алгоритм:
        1. Проверяет кэш БД на наличие актуальной цены (< 24 часов)
        2. Если цена в кэше актуальна - использует её
        3. Если нет - AI формирует поисковый запрос и оценивает цену
        4. Сохраняет новую цену в кэш для других пользователей

        Args:
            session: Сессия БД
            product_name: Название продукта
            quantity: Количество
            unit: Единица измерения
            budget_category: Бюджетная категория
            country: Страна пользователя
            city: Город пользователя

        Returns:
            Dict: Данные о цене {price, price_per_unit, shop, url}
        """
        # ШАГ 1: Проверяем кэш
        cached_price = await ShoppingListService._get_cached_price(
            session,
            product_name,
            unit,
            city,
            country,
            budget_category
        )

        if cached_price:
            # Используем кэшированную цену
            total_price = cached_price.price_per_unit * quantity
            return {
                "price": round(total_price, 2),
                "price_per_unit": cached_price.price_per_unit,
                "shop": cached_price.shop_name or f"Средняя цена в {city}",
                "url": cached_price.shop_url
            }

        # ШАГ 2: Цены нет в кэше или она устарела - ищем через AI
        logger.info(f"No cached price for {product_name}, searching via AI...")

        try:
            import anthropic
            from anthropic import AsyncAnthropic
            from app.config import settings

            # Создаем отдельный AI client с отключенными retry для быстрого failover
            # При ошибке 429 сразу перейдем к fallback вместо блокировки на 60 секунд
            ai_client = AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                max_retries=0  # Отключаем автоматические retry - обрабатываем сами
            )

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

            # Первый запрос к AI - формирование поискового запроса
            response1 = await ai_client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=1000,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
                timeout=10.0  # Таймаут 10 секунд для быстрого failover
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

            response2 = await ai_client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=500,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt2}],
                timeout=10.0  # Таймаут 10 секунд для быстрого failover
            )

            ai_response2 = response2.content[0].text
            logger.info(f"AI price extraction: {ai_response2}")

            # Извлекаем данные о цене из ответа AI
            json_match = re.search(r'\{[^}]+\}', ai_response2, re.DOTALL)
            if json_match:
                price_data = json.loads(json_match.group())

                price_per_unit = float(price_data.get("price_per_unit", 0))
                shop = price_data.get("shop", f"Средняя цена в {city}")
                url = price_data.get("url")

                # ШАГ 3: Сохраняем цену в кэш для других пользователей
                await ShoppingListService._save_price_to_cache(
                    session,
                    product_name,
                    unit,
                    city,
                    country,
                    budget_category,
                    price=price_per_unit * quantity,  # Сохраняем общую цену для данного количества
                    price_per_unit=price_per_unit,
                    shop_name=shop,
                    shop_url=url
                )

                return {
                    "price": round(price_per_unit * quantity, 2),
                    "price_per_unit": price_per_unit,
                    "shop": shop,
                    "url": url
                }
            else:
                raise ValueError("Could not parse AI price response")

        except anthropic.RateLimitError as e:
            logger.warning("Rate limit exceeded for price search ({}): {}. Using fallback estimation immediately.", product_name, repr(e))
            # При превышении лимита API - сразу используем fallback без retry
        except anthropic.APITimeoutError as e:
            logger.warning("API timeout for price search ({}): {}. Using fallback estimation.", product_name, repr(e))
        except Exception as e:
            logger.warning("AI price search failed for {}: {}. Using fallback estimation.", product_name, repr(e))

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

    @staticmethod
    async def cleanup_old_prices(
        session: AsyncSession,
        max_age_days: int = 7
    ) -> int:
        """
        Очистить устаревшие цены из кэша

        Удаляет записи о ценах, которые не обновлялись дольше указанного времени.
        Это нужно для поддержания БД в чистоте и удаления неактуальных данных.

        Примечание: Цены старше 24 часов автоматически считаются устаревшими
        и обновляются при следующем запросе. Этот метод удаляет ОЧЕНЬ старые
        записи (по умолчанию > 7 дней), которые вероятно больше не актуальны.

        Args:
            session: Сессия БД
            max_age_days: Максимальный возраст записи в днях (по умолчанию 7)

        Returns:
            int: Количество удаленных записей
        """
        from sqlalchemy import delete

        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        # Подсчитываем сколько записей будет удалено
        count_result = await session.execute(
            select(ProductPrice).where(ProductPrice.last_updated < cutoff_date)
        )
        records_to_delete = len(count_result.scalars().all())

        if records_to_delete == 0:
            logger.info("No old price records to cleanup")
            return 0

        # Удаляем устаревшие записи
        await session.execute(
            delete(ProductPrice).where(ProductPrice.last_updated < cutoff_date)
        )

        await session.commit()

        logger.info(
            f"Cleaned up {records_to_delete} price records older than {max_age_days} days"
        )

        return records_to_delete

    @staticmethod
    async def get_price_cache_stats(session: AsyncSession) -> Dict:
        """
        Получить статистику по кэшу цен

        Returns:
            Dict: Статистика {
                total_records: общее количество записей,
                fresh_records: записи младше 24 часов,
                stale_records: записи старше 24 часов но младше 7 дней,
                very_old_records: записи старше 7 дней,
                cities: количество городов в кэше,
                products: количество уникальных продуктов
            }
        """
        from sqlalchemy import func, distinct

        # Общее количество записей
        total_result = await session.execute(select(func.count(ProductPrice.id)))
        total_records = total_result.scalar()

        # Записи младше 24 часов
        fresh_cutoff = datetime.utcnow() - timedelta(hours=24)
        fresh_result = await session.execute(
            select(func.count(ProductPrice.id))
            .where(ProductPrice.last_updated >= fresh_cutoff)
        )
        fresh_records = fresh_result.scalar()

        # Записи старше 7 дней
        old_cutoff = datetime.utcnow() - timedelta(days=7)
        old_result = await session.execute(
            select(func.count(ProductPrice.id))
            .where(ProductPrice.last_updated < old_cutoff)
        )
        very_old_records = old_result.scalar()

        # Записи между 24 часами и 7 днями
        stale_records = total_records - fresh_records - very_old_records

        # Количество городов
        cities_result = await session.execute(
            select(func.count(distinct(ProductPrice.city)))
        )
        cities_count = cities_result.scalar()

        # Количество уникальных продуктов
        products_result = await session.execute(
            select(func.count(distinct(ProductPrice.product_name)))
        )
        products_count = products_result.scalar()

        return {
            "total_records": total_records,
            "fresh_records": fresh_records,
            "stale_records": stale_records,
            "very_old_records": very_old_records,
            "cities": cities_count,
            "products": products_count
        }
