"""
Сервис для проверки заполненности дневника питания
"""
from datetime import date, datetime, timedelta
from typing import List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from app.models.user import User
from app.models.meal import Meal, MealType
from app.services.claude_ai import ClaudeAIService
from app.db.session import async_session_maker
from loguru import logger


class DiaryCheckService:
    """Сервис для проверки и напоминаний о заполнении дневника"""

    @staticmethod
    def _create_diary_reminder_keyboard() -> InlineKeyboardMarkup:
        """
        Создает клавиатуру с кнопками для напоминания о дневнике

        Returns:
            InlineKeyboardMarkup: Клавиатура с кнопками навигации
        """
        keyboard = [
            [InlineKeyboardButton("📸 Добавить еду", callback_data="add_food")],
            [InlineKeyboardButton("📊 Мой дневник", callback_data="diary")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def _analyze_eating_patterns(
        user: User,
        session: AsyncSession,
        days: int = 7
    ) -> Tuple[str, Optional[MealType]]:
        """
        Анализирует паттерны питания пользователя за последние N дней

        Выявляет:
        - Какие приемы пищи пропускаются чаще всего (>40% дней)
        - Среднее количество приемов пищи в день
        - Паттерны недоедания

        Args:
            user: Объект пользователя
            session: Сессия БД
            days: Количество дней для анализа (по умолчанию 7)

        Returns:
            Tuple[str, Optional[MealType]]: (текст с описанием паттернов, тип пропущенного приема пищи или None)
        """
        try:
            today = date.today()
            start_date = today - timedelta(days=days)

            # Получаем все приемы пищи за последние N дней
            result = await session.execute(
                select(Meal)
                .where(
                    Meal.user_id == user.id,
                    Meal.meal_date >= start_date,
                    Meal.meal_date <= today
                )
            )
            meals = result.scalars().all()

            # Группируем по дням и типам приемов пищи
            meals_by_date = {}
            for meal in meals:
                meal_date = meal.meal_date
                if meal_date not in meals_by_date:
                    meals_by_date[meal_date] = set()
                if meal.meal_type:
                    meals_by_date[meal_date].add(meal.meal_type)

            # Подсчитываем пропуски для каждого типа приема пищи
            meal_types_to_check = [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER]
            missing_counts = {meal_type: 0 for meal_type in meal_types_to_check}

            # Проверяем каждый день
            for i in range(days):
                check_date = today - timedelta(days=i)
                meals_on_date = meals_by_date.get(check_date, set())

                for meal_type in meal_types_to_check:
                    if meal_type not in meals_on_date:
                        missing_counts[meal_type] += 1

            # Рассчитываем процент пропусков
            threshold = 0.4  # 40% порог
            pattern_text = ""
            missing_meal_type = None

            meal_type_names = {
                MealType.BREAKFAST: "завтрак",
                MealType.LUNCH: "обед",
                MealType.DINNER: "ужин"
            }

            for meal_type, missing_count in missing_counts.items():
                missing_percent = missing_count / days
                if missing_percent > threshold:
                    meal_name = meal_type_names.get(meal_type, "прием пищи")
                    pattern_text += f"⚠️ Замечаю паттерн: ты часто пропускаешь {meal_name} ({missing_count} из {days} дней на этой неделе).\n"
                    if missing_meal_type is None:  # Берем первый найденный паттерн
                        missing_meal_type = meal_type

            # Анализируем среднее количество приемов пищи
            if meals_by_date:
                avg_meals_per_day = sum(len(meals) for meals in meals_by_date.values()) / len(meals_by_date)
                if avg_meals_per_day < 2.5:
                    pattern_text += f"📊 В среднем ты делаешь {avg_meals_per_day:.1f} приема пищи в день (рекомендуется 3-4).\n"

            return (pattern_text.strip(), missing_meal_type)

        except Exception as e:
            logger.error(f"Error analyzing eating patterns for user {user.id}: {repr(e)}")
            return ("", None)

    @staticmethod
    async def check_and_notify_incomplete_diaries(bot: Bot, current_time: str):
        """
        Проверяет дневники всех пользователей и отправляет напоминания при необходимости

        Args:
            bot: Telegram bot instance
            current_time: Текущее время в формате HH:MM
        """
        try:
            async with async_session_maker() as session:
                # Получаем всех пользователей с включенной проверкой дневника на это время
                result = await session.execute(
                    select(User).where(
                        User.diary_check_enabled == True,
                        User.diary_check_time == current_time,
                        User.is_active == True,
                        User.is_blocked == False
                    )
                )
                users = result.scalars().all()

                logger.info(f"Checking diaries for {len(users)} users at {current_time}")

                for user in users:
                    try:
                        await DiaryCheckService._check_user_diary(bot, user, session)
                    except Exception as e:
                        logger.error("Error checking diary for user {}: {}", user.id, repr(e))

        except Exception as e:
            logger.error("Error in check_and_notify_incomplete_diaries: {}", repr(e))

    @staticmethod
    async def _check_user_diary(bot: Bot, user: User, session: AsyncSession):
        """
        Проверяет дневник конкретного пользователя и отправляет уведомление при необходимости

        Args:
            bot: Telegram bot instance
            user: Объект пользователя
            session: Сессия БД
        """
        try:
            today = date.today()

            # Получаем все приемы пищи пользователя за сегодня
            result = await session.execute(
                select(Meal)
                .options(selectinload(Meal.foods))
                .where(Meal.user_id == user.id, Meal.meal_date == today)
            )
            meals = result.scalars().all()

            # Рассчитываем сумму калорий за день
            total_calories = sum(meal.calories for meal in meals if meal.calories)

            # Рассчитываем процент от целевых калорий
            if not user.target_calories or user.target_calories == 0:
                logger.warning(f"User {user.id} has no target calories set")
                return

            calorie_percent = (total_calories / user.target_calories) * 100
            calorie_deficit_percent = 100 - calorie_percent

            # Если дефицит больше 30% - отправляем уведомление
            if calorie_deficit_percent > 30:
                logger.info(
                    f"User {user.id} has {calorie_deficit_percent:.0f}% calorie deficit "
                    f"({total_calories}/{user.target_calories} kcal)"
                )

                # Генерируем персонализированное сообщение через AI с анализом паттернов
                reminder_text, missing_meal_type, current_hour = await DiaryCheckService._generate_diary_reminder_message(
                    user=user,
                    total_calories=total_calories,
                    meals_count=len(meals),
                    session=session
                )

                # Конвертируем MealType enum в строку для клавиатуры
                missing_meal_str = None
                if missing_meal_type:
                    meal_type_to_str = {
                        MealType.BREAKFAST: "breakfast",
                        MealType.LUNCH: "lunch",
                        MealType.DINNER: "dinner",
                        MealType.SNACK: "snack"
                    }
                    missing_meal_str = meal_type_to_str.get(missing_meal_type)

                # Создаем умную адаптивную клавиатуру с учетом времени и паттернов
                from app.bot.keyboards import smart_diary_reminder_keyboard
                keyboard = smart_diary_reminder_keyboard(
                    current_hour=current_hour,
                    missing_meal_type=missing_meal_str
                )

                # Отправляем сообщение с умной клавиатурой
                await bot.send_message(
                    chat_id=user.telegram_id,
                    text=reminder_text,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )

                logger.info(
                    f"Sent smart diary reminder to user {user.id} "
                    f"(missing: {missing_meal_str}, hour: {current_hour})"
                )

        except Exception as e:
            logger.error("Error in _check_user_diary for user {}: {}", user.id, repr(e))
            raise

    @staticmethod
    async def _generate_diary_reminder_message(
        user: User,
        total_calories: int,
        meals_count: int,
        session: AsyncSession
    ) -> Tuple[str, Optional[MealType], int]:
        """
        Генерирует персонализированное напоминание о заполнении дневника через AI

        Args:
            user: Объект пользователя
            total_calories: Сумма калорий за день
            meals_count: Количество приемов пищи
            session: Сессия БД

        Returns:
            Tuple[str, Optional[MealType], int]: (текст сообщения, пропущенный тип приема пищи, текущий час)
        """
        try:
            calorie_deficit = user.target_calories - total_calories
            deficit_percent = (calorie_deficit / user.target_calories) * 100
            current_hour = datetime.now().hour

            # Анализируем паттерны питания за последние 7 дней
            pattern_text, missing_meal_type = await DiaryCheckService._analyze_eating_patterns(
                user=user,
                session=session,
                days=7
            )

            # Добавляем информацию о паттернах в промпт если они обнаружены
            patterns_section = ""
            if pattern_text:
                patterns_section = f"\n\nОБНАРУЖЕННЫЕ ПАТТЕРНЫ:\n{pattern_text}\n"

            # Формируем промпт для AI с учетом паттернов
            prompt = f"""
Пользователь не полностью заполнил дневник питания. Сгенерируй мягкое персонализированное напоминание (3-4 предложения).

КОНТЕКСТ:
- Имя: {user.preferred_name or user.first_name}
- Целевые калории: {user.target_calories} ккал/день
- Записано за сегодня: {total_calories} ккал
- Дефицит: {calorie_deficit} ккал ({deficit_percent:.0f}%)
- Количество приемов пищи: {meals_count}
- Цель: {user.goal.value if user.goal else 'не указана'}
- Текущее время: {current_hour}:00{patterns_section}

ЗАДАЧА: Напомни о важности полного дневника!
- Используй дружелюбный тон и эмодзи (📝, 🍽️, 📊, ⚠️)
- Если обнаружены паттерны - ОБЯЗАТЕЛЬНО упомяни их первыми! Объясни почему важен пропускаемый прием пищи
- Объясни почему важно записывать ВСЕ приемы пищи:
  * Точный подсчет калорий и КБЖУ
  * Понимание реального рациона
  * Выявление паттернов питания
  * Достижение целей по весу
- Если цель - похудение, объясни что недоедание/голодание вредно (замедляет метаболизм, теряется мышечная масса)
- При похудении важен УМЕРЕННЫЙ дефицит (15-20%), а не экстремальный!
- НЕ критикуй, а мягко мотивируй
- Попроси добавить недостающие приемы пищи

Формат: 3-4 предложения, начни с приветствия по времени суток и эмодзи."""

            # Генерируем через AI используя Haiku 4.5 для экономии (67% дешевле)
            from app.config import settings
            claude_service = ClaudeAIService()

            # Используем async клиент напрямую для выбора модели
            ai_response = await claude_service.async_client.messages.create(
                model=settings.CLAUDE_MODEL_HAIKU_4_5,  # Haiku 4.5 - быстрее и дешевле для простых задач
                max_tokens=500,
                temperature=0.7,
                system="Ты заботливый AI-нутрициолог, который мягко напоминает о важности ведения дневника питания. Персонализируй сообщения с учетом паттернов пользователя.",
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            reminder_text = ai_response.content[0].text.strip()
            logger.info(f"Generated diary reminder with Haiku 4.5 for user {user.id}")

            return (reminder_text, missing_meal_type, current_hour)

        except Exception as e:
            logger.error("Error generating diary reminder message: {}", repr(e))
            current_hour = datetime.now().hour

            # Fallback сообщение
            fallback_message = (
                f"📝 <b>Привет, {user.preferred_name or user.first_name}!</b>\n\n"
                f"Замечаю, что сегодня записано только {total_calories} ккал из {user.target_calories} ккал "
                f"(дефицит {deficit_percent:.0f}%).\n\n"
                f"Не забудь добавить все приемы пищи в дневник! "
                f"Это важно для точного подсчета калорий и достижения целей. 💪"
            )

            return (fallback_message, None, current_hour)

    @staticmethod
    async def get_diary_completion_stats(user_id: int, session: AsyncSession) -> dict:
        """
        Получает статистику заполненности дневника пользователя

        Args:
            user_id: ID пользователя
            session: Сессия БД

        Returns:
            Словарь со статистикой
        """
        try:
            today = date.today()

            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return {"error": "User not found"}

            # Получаем приемы пищи за сегодня
            result = await session.execute(
                select(Meal)
                .where(Meal.user_id == user_id, Meal.meal_date == today)
            )
            meals = result.scalars().all()

            total_calories = sum(meal.calories for meal in meals if meal.calories)
            total_proteins = sum(meal.proteins for meal in meals if meal.proteins)
            total_fats = sum(meal.fats for meal in meals if meal.fats)
            total_carbs = sum(meal.carbs for meal in meals if meal.carbs)

            completion_percent = 0
            if user.target_calories and user.target_calories > 0:
                completion_percent = (total_calories / user.target_calories) * 100

            return {
                "meals_count": len(meals),
                "total_calories": total_calories,
                "target_calories": user.target_calories,
                "completion_percent": completion_percent,
                "deficit_percent": max(0, 100 - completion_percent),
                "total_proteins": total_proteins,
                "total_fats": total_fats,
                "total_carbs": total_carbs,
                "target_proteins": user.target_proteins,
                "target_fats": user.target_fats,
                "target_carbs": user.target_carbs
            }

        except Exception as e:
            logger.error("Error getting diary completion stats: {}", repr(e))
            return {"error": str(e)}
