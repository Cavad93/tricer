"""
Обработчики для дневника питания
"""
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from loguru import logger
from datetime import date

from app.services.meal_service import MealService
from app.bot.keyboards import (
    main_menu_keyboard,
    diary_main_keyboard,
    diary_meal_list_keyboard,
    back_to_menu_keyboard,
    meal_edit_menu_keyboard,
    meal_food_list_keyboard
)
from app.models.user import User
from app.models.meal import MealType
from app.db.session import async_session_maker
from sqlalchemy import select

# Состояния для ConversationHandler
WAITING_PORTION_INPUT = 1


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
                reply_markup=diary_main_keyboard()
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


async def diary_edit_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показать список приемов пищи для редактирования
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
                    "❌ Пользователь не найден",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Получаем приемы пищи за сегодня
            today = date.today()
            meals = await MealService.get_meals_by_date(session, db_user.id, today)

            if not meals:
                await query.edit_message_text(
                    "📝 У вас пока нет записей за сегодня",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Показываем список с кнопками редактирования
            await query.edit_message_text(
                "✏️ *Выберите прием пищи для редактирования:*",
                parse_mode="Markdown",
                reply_markup=diary_meal_list_keyboard(meals, "edit")
            )

            logger.info(f"Edit list shown for user {user.id}, {len(meals)} meals")

    except Exception as e:
        logger.error("Error showing edit list for user {}: {}", user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при загрузке списка.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )


async def diary_delete_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показать список приемов пищи для удаления
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
                    "❌ Пользователь не найден",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Получаем приемы пищи за сегодня
            today = date.today()
            meals = await MealService.get_meals_by_date(session, db_user.id, today)

            if not meals:
                await query.edit_message_text(
                    "📝 У вас пока нет записей за сегодня",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Показываем список с кнопками удаления
            await query.edit_message_text(
                "🗑️ *Выберите прием пищи для удаления:*",
                parse_mode="Markdown",
                reply_markup=diary_meal_list_keyboard(meals, "delete")
            )

            logger.info(f"Delete list shown for user {user.id}, {len(meals)} meals")

    except Exception as e:
        logger.error("Error showing delete list for user {}: {}", user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при загрузке списка.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )


async def diary_edit_meal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показать меню редактирования приема пищи
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Извлекаем meal_id из callback_data
    try:
        meal_id = int(query.data.replace("diary_edit_", ""))
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

            # Получаем прием пищи
            from app.models.meal import Meal
            from sqlalchemy.orm import selectinload

            meal_result = await session.execute(
                select(Meal)
                .where(Meal.id == meal_id, Meal.user_id == db_user.id)
                .options(selectinload(Meal.foods))
            )
            meal = meal_result.scalar_one_or_none()

            if not meal:
                await query.edit_message_text(
                    "❌ Прием пищи не найден",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Сохраняем meal_id в context для следующего шага
            context.user_data["editing_meal_id"] = meal_id

            # Показываем информацию о блюде
            meal_type_names = {
                MealType.BREAKFAST: "Завтрак",
                MealType.LUNCH: "Обед",
                MealType.DINNER: "Ужин",
                MealType.SNACK: "Перекус"
            }

            meal_name = meal_type_names.get(meal.meal_type, "Прием пищи")
            time_str = meal.meal_time.strftime("%H:%M")

            edit_text = f"✏️ *Редактирование: {meal_name} ({time_str})*\n\n"
            edit_text += "*Продукты:*\n"

            for i, food in enumerate(meal.foods, 1):
                edit_text += (
                    f"{i}. {food.name} - {food.portion_description or f'{food.portion_size}г'}\n"
                    f"   {food.calories} ккал | Б: {food.proteins:.0f}г | "
                    f"Ж: {food.fats:.0f}г | У: {food.carbs:.0f}г\n"
                )

            edit_text += f"\n📊 *Итого:* {meal.total_calories} ккал\n\n"
            edit_text += "Выберите действие:"

            await query.edit_message_text(
                edit_text,
                parse_mode="Markdown",
                reply_markup=meal_edit_menu_keyboard(meal_id)
            )

            logger.info(f"Showing edit menu for meal {meal_id}, user {user.id}")

    except Exception as e:
        logger.error("Error starting meal edit {} for user {}: {}", meal_id, user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при загрузке приема пищи.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )


async def edit_portion_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начать изменение порции приема пищи
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Извлекаем meal_id из callback_data
    try:
        meal_id = int(query.data.replace("edit_portion_", ""))
    except ValueError:
        await query.edit_message_text(
            "❌ Неверный ID приема пищи",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

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
                return ConversationHandler.END

            # Получаем прием пищи
            from app.models.meal import Meal
            from sqlalchemy.orm import selectinload

            meal_result = await session.execute(
                select(Meal)
                .where(Meal.id == meal_id, Meal.user_id == db_user.id)
                .options(selectinload(Meal.foods))
            )
            meal = meal_result.scalar_one_or_none()

            if not meal:
                await query.edit_message_text(
                    "❌ Прием пищи не найден",
                    reply_markup=main_menu_keyboard()
                )
                return ConversationHandler.END

            # Сохраняем meal_id в context
            context.user_data["editing_meal_id"] = meal_id

            edit_text = (
                "📏 *Изменение размера порции*\n\n"
                "📝 *Введите новый размер порции в процентах*\n\n"
                "Например:\n"
                "• `50` - уменьшить порцию вдвое (съел только половину)\n"
                "• `75` - съел 3/4 от порции\n"
                "• `100` - оставить как есть\n"
                "• `150` - увеличить в 1.5 раза\n\n"
                "Введите число от 1 до 500:"
            )

            await query.edit_message_text(
                edit_text,
                parse_mode="Markdown"
            )

            logger.info(f"Starting portion edit for meal {meal_id}, user {user.id}")

            return WAITING_PORTION_INPUT

    except Exception as e:
        logger.error("Error starting portion edit {} for user {}: {}", meal_id, user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при загрузке приема пищи.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END


async def remove_food_from_meal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показать список продуктов для удаления из приема пищи
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Извлекаем meal_id из callback_data
    try:
        meal_id = int(query.data.replace("remove_food_from_meal_", ""))
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

            # Получаем прием пищи
            from app.models.meal import Meal
            from sqlalchemy.orm import selectinload

            meal_result = await session.execute(
                select(Meal)
                .where(Meal.id == meal_id, Meal.user_id == db_user.id)
                .options(selectinload(Meal.foods))
            )
            meal = meal_result.scalar_one_or_none()

            if not meal:
                await query.edit_message_text(
                    "❌ Прием пищи не найден",
                    reply_markup=main_menu_keyboard()
                )
                return

            if not meal.foods:
                await query.edit_message_text(
                    "❌ В этом приеме пищи нет продуктов",
                    reply_markup=meal_edit_menu_keyboard(meal_id)
                )
                return

            edit_text = "🗑️ *Выберите продукт для удаления:*\n\n"

            await query.edit_message_text(
                edit_text,
                parse_mode="Markdown",
                reply_markup=meal_food_list_keyboard(meal_id, meal.foods)
            )

            logger.info(f"Showing food list for removal from meal {meal_id}, user {user.id}")

    except Exception as e:
        logger.error("Error showing food list {} for user {}: {}", meal_id, user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при загрузке списка продуктов.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )


async def delete_food_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удалить конкретный продукт из приема пищи с перерасчетом калорий
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Извлекаем meal_id и food_id из callback_data
    try:
        parts = query.data.replace("delete_food_", "").split("_")
        meal_id = int(parts[0])
        food_id = int(parts[1])
    except (ValueError, IndexError):
        await query.edit_message_text(
            "❌ Неверный ID",
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

            # Получаем прием пищи
            from app.models.meal import Meal, MealFood
            from sqlalchemy.orm import selectinload

            meal_result = await session.execute(
                select(Meal)
                .where(Meal.id == meal_id, Meal.user_id == db_user.id)
                .options(selectinload(Meal.foods))
            )
            meal = meal_result.scalar_one_or_none()

            if not meal:
                await query.edit_message_text(
                    "❌ Прием пищи не найден",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Находим и удаляем продукт
            food_result = await session.execute(
                select(MealFood).where(MealFood.id == food_id, MealFood.meal_id == meal_id)
            )
            food = food_result.scalar_one_or_none()

            if not food:
                await query.edit_message_text(
                    "❌ Продукт не найден",
                    reply_markup=meal_edit_menu_keyboard(meal_id)
                )
                return

            food_name = food.name

            # Удаляем продукт
            await session.delete(food)

            # Перерасчитываем калории приема пищи
            meal.total_calories = sum(f.calories for f in meal.foods if f.id != food_id)
            meal.total_proteins = sum(f.proteins for f in meal.foods if f.id != food_id)
            meal.total_fats = sum(f.fats for f in meal.foods if f.id != food_id)
            meal.total_carbs = sum(f.carbs for f in meal.foods if f.id != food_id)

            await session.commit()

            # Если больше нет продуктов, удаляем весь прием пищи
            if len(meal.foods) <= 1:  # Остался только удаляемый продукт
                await session.delete(meal)
                await session.commit()

                await query.edit_message_text(
                    f"✅ Продукт *{food_name}* удален\n\n"
                    f"Прием пищи был полностью удален, так как это был последний продукт.",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard()
                )
            else:
                await query.edit_message_text(
                    f"✅ Продукт *{food_name}* удален\n\n"
                    f"📊 Новое количество калорий: {meal.total_calories} ккал",
                    parse_mode="Markdown",
                    reply_markup=meal_edit_menu_keyboard(meal_id)
                )

            logger.info(f"Food {food_id} deleted from meal {meal_id} by user {user.id}")

    except Exception as e:
        logger.error("Error deleting food {} from meal {} for user {}: {}", food_id, meal_id, user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при удалении продукта.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )


async def delete_whole_meal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удалить весь прием пищи
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Извлекаем meal_id из callback_data
    try:
        meal_id = int(query.data.replace("delete_whole_meal_", ""))
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

            # Получаем прием пищи
            from app.models.meal import Meal

            meal_result = await session.execute(
                select(Meal)
                .where(Meal.id == meal_id, Meal.user_id == db_user.id)
            )
            meal = meal_result.scalar_one_or_none()

            if not meal:
                await query.edit_message_text(
                    "❌ Прием пищи не найден",
                    reply_markup=main_menu_keyboard()
                )
                return

            # Показываем информацию о приеме пищи
            meal_type_names = {
                MealType.BREAKFAST: "Завтрак",
                MealType.LUNCH: "Обед",
                MealType.DINNER: "Ужин",
                MealType.SNACK: "Перекус"
            }

            meal_name = meal_type_names.get(meal.meal_type, "Прием пищи")
            time_str = meal.meal_time.strftime("%H:%M")

            # Удаляем прием пищи (продукты удалятся каскадно)
            await session.delete(meal)
            await session.commit()

            await query.edit_message_text(
                f"✅ {meal_name} ({time_str}) полностью удален из дневника\n\n"
                f"📊 Удалено {meal.total_calories} ккал",
                reply_markup=main_menu_keyboard()
            )

            logger.info(f"Meal {meal_id} completely deleted by user {user.id}")

    except Exception as e:
        logger.error("Error deleting whole meal {} for user {}: {}", meal_id, user.id, repr(e))

        await query.edit_message_text(
            "❌ Ошибка при удалении приема пищи.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )


async def add_food_to_meal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Добавить продукт к существующему приему пищи
    """
    query = update.callback_query
    await query.answer()

    # Извлекаем meal_id из callback_data
    try:
        meal_id = int(query.data.replace("add_food_to_meal_", ""))
    except ValueError:
        await query.edit_message_text(
            "❌ Неверный ID приема пищи",
            reply_markup=main_menu_keyboard()
        )
        return

    # Сохраняем meal_id в context для последующего добавления
    context.user_data["adding_to_meal_id"] = meal_id

    await query.edit_message_text(
        "➕ *Добавление продукта*\n\n"
        "Отправьте фото или текстовое описание продукта, который хотите добавить к этому приему пищи.\n\n"
        "Для отмены нажмите /cancel",
        parse_mode="Markdown"
    )

    logger.info(f"Started adding food to meal {meal_id}")


async def edit_portion_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка ввода нового размера порции
    """
    user = update.effective_user
    portion_text = update.message.text.strip()

    # Проверяем, что введено число
    try:
        portion_percent = int(portion_text)

        if portion_percent < 1 or portion_percent > 500:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число от 1 до 500",
            )
            return WAITING_PORTION_INPUT

    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите целое число (например: 50, 75, 100)",
        )
        return WAITING_PORTION_INPUT

    # Получаем meal_id из context
    meal_id = context.user_data.get("editing_meal_id")

    if not meal_id:
        await update.message.reply_text(
            "❌ Ошибка: не найден ID приема пищи",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    try:
        async with async_session_maker() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == user.id)
            )
            db_user = result.scalar_one_or_none()

            if not db_user:
                await update.message.reply_text(
                    "❌ Пользователь не найден",
                    reply_markup=main_menu_keyboard()
                )
                return ConversationHandler.END

            # Обновляем порцию
            success = await MealService.update_meal_portion(
                session, meal_id, db_user.id, portion_percent
            )

            if success:
                if portion_percent == 100:
                    message = "✅ Порция осталась без изменений"
                elif portion_percent < 100:
                    message = f"✅ Порция уменьшена до {portion_percent}%"
                else:
                    message = f"✅ Порция увеличена до {portion_percent}%"

                await update.message.reply_text(
                    f"{message}\n\nИзменения сохранены в дневнике!",
                    reply_markup=main_menu_keyboard()
                )
                logger.info(f"Meal {meal_id} portion updated to {portion_percent}% by user {user.id}")
            else:
                await update.message.reply_text(
                    "❌ Прием пищи не найден или не может быть изменен",
                    reply_markup=main_menu_keyboard()
                )

            # Очищаем context
            context.user_data.pop("editing_meal_id", None)

            return ConversationHandler.END

    except Exception as e:
        logger.error("Error updating meal portion {} for user {}: {}", meal_id, user.id, repr(e))

        await update.message.reply_text(
            "❌ Ошибка при обновлении порции.\nПопробуйте позже.",
            reply_markup=main_menu_keyboard()
        )

        context.user_data.pop("editing_meal_id", None)
        return ConversationHandler.END


async def cancel_edit_portion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Отмена редактирования порции
    """
    await update.message.reply_text(
        "❌ Редактирование отменено",
        reply_markup=main_menu_keyboard()
    )

    # Очищаем context
    context.user_data.pop("editing_meal_id", None)

    return ConversationHandler.END


async def diary_delete_meal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Удалить прием пищи из списка
    """
    query = update.callback_query
    await query.answer()

    user = update.effective_user

    # Извлекаем meal_id из callback_data
    try:
        meal_id = int(query.data.replace("diary_delete_", ""))
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
