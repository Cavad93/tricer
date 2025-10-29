"""
Сервис для работы с планами питания
"""
import json
from datetime import date, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from loguru import logger

from app.models.user import User
from app.models.meal_plan import MealPlan, MealPlanDay, PlannedMeal, PlanPeriod
from app.services.claude_ai import ClaudeAIService


class MealPlanService:
    """Сервис для генерации и управления планами питания"""

    @staticmethod
    async def generate_meal_plan(
        session: AsyncSession,
        user_id: int,
        period_type: PlanPeriod,
        start_date: date = None,
        preferences: dict = None,
        medical_context: dict = None,
        old_plan_id: int = None
    ) -> MealPlan:
        """
        Генерация плана питания через AI

        Args:
            session: Сессия БД
            user_id: ID пользователя
            period_type: Период плана (day/week/month)
            start_date: Дата начала плана (по умолчанию - сегодня)
            preferences: Дополнительные предпочтения пользователя
                - favorite_foods: любимые блюда/продукты
                - additional_dislikes: нежелательные продукты
                - special_requests: особые пожелания
            medical_context: Временные медицинские данные (Этап 4 - доработка)
                - chronic_conditions_status: текущее состояние хронических заболеваний
                - acute_conditions: текущие острые состояния
            old_plan_id: ID предыдущего плана (для внесения изменений)

        Returns:
            MealPlan: Созданный план питания
        """
        # Получаем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Определяем даты
        if start_date is None:
            start_date = date.today()

        days_count = {
            PlanPeriod.DAY: 1,
            PlanPeriod.WEEK: 7,
            PlanPeriod.MONTH: 30,
        }[period_type]

        end_date = start_date + timedelta(days=days_count - 1)

        # Загружаем данные старого плана, если он указан
        old_plan_data = None
        if old_plan_id:
            old_plan_data = await MealPlanService._load_old_plan_data(session, old_plan_id)

        # Формируем промпт для AI с учетом preferences, medical_context и old_plan_data
        prompt = MealPlanService._build_meal_plan_prompt(user, period_type, days_count, preferences, medical_context, old_plan_data)

        # Генерируем план через AI
        from app.config import settings
        ai_service = ClaudeAIService()
        try:
            ai_response = await ai_service.async_client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=16000,
                temperature=0.8,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            plan_data = ai_response.content[0].text
            logger.info(f"AI generated meal plan for user {user_id}")

        except Exception as e:
            logger.error(f"Error generating meal plan: {e}")
            raise

        # Парсим ответ AI
        parsed_plan = MealPlanService._parse_ai_meal_plan(plan_data)

        # Создаем план в БД
        meal_plan = MealPlan(
            user_id=user.telegram_id,
            period_type=period_type,
            start_date=start_date,
            end_date=end_date,
            daily_calories=user.target_calories,
            daily_proteins=user.target_proteins,
            daily_fats=user.target_fats,
            daily_carbs=user.target_carbs,
            budget_category=user.budget_category.value if user.budget_category else "normal",
            diet_preferences={
                "diet_type": user.diet_type.value if user.diet_type else "omnivore",
                "allergies": user.allergies or [],
            }
        )

        session.add(meal_plan)
        await session.flush()  # Чтобы получить ID плана

        # Создаем дни и приемы пищи
        for day_num, day_data in enumerate(parsed_plan["days"], 1):
            day_date = start_date + timedelta(days=day_num - 1)

            meal_plan_day = MealPlanDay(
                meal_plan_id=meal_plan.id,
                day_date=day_date,
                day_number=day_num,
                total_calories=day_data.get("total_calories", 0),
                total_proteins=day_data.get("total_proteins", 0),
                total_fats=day_data.get("total_fats", 0),
                total_carbs=day_data.get("total_carbs", 0),
            )

            session.add(meal_plan_day)
            await session.flush()

            # Создаем приемы пищи
            for meal_order, meal_data in enumerate(day_data.get("meals", []), 1):
                planned_meal = PlannedMeal(
                    meal_plan_day_id=meal_plan_day.id,
                    meal_type=meal_data.get("meal_type", "breakfast"),
                    meal_order=meal_order,
                    recipe_name=meal_data.get("recipe_name", ""),
                    ingredients=meal_data.get("ingredients", []),
                    calories=meal_data.get("calories", 0),
                    proteins=meal_data.get("proteins", 0),
                    fats=meal_data.get("fats", 0),
                    carbs=meal_data.get("carbs", 0),
                    cooking_instructions=meal_data.get("cooking_instructions", ""),
                    cooking_time_minutes=meal_data.get("cooking_time_minutes", 0),
                    serving_size=meal_data.get("serving_size", "1 порция"),
                    micronutrients=meal_data.get("micronutrients", {})
                )

                session.add(planned_meal)

        await session.commit()
        logger.info(f"Meal plan created for user {user_id}: {meal_plan.id}")

        return meal_plan

    @staticmethod
    async def _load_old_plan_data(session: AsyncSession, plan_id: int) -> Optional[Dict]:
        """
        Загружает данные предыдущего плана для передачи в AI

        Args:
            session: Сессия БД
            plan_id: ID плана для загрузки

        Returns:
            Dict с данными плана или None если план не найден
        """
        try:
            # Загружаем план
            result = await session.execute(
                select(MealPlan).where(MealPlan.id == plan_id)
            )
            plan = result.scalar_one_or_none()

            if not plan:
                logger.warning(f"Old plan {plan_id} not found")
                return None

            # Загружаем дни плана
            days_result = await session.execute(
                select(MealPlanDay)
                .where(MealPlanDay.meal_plan_id == plan_id)
                .order_by(MealPlanDay.day_number)
            )
            days = days_result.scalars().all()

            # Формируем структуру с данными плана
            plan_data = {
                "period_type": plan.period_type.value,
                "days": []
            }

            for day in days:
                # Загружаем приемы пищи для дня
                meals_result = await session.execute(
                    select(PlannedMeal)
                    .where(PlannedMeal.meal_plan_day_id == day.id)
                    .order_by(PlannedMeal.meal_order)
                )
                meals = meals_result.scalars().all()

                day_data = {
                    "day_number": day.day_number,
                    "total_calories": day.total_calories,
                    "meals": []
                }

                for meal in meals:
                    day_data["meals"].append({
                        "meal_type": meal.meal_type,
                        "recipe_name": meal.recipe_name,
                        "calories": meal.calories,
                        "proteins": meal.proteins,
                        "fats": meal.fats,
                        "carbs": meal.carbs,
                        "ingredients": meal.ingredients
                    })

                plan_data["days"].append(day_data)

            return plan_data

        except Exception as e:
            logger.error(f"Error loading old plan {plan_id}: {e}")
            return None

    @staticmethod
    def _build_meal_plan_prompt(user: User, period_type: PlanPeriod, days_count: int, preferences: dict = None, medical_context: dict = None, old_plan_data: dict = None) -> str:
        """Формирование промпта для генерации плана питания"""

        # Обрабатываем preferences
        preferences = preferences or {}
        favorite_foods = preferences.get("favorite_foods")
        additional_dislikes = preferences.get("additional_dislikes")
        special_requests = preferences.get("special_requests")

        # Обрабатываем временный медицинский контекст (Этап 4 - доработка)
        medical_context = medical_context or {}
        chronic_conditions_status = medical_context.get("chronic_conditions_status")
        acute_conditions = medical_context.get("acute_conditions")

        # Маппинг бюджетных категорий
        budget_descriptions = {
            "economy": "Эконом (бюджетные продукты, простые рецепты, средняя цена продуктов: 100-150₽ на прием пищи)",
            "normal": "Норм (средний бюджет, разнообразные продукты, средняя цена: 200-300₽ на прием пищи)",
            "premium": "Премиум (высокий бюджет, качественные продукты, деликатесы, средняя цена: 400-600₽ на прием пищи)"
        }

        budget_desc = budget_descriptions.get(user.budget_category.value if user.budget_category else "normal", budget_descriptions["normal"])

        # Маппинг целей
        goal_descriptions = {
            "weight_loss": "Похудение (дефицит калорий)",
            "weight_gain": "Набор массы (профицит калорий)",
            "maintenance": "Поддержание веса",
            "health": "Здоровое питание"
        }

        goal_desc = goal_descriptions.get(user.goal.value if user.goal else "health", "Здоровое питание")

        # Маппинг типов диеты
        diet_descriptions = {
            "omnivore": "Всеядный (все продукты)",
            "vegetarian": "Вегетарианец (без мяса и рыбы)",
            "vegan": "Веган (только растительная пища)",
            "pescatarian": "Пескетарианец (рыба разрешена, мясо нет)"
        }

        diet_desc = diet_descriptions.get(user.diet_type.value if user.diet_type else "omnivore", "Всеядный")

        # Маппинг уровней активности
        activity_level_descriptions = {
            "minimal": "Минимальная (сидячий образ жизни, без тренировок)",
            "low": "Низкая (1-3 лёгкие тренировки в неделю)",
            "medium": "Средняя (3-5 умеренных тренировок в неделю)",
            "high": "Высокая (5-7 интенсивных тренировок в неделю)"
        }

        activity_level_desc = activity_level_descriptions.get(
            user.activity_level.value if user.activity_level else "medium",
            "Средняя (3-5 умеренных тренировок в неделю)"
        )

        # Формируем информацию об аллергиях
        allergies_text = ""
        if user.allergies and len(user.allergies) > 0:
            allergies_text = f"\n❗ АЛЛЕРГИИ/ИСКЛЮЧЕНИЯ: {', '.join(user.allergies)}"

        # Формируем информацию о медицинских ограничениях (Этап 4)
        medical_info_text = ""
        if user.chronic_conditions and len(user.chronic_conditions) > 0:
            medical_info_text += f"\n🏥 ХРОНИЧЕСКИЕ ЗАБОЛЕВАНИЯ: {', '.join(user.chronic_conditions)}"
            # Добавляем текущее состояние, если пользователь уточнил
            if chronic_conditions_status and chronic_conditions_status != "no_changes":
                medical_info_text += f"\n   📋 ТЕКУЩЕЕ СОСТОЯНИЕ: {chronic_conditions_status}"
        if user.removed_organs and len(user.removed_organs) > 0:
            medical_info_text += f"\n⚕️ УДАЛЕННЫЕ ОРГАНЫ: {', '.join(user.removed_organs)}"

        # Добавляем информацию об острых состояниях (Этап 4 - доработка)
        if acute_conditions:
            medical_info_text += f"\n🌡️ ОСТРЫЕ СОСТОЯНИЯ (ВРЕМЕННЫЕ): {acute_conditions}"
            medical_info_text += "\n   ⚠️ ВАЖНО: Учти эти временные состояния при составлении рациона! Рацион должен быть щадящим и подходящим для текущего состояния."

        # Добавляем медицинские ограничения по питанию, если они есть
        medical_restrictions_text = ""
        if user.medical_restrictions and len(user.medical_restrictions) > 0:
            restrictions = user.medical_restrictions
            if restrictions.get("foods_to_avoid"):
                medical_restrictions_text += f"\n❌ ИЗБЕГАТЬ: {', '.join(restrictions['foods_to_avoid'])}"
            if restrictions.get("foods_to_limit"):
                medical_restrictions_text += f"\n⚠️ ОГРАНИЧИТЬ: {', '.join(restrictions['foods_to_limit'])}"
            if restrictions.get("foods_to_increase"):
                medical_restrictions_text += f"\n✅ УВЕЛИЧИТЬ: {', '.join(restrictions['foods_to_increase'])}"
            if restrictions.get("nutrients_to_focus"):
                medical_restrictions_text += f"\n🎯 ФОКУС НА НУТРИЕНТАХ: {', '.join(restrictions['nutrients_to_focus'])}"

        period_text = {
            PlanPeriod.DAY: "на 1 день",
            PlanPeriod.WEEK: "на 7 дней (неделю)",
            PlanPeriod.MONTH: "на 30 дней (месяц)"
        }[period_type]

        # Формируем секцию о времени готовки
        cooking_time_text = ""
        if user.preferred_cooking_time_minutes:
            cooking_time_text = f"\n⏰ ВРЕМЯ НА ГОТОВКУ: до {user.preferred_cooking_time_minutes} минут на одно блюдо\n   (Подбирай рецепты, которые можно приготовить за это время)"

        # Формируем секцию с предпочтениями пользователя
        preferences_text = ""
        if favorite_foods:
            preferences_text += f"\n✨ ЛЮБИМЫЕ ПРОДУКТЫ/БЛЮДА: {favorite_foods}\n   (Постарайся включить их в план, где это возможно)"
        if additional_dislikes:
            preferences_text += f"\n❌ ДОПОЛНИТЕЛЬНЫЕ НЕЖЕЛАТЕЛЬНЫЕ ПРОДУКТЫ: {additional_dislikes}\n   (Избегай этих продуктов в плане)"
        if special_requests:
            preferences_text += f"\n💡 ОСОБЫЕ ПОЖЕЛАНИЯ: {special_requests}\n   (Учти эти пожелания при составлении плана)"

        # Формируем секцию с предыдущим планом (если есть)
        old_plan_text = ""
        if old_plan_data and old_plan_data.get("days"):
            old_plan_text = "\n\n📋 ПРЕДЫДУЩИЙ ПЛАН ПИТАНИЯ (для внесения изменений):\n"
            old_plan_text += "⚠️ ВАЖНО: Это план, который уже был составлен. Пользователь просит внести изменения.\n"
            old_plan_text += "Внимательно изучи предыдущий план и учти пожелания пользователя из секции ОСОБЫЕ ПОЖЕЛАНИЯ.\n\n"

            for day_data in old_plan_data["days"]:
                old_plan_text += f"День {day_data['day_number']} ({day_data['total_calories']} ккал):\n"
                for meal in day_data["meals"]:
                    meal_type_ru = {
                        "breakfast": "Завтрак",
                        "lunch": "Обед",
                        "dinner": "Ужин",
                        "snack": "Перекус"
                    }.get(meal["meal_type"], meal["meal_type"])

                    old_plan_text += f"  • {meal_type_ru}: {meal['recipe_name']} "
                    old_plan_text += f"({meal['calories']} ккал, Б:{meal['proteins']}г Ж:{meal['fats']}г У:{meal['carbs']}г)\n"
                old_plan_text += "\n"

        # Подключаем AI system prompts для правильного тона
        from app.bot.texts import AI_SYSTEM_PROMPT_BASE, AI_SYSTEM_PROMPT_NO_DIAGNOSIS

        prompt = f"""{AI_SYSTEM_PROMPT_BASE}

{AI_SYSTEM_PROMPT_NO_DIAGNOSIS}

Ты профессиональный диетолог и нутрициолог. Создай детальный план питания {period_text} для пользователя.

📊 ПАРАМЕТРЫ ПОЛЬЗОВАТЕЛЯ:
- Имя: {user.preferred_name or "Пользователь"}
- Пол: {"Мужской" if user.gender.value == "male" else "Женский"}
- Возраст: {user.age} лет
- Рост: {user.height} см
- Текущий вес: {user.current_weight} кг
- Целевой вес: {user.target_weight} кг
- Уровень активности: {activity_level_desc}
- Цель: {goal_desc}
- Тип питания: {diet_desc}
- Бюджет: {budget_desc}{allergies_text}{medical_info_text}

⚠️ ВАЖНО: Учитывай возраст, вес и уровень активности при расчёте микронутриентов!
   Для более активных людей и людей с большим весом потребности в некоторых микронутриентах выше.

🏥 МЕДИЦИНСКИЕ ОГРАНИЧЕНИЯ (Этап 4 - КРИТИЧЕСКИ ВАЖНО):{medical_restrictions_text}

⚠️ ВНИМАНИЕ: Строго соблюдай все медицинские ограничения! Это влияет на здоровье пользователя.

🎯 ЦЕЛЕВЫЕ ПОКАЗАТЕЛИ НА ДЕНЬ:
- Калории: {user.target_calories} ккал
- Белки: {user.target_proteins}г
- Жиры: {user.target_fats}г
- Углеводы: {user.target_carbs}г
{cooking_time_text}
{preferences_text}{old_plan_text}

💊 МИКРОНУТРИЕНТЫ (для месячного планирования):
ВАЖНО: Рацион должен быть сбалансирован так, чтобы за МЕСЯЦ восполнить суточные нормы по всем микронутриентам.
Не обязательно достигать 100% каждого микронутриента каждый день, но в среднем за месяц все должно быть в норме.

Основные микронутриенты для контроля (средняя норма в день):
- Витамин A: {"900 мкг" if user.gender.value == "male" else "700 мкг"}
- Витамин C: 90 мг
- Витамин D: 10 мкг
- Витамин E: 15 мг
- Витамин B12: 3 мкг
- Витамин B9 (фолиевая кислота): 400 мкг
- Железо (Fe): {"10 мг" if user.gender.value == "male" else "18 мг"}
- Кальций (Ca): 1000 мг
- Магний (Mg): 400 мг
- Цинк (Zn): 12 мг
- Калий (K): 3500 мг

Стратегия восполнения за месяц:
- Чередуй продукты богатые разными витаминами (рыба, мясо, овощи, фрукты, орехи)
- Включай источники железа (красное мясо, печень) несколько раз в неделю
- Обеспечь регулярное поступление кальция (молочка) и магния (орехи, злаки)
- Добавляй разнообразные овощи и фрукты каждый день

📋 ТРЕБОВАНИЯ К ПЛАНУ:

1. Создай план на {days_count} {"день" if days_count == 1 else "дней"}
2. Для каждого дня предусмотри 4 приема пищи: завтрак, обед, ужин, перекус
3. Каждый прием пищи должен содержать:
   - Название блюда
   - Список ингредиентов с количеством (в граммах)
   - Точные КБЖУ (калории, белки, жиры, углеводы)
   - Краткую инструкцию по приготовлению
   - Время приготовления (в минутах)
   - Размер порции

4. ВАЖНО:
   - Соблюдай бюджетную категорию "{user.budget_category.value if user.budget_category else "normal"}"
   - Строго соблюдай тип питания "{user.diet_type.value if user.diet_type else "omnivore"}"
   - Исключи все аллергены: {user.allergies if user.allergies else "нет"}
   - Суммарные КБЖУ за день должны быть близки к целевым показателям (±50 ккал)
   - Рецепты должны быть реалистичными и легко воспроизводимыми
   - Учитывай доступность продуктов в России

5. Разнообразие: каждый день должен быть уникальным, избегай повторений блюд

6. БАЛАНС МИКРОНУТРИЕНТОВ (особенно важно для планов на неделю/месяц):
   - Подбирай блюда так, чтобы в сумме за весь период план обеспечивал достаточное поступление всех микронутриентов
   - Для месячного плана: включай разнообразные источники витаминов и минералов
   - Например:
     * Рыба (омега-3, D, B12) - 2-3 раза в неделю
     * Красное мясо/печень (железо, B12) - 2-3 раза в неделю
     * Молочные продукты (кальций) - ежедневно
     * Орехи и семена (магний, E, цинк) - ежедневно в перекусах
     * Разноцветные овощи и фрукты (витамины A, C, K) - ежедневно
     * Цельнозерновые (группа B, магний) - ежедневно

7. МИКРОНУТРИЕНТЫ В ОТВЕТЕ:
   ⚠️ ВАЖНО: Для КАЖДОГО приёма пищи рассчитай и верни примерное содержание ВСЕХ микронутриентов!

   Учитывай возраст, вес и уровень активности пользователя при оценке адекватности микронутриентов.
   Для более активных людей и людей с большим весом некоторые нормы могут быть выше.

   Включай ВСЕ следующие микронутриенты (в единицах измерения):

   Витамины (15):
   - vitamin_a (мкг) - Витамин A (ретинол)
   - beta_carotene (мкг) - Бета-каротин
   - vitamin_b1 (мг) - Витамин B1 (тиамин)
   - vitamin_b2 (мг) - Витамин B2 (рибофлавин)
   - vitamin_b3 (мг) - Витамин B3/PP (ниацин)
   - vitamin_b5 (мг) - Витамин B5 (пантотеновая кислота)
   - vitamin_b6 (мг) - Витамин B6 (пиридоксин)
   - vitamin_b7 (мкг) - Витамин B7/H (биотин)
   - vitamin_b9 (мкг) - Витамин B9 (фолиевая кислота)
   - vitamin_b12 (мкг) - Витамин B12 (кобаламин)
   - vitamin_c (мг) - Витамин C (аскорбиновая кислота)
   - vitamin_d (мкг) - Витамин D (кальциферол)
   - vitamin_e (мг) - Витамин E (токоферол)
   - vitamin_k (мкг) - Витамин K (филлохинон)
   - choline (мг) - Холин

   Минералы (17):
   - calcium (мг) - Кальций (Ca)
   - phosphorus (мг) - Фосфор (P)
   - magnesium (мг) - Магний (Mg)
   - potassium (мг) - Калий (K)
   - sodium (мг) - Натрий (Na)
   - chloride (мг) - Хлор (Cl)
   - iron (мг) - Железо (Fe)
   - zinc (мг) - Цинк (Zn)
   - iodine (мкг) - Йод (I)
   - selenium (мкг) - Селен (Se)
   - copper (мг) - Медь (Cu)
   - manganese (мг) - Марганец (Mn)
   - chromium (мкг) - Хром (Cr)
   - fluoride (мг) - Фтор (F)
   - cobalt (мкг) - Кобальт (Co)
   - silicon (мг) - Кремний (Si)

   Рассчитывай микронутриенты на основе состава ингредиентов. Используй справочные данные о составе продуктов (USDA, российские таблицы состава пищи).

ФОРМАТ ОТВЕТА (СТРОГО JSON):
{{
  "days": [
    {{
      "day_number": 1,
      "total_calories": 2000,
      "total_proteins": 150,
      "total_fats": 65,
      "total_carbs": 200,
      "meals": [
        {{
          "meal_type": "breakfast",
          "recipe_name": "Овсяная каша с бананом и орехами",
          "calories": 450,
          "proteins": 15,
          "fats": 12,
          "carbs": 68,
          "serving_size": "1 порция (300г)",
          "cooking_time_minutes": 10,
          "ingredients": [
            {{"name": "Овсяные хлопья", "quantity": 80, "unit": "г"}},
            {{"name": "Молоко 2.5%", "quantity": 200, "unit": "мл"}},
            {{"name": "Банан", "quantity": 100, "unit": "г"}},
            {{"name": "Грецкие орехи", "quantity": 20, "unit": "г"}},
            {{"name": "Мёд", "quantity": 10, "unit": "г"}}
          ],
          "cooking_instructions": "1. Залить овсяные хлопья молоком и варить 5 минут. 2. Добавить нарезанный банан. 3. Посыпать измельченными орехами и полить медом.",
          "micronutrients": {{
            "vitamin_a": 50, "beta_carotene": 200, "vitamin_b1": 0.3, "vitamin_b2": 0.4,
            "vitamin_b3": 2.5, "vitamin_b5": 1.2, "vitamin_b6": 0.5, "vitamin_b7": 8,
            "vitamin_b9": 40, "vitamin_b12": 0.5, "vitamin_c": 10, "vitamin_d": 1.2,
            "vitamin_e": 4, "vitamin_k": 5, "choline": 60,
            "calcium": 250, "phosphorus": 200, "magnesium": 80, "potassium": 400,
            "sodium": 150, "chloride": 180, "iron": 2.5, "zinc": 2, "iodine": 15,
            "selenium": 12, "copper": 0.3, "manganese": 0.8, "chromium": 8,
            "fluoride": 0.2, "cobalt": 2, "silicon": 5
          }}
        }},
        // ... остальные приемы пищи (lunch, dinner, snack)
      ]
    }}
    // ... остальные дни
  ]
}}

Верни ТОЛЬКО валидный JSON, без дополнительного текста или объяснений."""

        return prompt

    @staticmethod
    def _parse_ai_meal_plan(ai_response: str) -> Dict:
        """
        Парсинг ответа AI с планом питания

        Args:
            ai_response: Ответ от AI

        Returns:
            Dict: Структурированный план питания
        """
        try:
            # Пытаемся найти JSON в ответе
            start_idx = ai_response.find("{")
            end_idx = ai_response.rfind("}") + 1

            if start_idx == -1 or end_idx == 0:
                raise ValueError("JSON not found in AI response")

            json_str = ai_response[start_idx:end_idx]
            plan_data = json.loads(json_str)

            return plan_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI meal plan response: {e}")
            logger.error(f"AI response: {ai_response[:500]}...")
            raise ValueError("Invalid JSON format in AI response")

    @staticmethod
    async def get_active_meal_plan(session: AsyncSession, user_id: int) -> Optional[MealPlan]:
        """Получить активный план питания пользователя"""
        result = await session.execute(
            select(MealPlan)
            .where(and_(
                MealPlan.user_id == user_id,
                MealPlan.is_active == 1,
                MealPlan.end_date >= date.today()
            ))
            .order_by(MealPlan.created_at.desc())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_meal_plan_by_id(session: AsyncSession, plan_id: int) -> Optional[MealPlan]:
        """Получить план питания по ID"""
        result = await session.execute(
            select(MealPlan).where(MealPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_meal_plan_days(
        session: AsyncSession,
        meal_plan_id: int
    ) -> List[MealPlanDay]:
        """Получить все дни плана питания"""
        result = await session.execute(
            select(MealPlanDay)
            .where(MealPlanDay.meal_plan_id == meal_plan_id)
            .order_by(MealPlanDay.day_number)
        )
        return result.scalars().all()

    @staticmethod
    async def get_day_meals(
        session: AsyncSession,
        day_id: int
    ) -> List[PlannedMeal]:
        """Получить все приемы пищи для дня"""
        result = await session.execute(
            select(PlannedMeal)
            .where(PlannedMeal.meal_plan_day_id == day_id)
            .order_by(PlannedMeal.meal_order)
        )
        return result.scalars().all()

    @staticmethod
    async def deactivate_old_plans(session: AsyncSession, user_id: int):
        """Деактивировать старые планы питания пользователя"""
        result = await session.execute(
            select(MealPlan).where(and_(
                MealPlan.user_id == user_id,
                MealPlan.is_active == 1
            ))
        )
        old_plans = result.scalars().all()

        for plan in old_plans:
            plan.is_active = 0

        await session.commit()
        logger.info(f"Deactivated {len(old_plans)} old meal plans for user {user_id}")

    @staticmethod
    async def deactivate_expired_plans(session: AsyncSession) -> int:
        """
        Деактивировать истёкшие планы питания

        Returns:
            int: Количество деактивированных планов
        """
        from datetime import date

        today = date.today()

        # Находим активные планы, которые истекли
        result = await session.execute(
            select(MealPlan).where(and_(
                MealPlan.is_active == 1,
                MealPlan.end_date < today
            ))
        )
        expired_plans = result.scalars().all()

        # Деактивируем их
        for plan in expired_plans:
            plan.is_active = 0

        if expired_plans:
            await session.commit()
            logger.info(f"Deactivated {len(expired_plans)} expired meal plans")

        return len(expired_plans)

    @staticmethod
    async def copy_day_from_weekly_plan(
        session: AsyncSession,
        user_id: int,
        weekly_plan: MealPlan,
        day_number: int = None
    ) -> MealPlan:
        """
        Копирование одного дня из недельного плана в отдельный дневной план

        Args:
            session: Сессия БД
            user_id: ID пользователя
            weekly_plan: Недельный план, из которого копируем
            day_number: Номер дня для копирования (1-7). Если None, берем день недели сегодня

        Returns:
            MealPlan: Созданный дневной план
        """
        from datetime import date, timedelta

        # Определяем какой день копировать
        if day_number is None:
            # Берем текущий день недели (1 = понедельник, 7 = воскресенье)
            today = date.today()
            # Вычисляем, сколько дней прошло с начала недельного плана
            days_diff = (today - weekly_plan.start_date).days
            # Определяем номер дня в плане (циклически)
            day_number = (days_diff % 7) + 1

        # Получаем день для копирования
        result = await session.execute(
            select(MealPlanDay).where(and_(
                MealPlanDay.meal_plan_id == weekly_plan.id,
                MealPlanDay.day_number == day_number
            ))
        )
        source_day = result.scalar_one_or_none()

        if not source_day:
            raise ValueError(f"Day {day_number} not found in weekly plan")

        # Получаем приемы пищи этого дня
        meals = await MealPlanService.get_day_meals(session, source_day.id)

        # Создаем новый дневной план
        start_date = date.today()
        end_date = start_date

        daily_plan = MealPlan(
            user_id=user_id,
            period_type=PlanPeriod.DAY,
            start_date=start_date,
            end_date=end_date,
            daily_calories=weekly_plan.daily_calories,
            daily_proteins=weekly_plan.daily_proteins,
            daily_fats=weekly_plan.daily_fats,
            daily_carbs=weekly_plan.daily_carbs,
            budget_category=weekly_plan.budget_category,
            diet_preferences=weekly_plan.diet_preferences
        )

        session.add(daily_plan)
        await session.flush()

        # Создаем день
        new_day = MealPlanDay(
            meal_plan_id=daily_plan.id,
            day_date=start_date,
            day_number=1,
            total_calories=source_day.total_calories,
            total_proteins=source_day.total_proteins,
            total_fats=source_day.total_fats,
            total_carbs=source_day.total_carbs
        )

        session.add(new_day)
        await session.flush()

        # Копируем приемы пищи
        for meal in meals:
            new_meal = PlannedMeal(
                meal_plan_day_id=new_day.id,
                meal_type=meal.meal_type,
                meal_order=meal.meal_order,
                recipe_name=meal.recipe_name,
                ingredients=meal.ingredients,
                calories=meal.calories,
                proteins=meal.proteins,
                fats=meal.fats,
                carbs=meal.carbs,
                cooking_instructions=meal.cooking_instructions,
                cooking_time_minutes=meal.cooking_time_minutes,
                serving_size=meal.serving_size
            )

            session.add(new_meal)

        await session.commit()
        logger.info(f"Copied day {day_number} from weekly plan {weekly_plan.id} to new daily plan {daily_plan.id}")

        return daily_plan
