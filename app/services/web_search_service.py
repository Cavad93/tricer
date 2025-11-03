"""
Сервис для веб-поиска пищевой ценности блюд с использованием Haiku 4.5
"""
import aiohttp
import asyncio
from typing import Dict, List, Optional
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
import json
import re

from app.config import settings
from app.services.product_service import ProductService
from app.services.claude_ai import ClaudeAIService


class WebSearchService:
    """
    Сервис для поиска данных о пищевой ценности продуктов.

    Использует:
    1. Кэш продуктов (ProductService) - мгновенный ответ для известных продуктов
    2. DuckDuckGo HTML поиск + Claude Haiku 4.5 - извлечение данных из веба
    3. Сохранение результатов в кэш для будущих запросов
    """

    @staticmethod
    async def search_nutrition_data(
        product_name: str,
        session: AsyncSession
    ) -> Optional[Dict]:
        """
        Поиск пищевой ценности продукта с кэшированием.

        Workflow:
        1. Проверка кэша (ProductService)
        2. Если нет в кэше → поиск в DuckDuckGo
        3. Анализ HTML через Haiku 4.5
        4. Сохранение в кэш

        Args:
            product_name: Название продукта
            session: Сессия БД для работы с кэшем

        Returns:
            Dict с КБЖУ и микронутриентами или None
        """
        try:
            # 1. Проверка кэша
            logger.info(f"🔍 Searching nutrition data for: {product_name}")
            cached_product = await ProductService.find_by_name(session, product_name)

            if cached_product:
                logger.info(f"✅ Product '{product_name}' found in cache!")
                return {
                    "found": True,
                    "source": "cache",
                    "product_name": cached_product.name,
                    "per_100g": {
                        "calories": cached_product.calories,
                        "proteins": cached_product.proteins,
                        "fats": cached_product.fats,
                        "carbs": cached_product.carbs
                    },
                    "micronutrients": cached_product.micronutrients,
                    "confidence": cached_product.confidence,
                    "usage_count": cached_product.usage_count
                }

            # 2. Поиск в интернете
            logger.info(f"📡 Product not in cache, searching web...")
            html_content = await WebSearchService._fetch_duckduckgo_html(product_name)

            if not html_content:
                logger.warning(f"⚠️ No HTML content found for '{product_name}'")
                return None

            # 3. Анализ HTML через Haiku 4.5
            logger.info(f"🤖 Analyzing HTML with Haiku 4.5...")
            nutrition_data = await WebSearchService._extract_nutrition_with_ai(
                product_name,
                html_content
            )

            if not nutrition_data or not nutrition_data.get("found"):
                logger.warning(f"⚠️ Failed to extract nutrition data for '{product_name}'")
                return None

            # 4. Сохранение в кэш
            logger.info(f"💾 Saving '{product_name}' to cache...")
            await ProductService.create_or_update(
                session=session,
                name=product_name,
                calories=nutrition_data["per_100g"]["calories"],
                proteins=nutrition_data["per_100g"]["proteins"],
                fats=nutrition_data["per_100g"]["fats"],
                carbs=nutrition_data["per_100g"]["carbs"],
                micronutrients=nutrition_data.get("micronutrients", {}),
                source="web_search",
                confidence=nutrition_data.get("confidence", 0.8),
                category=nutrition_data.get("category")
            )

            logger.info(f"✅ Successfully processed '{product_name}'")
            return nutrition_data

        except Exception as e:
            logger.error(f"❌ Error searching nutrition data for '{product_name}': {repr(e)}")
            return None

    @staticmethod
    async def _fetch_duckduckgo_html(product_name: str) -> Optional[str]:
        """
        Получить HTML результатов поиска DuckDuckGo.

        Args:
            product_name: Название продукта

        Returns:
            HTML содержимое или None
        """
        try:
            # Формируем поисковый запрос
            search_query = f"{product_name} калории КБЖУ пищевая ценность состав витамины минералы"
            encoded_query = search_query.replace(" ", "+")

            # URL для HTML версии DuckDuckGo
            ddg_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

            async with aiohttp.ClientSession() as client_session:
                async with client_session.get(
                    ddg_url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                ) as response:
                    if response.status == 200:
                        html_text = await response.text()

                        # Проверяем, что получили осмысленный результат
                        if len(html_text) > 1000:
                            logger.info(f"✅ Fetched {len(html_text)} bytes of HTML from DuckDuckGo")
                            return html_text
                        else:
                            logger.warning(f"⚠️ HTML content too short: {len(html_text)} bytes")
                            return None
                    else:
                        logger.warning(f"⚠️ DuckDuckGo returned status {response.status}")
                        return None

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ DuckDuckGo request timeout for '{product_name}'")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching DuckDuckGo HTML: {repr(e)}")
            return None

    @staticmethod
    async def _extract_nutrition_with_ai(
        product_name: str,
        html_content: str
    ) -> Optional[Dict]:
        """
        Извлечь пищевую ценность из HTML через Claude Haiku 4.5.

        Args:
            product_name: Название продукта
            html_content: HTML содержимое

        Returns:
            Dict с данными о пищевой ценности
        """
        try:
            # Обрезаем HTML до разумного размера (Haiku может обработать ~200K tokens)
            # ~1 token = 4 символа, оставим ~100K символов (~25K tokens)
            html_content = html_content[:100000]

            # Промпт для Haiku 4.5
            prompt = f"""Проанализируй HTML результаты поиска о продукте "{product_name}".

Твоя задача: извлечь точные данные о пищевой ценности продукта на 100г.

ИЩИ В HTML:
1. Таблицы с пищевой ценностью (table, td, tr)
2. Списки с КБЖУ (ul, li)
3. Блоки с витаминами и минералами
4. Ключевые слова: "калории", "ккал", "белки", "жиры", "углеводы", "витамин", "минерал"

ИЗВЛЕКИ (на 100г продукта):

Макронутриенты:
- Калории (ккал)
- Белки (г)
- Жиры (г)
- Углеводы (г)

Микронутриенты (если есть в HTML):

Витамины:
- A (мкг или МЕ)
- B1/тиамин (мг)
- B2/рибофлавин (мг)
- B3/ниацин (мг)
- B6/пиридоксин (мг)
- B9/фолиевая кислота (мкг)
- B12/кобаламин (мкг)
- C/аскорбиновая кислота (мг)
- D (мкг или МЕ)
- E (мг)
- K (мкг)

Минералы:
- Железо/Fe (мг)
- Кальций/Ca (мг)
- Магний/Mg (мг)
- Калий/K (мг)
- Натрий/Na (мг)
- Цинк/Zn (мг)
- Фосфор/P (мг)
- Йод/I (мкг)
- Селен/Se (мкг)

ВАЖНО:
- Если данных нет - поставь null
- Обрати внимание на единицы измерения (г, мг, мкг)
- Ищи таблицы "Пищевая ценность", "Nutrition Facts", "Состав"
- Предпочитай данные из надежных источников (calorizator.ru, fatsecret.ru, usda.gov)

Верни ТОЛЬКО JSON в формате:
{{
  "found": true,
  "product_name": "точное название из источника",
  "per_100g": {{
    "calories": number,
    "proteins": number,
    "fats": number,
    "carbs": number
  }},
  "micronutrients": {{
    "vitamins": {{
      "A": number or null,
      "B1": number or null,
      "B2": number or null,
      "B3": number or null,
      "B6": number or null,
      "B9": number or null,
      "B12": number or null,
      "C": number or null,
      "D": number or null,
      "E": number or null,
      "K": number or null
    }},
    "minerals": {{
      "iron": number or null,
      "calcium": number or null,
      "magnesium": number or null,
      "potassium": number or null,
      "sodium": number or null,
      "zinc": number or null,
      "phosphorus": number or null,
      "iodine": number or null,
      "selenium": number or null
    }}
  }},
  "category": "фрукты/овощи/мясо/рыба/молочное/злаки/прочее",
  "source": "название сайта",
  "confidence": 0.0-1.0
}}

Если данные НЕ найдены, верни:
{{
  "found": false,
  "reason": "краткая причина"
}}

HTML:
{html_content}
"""

            # Вызов Haiku 4.5
            ai_service = ClaudeAIService()

            response = await ai_service._call_with_rate_limit_and_retry(
                ai_service.async_client.messages.create,
                model=settings.CLAUDE_MODEL_HAIKU_4_5,
                max_tokens=4000,
                temperature=0.1,  # Низкая температура для точности
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Извлекаем JSON из ответа
            response_text = response.content[0].text.strip()

            # Парсим JSON
            # Claude может вернуть JSON в code block или напрямую
            if "```json" in response_text:
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            elif "```" in response_text:
                json_match = re.search(r'```\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)

            data = json.loads(response_text)

            logger.info(f"✅ Haiku 4.5 extracted data: found={data.get('found')}, confidence={data.get('confidence')}")
            return data

        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON from Haiku response: {repr(e)}")
            logger.error(f"Response text: {response_text[:500]}")
            return None
        except Exception as e:
            logger.error(f"❌ Error extracting nutrition with AI: {repr(e)}")
            return None

    @staticmethod
    async def search_scientific_sources(
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Поиск научных источников по запросу.

        Args:
            query: Поисковый запрос
            max_results: Максимальное количество результатов

        Returns:
            List[Dict] со структурой:
                - title: Заголовок
                - url: Ссылка
                - snippet: Краткое описание
        """
        try:
            results = []

            # Используем DuckDuckGo для поиска
            search_query = f"{query} научные исследования здоровье"
            ddg_url = f"https://api.duckduckgo.com/?q={search_query}&format=json&no_html=1"

            async with aiohttp.ClientSession() as client_session:
                try:
                    async with client_session.get(ddg_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()

                            # Извлекаем AbstractText
                            if data.get("AbstractText"):
                                results.append({
                                    "title": data.get("Heading", "Основная информация"),
                                    "url": data.get("AbstractURL", ""),
                                    "snippet": data.get("AbstractText", "")
                                })

                            # Извлекаем RelatedTopics
                            for topic in data.get("RelatedTopics", [])[:max_results]:
                                if isinstance(topic, dict) and topic.get("Text"):
                                    results.append({
                                        "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else "Дополнительная информация",
                                        "url": topic.get("FirstURL", ""),
                                        "snippet": topic.get("Text", "")
                                    })

                                    if len(results) >= max_results:
                                        break

                except Exception as e:
                    logger.warning(f"DuckDuckGo search failed: {repr(e)}")

            # Если не нашли результатов, возвращаем пустой список
            if not results:
                logger.info(f"No scientific sources found for query: {query}")

            return results[:max_results]

        except Exception as e:
            logger.error(f"Error searching scientific sources: {repr(e)}")
            return []
