"""
Сервис для веб-поиска пищевой ценности блюд
"""
import aiohttp
import asyncio
from typing import Dict, List, Optional
from loguru import logger
import json
import re


class WebSearchService:
    """Сервис для поиска данных о пищевой ценности блюд в интернете"""

    @staticmethod
    async def search_nutrition_data(dish_name: str) -> Dict:
        """
        Ищет данные о пищевой ценности блюда в интернете

        Args:
            dish_name: Название блюда

        Returns:
            Dict с данными о КБЖУ и микронутриентах
        """
        try:
            # Формируем поисковый запрос
            search_query = f"{dish_name} калории БЖУ состав пищевая ценность"

            # Используем DuckDuckGo Instant Answer API (бесплатный)
            async with aiohttp.ClientSession() as session:
                # Пробуем разные источники данных

                # 1. Поиск в DuckDuckGo
                ddg_url = f"https://api.duckduckgo.com/?q={search_query}&format=json&no_html=1"

                try:
                    async with session.get(ddg_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()

                            # Извлекаем текст из результатов
                            abstract_text = data.get("AbstractText", "")
                            related_topics = data.get("RelatedTopics", [])

                            # Пытаемся извлечь калории из текста
                            text_to_search = abstract_text + " " + " ".join([
                                t.get("Text", "") for t in related_topics if isinstance(t, dict)
                            ])

                            # Ищем паттерны с калориями
                            calories_match = re.search(r'(\d+)\s*(?:ккал|калори|calories)', text_to_search, re.IGNORECASE)
                            proteins_match = re.search(r'белк[а-я]*[:=\s]*(\d+(?:\.\d+)?)\s*г', text_to_search, re.IGNORECASE)
                            fats_match = re.search(r'жир[а-я]*[:=\s]*(\d+(?:\.\d+)?)\s*г', text_to_search, re.IGNORECASE)
                            carbs_match = re.search(r'углевод[а-я]*[:=\s]*(\d+(?:\.\d+)?)\s*г', text_to_search, re.IGNORECASE)

                            if calories_match:
                                result = {
                                    "source": "web_search",
                                    "dish_name": dish_name,
                                    "found": True,
                                    "calories": int(calories_match.group(1)) if calories_match else None,
                                    "proteins": float(proteins_match.group(1)) if proteins_match else None,
                                    "fats": float(fats_match.group(1)) if fats_match else None,
                                    "carbs": float(carbs_match.group(1)) if carbs_match else None,
                                    "note": "Данные найдены в интернете (приблизительные значения на 100г)"
                                }

                                logger.info(f"Found nutrition data for {dish_name}: {result}")
                                return result

                except Exception as e:
                    logger.warning("DuckDuckGo search failed: %s", str(e))

                # 2. Общий веб-поиск через HTML scraping (fallback)
                # Используем простой поиск по сайтам с пищевой ценностью
                search_engines = [
                    f"https://html.duckduckgo.com/html/?q={search_query.replace(' ', '+')}",
                ]

                for search_url in search_engines:
                    try:
                        async with session.get(
                            search_url,
                            timeout=aiohttp.ClientTimeout(total=10),
                            headers={"User-Agent": "Mozilla/5.0"}
                        ) as response:
                            if response.status == 200:
                                html_text = await response.text()

                                # Ищем калории в HTML
                                calories_match = re.search(r'(\d+)\s*(?:ккал|калори|calories)', html_text, re.IGNORECASE)

                                if calories_match:
                                    result = {
                                        "source": "web_scrape",
                                        "dish_name": dish_name,
                                        "found": True,
                                        "calories": int(calories_match.group(1)),
                                        "proteins": None,
                                        "fats": None,
                                        "carbs": None,
                                        "note": "Частичные данные из веб-поиска"
                                    }
                                    logger.info(f"Found partial nutrition data for {dish_name}")
                                    return result

                    except Exception as e:
                        logger.warning("Search engine {search_url} failed: %s", str(e))
                        continue

            # Если ничего не нашли
            return {
                "source": "not_found",
                "dish_name": dish_name,
                "found": False,
                "calories": None,
                "proteins": None,
                "fats": None,
                "carbs": None,
                "note": "Данные не найдены, используются приблизительные оценки"
            }

        except Exception as e:
            logger.error("Error searching nutrition data for {dish_name}: %s", str(e))
            return {
                "source": "error",
                "dish_name": dish_name,
                "found": False,
                "error": str(e),
                "note": "Ошибка при поиске данных"
            }

    @staticmethod
    async def search_multiple_dishes(dish_names: List[str]) -> Dict[str, Dict]:
        """
        Ищет данные для нескольких блюд параллельно

        Args:
            dish_names: Список названий блюд

        Returns:
            Dict с результатами для каждого блюда
        """
        tasks = [
            WebSearchService.search_nutrition_data(dish_name)
            for dish_name in dish_names
        ]

        results = await asyncio.gather(*tasks)

        return {
            dish_name: result
            for dish_name, result in zip(dish_names, results)
        }

    @staticmethod
    def format_search_results_for_prompt(search_results: Dict[str, Dict]) -> str:
        """
        Форматирует результаты поиска для передачи в промпт AI

        Args:
            search_results: Результаты поиска

        Returns:
            str: Отформатированный текст для промпта
        """
        if not search_results:
            return "Данные из интернета не найдены."

        formatted = "ДАННЫЕ ИЗ ИНТЕРНЕТА О ПИЩЕВОЙ ЦЕННОСТИ:\n\n"

        for dish_name, data in search_results.items():
            if data.get("found"):
                formatted += f"Блюдо: {dish_name}\n"
                if data.get("calories"):
                    formatted += f"  Калории: {data['calories']} ккал (на 100г)\n"
                if data.get("proteins"):
                    formatted += f"  Белки: {data['proteins']}г\n"
                if data.get("fats"):
                    formatted += f"  Жиры: {data['fats']}г\n"
                if data.get("carbs"):
                    formatted += f"  Углеводы: {data['carbs']}г\n"
                formatted += f"  Источник: {data.get('source', 'web')}\n\n"
            else:
                formatted += f"Блюдо: {dish_name}\n"
                formatted += f"  Данные не найдены в интернете\n\n"

        formatted += "\nИСПОЛЬЗУЙ ЭТИ РЕАЛЬНЫЕ ДАННЫЕ вместо своих оценок!\n"
        formatted += "Если данных нет - можешь дать приблизительную оценку, но обязательно укажи что это оценка.\n"

        return formatted
