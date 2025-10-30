"""
Обработчики для дневника питания
"""
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger
from datetime import date

from app.services.meal_service import MealService
from app.bot.keyboards import main_menu_keyboard, diary_actions_keyboard
from app.models.user import User
from app.models.meal import MealType
from app.db.session import async_session_maker
from sqlalchemy import select


async def diary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показать дневник питания за сегодня
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    try:
        async with async_session_maker() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await query.edit_message_text(
                    "❌ Пользователь не найден.\nИспользуйте /start для регистрации.",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Получаем приемы пищи за сегодня
            today = date.today()
            meals = await MealService.get_meals_by_date(session, db_user.id, today)

            # Получаем прогресс
            progress = await MealService.get_nutrition_progress(session, db_user.id, today)

            if not meals:
                await query.edit_message_text(
                    f"📅 *Дневник питания* - {today.strftime('%d.%m.%Y')}\n\n"
                    f"📝 Пока нет записей за сегодня.\n\n"
                    f"Отправьте фото еды, чтобы добавить запись!",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Формируем текст дневника
            meal_type_emoji = {
                MealType.BREAKFAST: "🌅",
                MealType.LUNCH: "🌞",
                MealType.DINNER: "🌙",
                MealType.SNACK: "🍎"
            }

            meal_type_names = {
                MealType.BREAKFAST: "Завтрак",
                MealType.LUNCH: "Обед",
                MealType.DINNER: "Ужин",
                MealType.SNACK: "Перекус"
            }

            diary_text = f"📅 *Дневник питания* - {today.strftime('%d.%m.%Y')}\n\n"

            for meal in meals:
                emoji = meal_type_emoji.get(meal.meal_type, "🍽")
                name = meal_type_names.get(meal.meal_type, "Прием пищи")
                time_str = meal.meal_time.strftime("%H:%M")

                diary_text += f"{emoji} *{name}* ({time_str})\n"

                for food in meal.foods:
                    diary_text += (
                        f"  • {food.name} - {food.portion_description or f'{food.portion_size}г'}\n"
                        f"    {food.calories} ккал | Б: {food.proteins:.0f}г | "
                        f"Ж: {food.fats:.0f}г | У: {food.carbs:.0f}г\n"
                    )

                diary_text += (
                    f"  📊 Итого: {meal.total_calories} ккал\n\n"
                )

            # Добавляем итоги за день
            current = progress["current"]
            target = progress["target"]
            percent = progress["percent"]

            diary_text += "━━━━━━━━━━━━━━━━━\n"
            diary_text += f"📊 *Итого за день:*\n"
            diary_text += (
                f"🔥 Калории: {current['calories']}/{target['calories']} ккал "
                f"({percent['calories']}%)\n"
            )
            diary_text += (
                f"🥩 Белки: {current['proteins']:.0f}/{target['proteins']}г "
                f"({percent['proteins']}%)\n"
            )
            diary_text += (
                f"🧈 Жиры: {current['fats']:.0f}/{target['fats']}г "
                f"({percent['fats']}%)\n"
            )
            diary_text += (
                f"🍞 Углеводы: {current['carbs']:.0f}/{target['carbs']}г "
                f"({percent['carbs']}%)\n"
            )

            # Добавляем мотивацию
            if percent['calories'] >= 100:
                diary_text += "\n✅ Дневная норма калорий достигнута!"
            elif percent['calories'] >= 80:
                diary_text += f"\n💪 Почти у цели! Осталось {progress['remaining']['calories']} ккал"
            else:
                diary_text += f"\n🎯 До цели: {progress['remaining']['calories']} ккал"

            await query.edit_message_text(
                diary_text,
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )

            logger.info(f"Diary shown for user {user.id}, {len(meals)} meals")

    except Exception as e:
        logger.error("Error showing diary for user {}: {}", user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при загрузке дневника.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )


async def delete_meal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удалить прием пищи из дневника
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Извлекаем meal_id из callback_data
    try:
        meal_id = int(query.data.replace("delete_meal_", ""))
    except ValueError:
        await query.edit_message_text(
            "❌ Неверный ID приема пищи",
            reply_markup=main_menu_keyboard()
        )
        return

    try:
        async with async_session_maker() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await query.edit_message_text(
                    "❌ Пользователь не найден",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Удаляем прием пищи
            success = await MealService.delete_meal(session, meal_id, db_user.id)

            if success:
                await query.edit_message_text(
                    "✅ Прием пищи удален из дневника",
                    reply_markup=main_menu_keyboard()
                )
                logger.info(f"Meal {meal_id} deleted by user {user.id}")
            else:
                await query.edit_message_text(
                    "❌ Прием пищи не найден или уже удален",
                    reply_markup=main_menu_keyboard()
                )

    except Exception as e:
        logger.error("Error deleting meal {} for user {}: {}", meal_id, user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при удалении.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
