"""
Хендлеры для управления конфиденциальностью и персональными данными (152-ФЗ)

Функции:
- Экспорт данных (/export_data)
- Удаление аккаунта (/delete_account)
- Управление согласиями (/privacy_settings)
- Отзыв согласия
"""

import json
import logging
from datetime import datetime
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.texts import (
    EXPORT_DATA_TEXT,
    DELETE_ACCOUNT_WARNING,
    PRIVACY_SETTINGS_TEXT
)
from app.bot.states import PrivacyStates
from app.db.session import async_session_maker
from app.models.user import User
from app.models.meal_plan import MealPlan, MealPlanDay, PlannedMeal
from app.models.medical_analysis import MedicalAnalysis
from app.models.chat import ChatMessage
from app.models.meal import Meal, MealFood
from app.models.usage import DailyUsage
from app.models.micronutrients import DailyMicronutrients
from app.models.wellness_log import WellnessLog
from app.models.pantry import UserPantry, PantryUsageLog
from app.models.shopping_list import ShoppingList, ShoppingItem
from app.models.food_correction import FoodRecognitionCorrection
from app.models.user_consent import UserConsent
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def privacy_settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /privacy_settings - управление конфиденциальностью
    """
    from app.config import settings

    keyboard = [
        [InlineKeyboardButton("📦 Экспортировать данные", callback_data="export_data")],
        [InlineKeyboardButton("📄 Политика конфиденциальности", url=settings.PRIVACY_POLICY_URL)],
        [InlineKeyboardButton("🗑️ Удалить аккаунт", callback_data="delete_account")],
        [InlineKeyboardButton("⚠️ Отозвать согласие", callback_data="revoke_consent")],
        [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        PRIVACY_SETTINGS_TEXT,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def export_data_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка кнопки "Экспортировать данные" (152-ФЗ: право на получение данных)
    """
    query = update.callback_query
    await query.answer()

    telegram_id = query.from_user.id
    logger.info(f"Export data request from telegram_id={telegram_id}")

    # Показываем сообщение о подготовке
    await query.edit_message_text(
        "⏳ Подготавливаю данные для экспорта...\n"
        "Это может занять несколько секунд.",
        parse_mode="HTML"
    )

    try:
        async with async_session_maker() as session:
            # Получаем данные пользователя
            user_data = await _collect_user_data(session, telegram_id)

            if not user_data:
                await query.edit_message_text(
                    "❌ Данные не найдены",
                    parse_mode="HTML"
                )
                return

            # Создаем JSON файл
            json_content = json.dumps(user_data, ensure_ascii=False, indent=2)
            file_bytes = BytesIO(json_content.encode('utf-8'))
            file_bytes.name = f"nutriai_data_{telegram_id}_{datetime.now().strftime('%Y%m%d')}.json"

            # Отправляем файл
            await query.message.reply_document(
                document=file_bytes,
                filename=file_bytes.name,
                caption=(
                    "📦 <b>Ваши данные экспортированы</b>\n\n"
                    "Файл содержит все ваши персональные данные в формате JSON.\n"
                    "Храните его в безопасном месте.\n\n"
                    "<i>Файл будет автоматически удален из Telegram через 24 часа.</i>"
                ),
                parse_mode="HTML"
            )

            await query.edit_message_text(
                "✅ Данные успешно экспортированы!",
                parse_mode="HTML"
            )

    except Exception as e:
        logger.error(f"Export data error: {e}")
        await query.edit_message_text(
            "❌ Ошибка при экспорте данных. Попробуйте позже.",
            parse_mode="HTML"
        )


async def _collect_user_data(db: AsyncSession, telegram_id: int) -> dict:
    """
    Собирает все данные пользователя для экспорта (152-ФЗ compliance)
    """
    logger.info(f"Starting data export for telegram_id={telegram_id}")

    # Получаем пользователя
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"User not found for telegram_id={telegram_id}")
        return None

    logger.debug(f"Collecting data for user_id={user.id}")

    # Базовые данные
    user_data = {
        "export_date": datetime.now().isoformat(),
        "user_id": user.id,
        "telegram_id": user.telegram_id,
        "profile": {
            "preferred_name": user.preferred_name,
            "country": user.country,
            "city": user.city,
            "gender": user.gender.value if user.gender else None,
            "birth_year": user.birth_year,
            "height": user.height,
            "current_weight": user.current_weight,
            "target_weight": user.target_weight,
            "goal": user.goal.value if user.goal else None,
            "activity_level": user.activity_level.value if user.activity_level else None,
            "diet_type": user.diet_type.value if user.diet_type else None,
            "budget_category": user.budget_category.value if user.budget_category else None,
            "allergies": user.allergies,
        },
        "medical_data": {
            "chronic_conditions": user.chronic_conditions,
            "removed_organs": user.removed_organs,
            "medical_restrictions": user.medical_restrictions,
            "medical_notes": user.medical_notes
        },
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None
    }

    # Получаем планы питания с днями и запланированными приемами пищи
    meal_plans_result = await db.execute(
        select(MealPlan).where(MealPlan.user_id == user.id)
    )
    meal_plans = meal_plans_result.scalars().all()

    meal_plans_data = []
    for plan in meal_plans:
        # Получаем дни плана питания
        meal_plan_days_result = await db.execute(
            select(MealPlanDay).where(MealPlanDay.meal_plan_id == plan.id).order_by(MealPlanDay.day_number)
        )
        meal_plan_days = meal_plan_days_result.scalars().all()

        days_data = []
        for day in meal_plan_days:
            # Получаем запланированные приемы пищи для каждого дня
            planned_meals_result = await db.execute(
                select(PlannedMeal).where(PlannedMeal.meal_plan_day_id == day.id).order_by(PlannedMeal.meal_order)
            )
            planned_meals = planned_meals_result.scalars().all()

            days_data.append({
                "id": day.id,
                "day_number": day.day_number,
                "day_date": day.day_date.isoformat() if day.day_date else None,
                "total_calories": day.total_calories,
                "total_proteins": day.total_proteins,
                "total_fats": day.total_fats,
                "total_carbs": day.total_carbs,
                "planned_meals": [
                    {
                        "id": pm.id,
                        "meal_type": pm.meal_type,
                        "meal_order": pm.meal_order,
                        "recipe_name": pm.recipe_name,
                        "ingredients": pm.ingredients,
                        "cooking_instructions": pm.cooking_instructions,
                        "cooking_time_minutes": pm.cooking_time_minutes,
                        "serving_size": pm.serving_size,
                        "calories": pm.calories,
                        "proteins": pm.proteins,
                        "fats": pm.fats,
                        "carbs": pm.carbs,
                        "micronutrients": pm.micronutrients
                    }
                    for pm in planned_meals
                ]
            })

        meal_plans_data.append({
            "id": plan.id,
            "period_type": plan.period_type.value if hasattr(plan.period_type, 'value') else plan.period_type,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            "end_date": plan.end_date.isoformat() if plan.end_date else None,
            "daily_calories": plan.daily_calories,
            "daily_proteins": plan.daily_proteins,
            "daily_fats": plan.daily_fats,
            "daily_carbs": plan.daily_carbs,
            "budget_category": plan.budget_category,
            "diet_preferences": plan.diet_preferences,
            "pdf_filename": plan.pdf_filename,
            "pdf_path": plan.pdf_path,
            "is_active": plan.is_active,
            "days": days_data,
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None
        })

    user_data["meal_plans"] = meal_plans_data

    # Получаем медицинские анализы
    analyses_result = await db.execute(
        select(MedicalAnalysis).where(MedicalAnalysis.user_id == user.id)
    )
    analyses = analyses_result.scalars().all()

    user_data["medical_analyses"] = [
        {
            "id": analysis.id,
            "analysis_type": analysis.analysis_type,
            "analysis_date": analysis.analysis_date.isoformat() if analysis.analysis_date else None,
            "detected_deficiencies": analysis.detected_deficiencies,
            "needs_doctor_consultation": analysis.needs_doctor_consultation,
            "recommendations": analysis.recommendations,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None
        }
        for analysis in analyses
    ]

    # Получаем историю чата
    chat_result = await db.execute(
        select(ChatMessage).where(ChatMessage.user_id == user.id).order_by(ChatMessage.created_at)
    )
    chat_messages = chat_result.scalars().all()

    user_data["chat_history"] = [
        {
            "id": msg.id,
            "role": msg.role.value if hasattr(msg.role, 'value') else msg.role,
            "content": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,  # Обрезаем длинные сообщения
            "tokens_used": msg.tokens_used,
            "created_at": msg.created_at.isoformat() if msg.created_at else None
        }
        for msg in chat_messages
    ]

    # Получаем дневник питания (meals) с продуктами (MealFood)
    meals_result = await db.execute(
        select(Meal).where(Meal.user_id == user.id).order_by(Meal.meal_date.desc(), Meal.meal_time.desc())
    )
    meals = meals_result.scalars().all()

    meal_diary = []
    for meal in meals:
        # Получаем продукты для каждого приема пищи
        meal_foods_result = await db.execute(
            select(MealFood).where(MealFood.meal_id == meal.id)
        )
        meal_foods = meal_foods_result.scalars().all()

        meal_diary.append({
            "id": meal.id,
            "meal_type": meal.meal_type.value if hasattr(meal.meal_type, 'value') else meal.meal_type,
            "meal_date": meal.meal_date.isoformat() if meal.meal_date else None,
            "meal_time": meal.meal_time.isoformat() if meal.meal_time else None,
            "total_calories": meal.total_calories,
            "total_proteins": meal.total_proteins,
            "total_fats": meal.total_fats,
            "total_carbs": meal.total_carbs,
            "notes": meal.notes,
            "photo_url": meal.photo_url,
            "foods": [
                {
                    "id": food.id,
                    "name": food.name,
                    "portion_size": food.portion_size,
                    "portion_description": food.portion_description,
                    "calories": food.calories,
                    "proteins": food.proteins,
                    "fats": food.fats,
                    "carbs": food.carbs,
                    "ingredients": food.ingredients,
                    "confidence_score": food.confidence_score,
                    "micronutrients": food.micronutrients
                }
                for food in meal_foods
            ],
            "created_at": meal.created_at.isoformat() if meal.created_at else None,
            "updated_at": meal.updated_at.isoformat() if meal.updated_at else None
        })

    user_data["meal_diary"] = meal_diary

    # Получаем статистику использования
    usage_result = await db.execute(
        select(DailyUsage).where(DailyUsage.user_id == user.id).order_by(DailyUsage.date.desc())
    )
    usage_stats = usage_result.scalars().all()

    user_data["usage_statistics"] = [
        {
            "date": usage.date.isoformat() if usage.date else None,
            "photos_analyzed": usage.photos_analyzed,
            "chat_messages_sent": usage.chat_messages_sent
        }
        for usage in usage_stats
    ]

    # Получаем данные о микронутриентах
    micronutrients_result = await db.execute(
        select(DailyMicronutrients).where(DailyMicronutrients.user_id == user.id).order_by(DailyMicronutrients.date.desc())
    )
    micronutrients = micronutrients_result.scalars().all()

    user_data["micronutrients_history"] = [
        {
            "date": micro.date.isoformat() if micro.date else None,
            "vitamins": micro.vitamins,
            "minerals": micro.minerals,
            "created_at": micro.created_at.isoformat() if micro.created_at else None
        }
        for micro in micronutrients
    ]

    # Получаем дневник самочувствия
    wellness_result = await db.execute(
        select(WellnessLog).where(WellnessLog.user_id == user.id).order_by(WellnessLog.log_datetime.desc())
    )
    wellness_logs = wellness_result.scalars().all()

    user_data["wellness_logs"] = [
        {
            "id": log.id,
            "log_datetime": log.log_datetime.isoformat() if log.log_datetime else None,
            "energy_level": log.energy_level,
            "mood": log.mood,
            "digestion": log.digestion,
            "sleep_quality": log.sleep_quality,
            "notes": log.notes,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in wellness_logs
    ]

    # Получаем продукты в кладовой с историей использования
    pantry_result = await db.execute(
        select(UserPantry).where(UserPantry.user_id == user.id)
    )
    pantry_items = pantry_result.scalars().all()

    pantry_data = []
    for item in pantry_items:
        # Получаем историю использования для каждого продукта
        usage_logs_result = await db.execute(
            select(PantryUsageLog).where(PantryUsageLog.pantry_item_id == item.id).order_by(PantryUsageLog.used_at.desc())
        )
        usage_logs = usage_logs_result.scalars().all()

        pantry_data.append({
            "id": item.id,
            "product_name": item.product_name,
            "category": item.category,
            "quantity": item.quantity,
            "unit": item.unit,
            "calories_per_100g": item.calories_per_100g,
            "proteins_per_100g": item.proteins_per_100g,
            "fats_per_100g": item.fats_per_100g,
            "carbs_per_100g": item.carbs_per_100g,
            "initial_quantity": item.initial_quantity,
            "last_used_date": item.last_used_date.isoformat() if item.last_used_date else None,
            "times_used": item.times_used,
            "expiration_date": item.expiration_date.isoformat() if item.expiration_date else None,
            "is_perishable": item.is_perishable,
            "source": item.source,
            "notes": item.notes,
            "usage_history": [
                {
                    "id": log.id,
                    "meal_id": log.meal_id,
                    "planned_meal_id": log.planned_meal_id,
                    "quantity_used": log.quantity_used,
                    "unit": log.unit,
                    "usage_type": log.usage_type,
                    "used_at": log.used_at.isoformat() if log.used_at else None,
                    "notes": log.notes
                }
                for log in usage_logs
            ],
            "added_at": item.added_at.isoformat() if item.added_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None
        })

    user_data["pantry"] = pantry_data

    # Получаем списки покупок с товарами (через meal_plan_id, т.к. ShoppingList не имеет user_id)
    meal_plan_ids_list = [plan.id for plan in meal_plans]
    shopping_lists_result = await db.execute(
        select(ShoppingList).where(ShoppingList.meal_plan_id.in_(meal_plan_ids_list)).order_by(ShoppingList.generated_at.desc())
    ) if meal_plan_ids_list else None
    shopping_lists = shopping_lists_result.scalars().all() if shopping_lists_result else []

    shopping_lists_data = []
    for slist in shopping_lists:
        # Получаем товары для каждого списка покупок
        shopping_items_result = await db.execute(
            select(ShoppingItem).where(ShoppingItem.shopping_list_id == slist.id)
        )
        shopping_items = shopping_items_result.scalars().all()

        shopping_lists_data.append({
            "id": slist.id,
            "meal_plan_id": slist.meal_plan_id,
            "total_cost": slist.total_cost,
            "currency": slist.currency,
            "pdf_filename": slist.pdf_filename,
            "pdf_path": slist.pdf_path,
            "items": [
                {
                    "id": item.id,
                    "category": item.category,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "estimated_price": item.estimated_price,
                    "price_per_unit": item.price_per_unit,
                    "shop_name": item.shop_name,
                    "shop_url": item.shop_url,
                    "notes": item.notes
                }
                for item in shopping_items
            ],
            "generated_at": slist.generated_at.isoformat() if slist.generated_at else None,
            "updated_at": slist.updated_at.isoformat() if slist.updated_at else None
        })

    user_data["shopping_lists"] = shopping_lists_data

    # Получаем коррекции распознавания
    corrections_result = await db.execute(
        select(FoodRecognitionCorrection).where(FoodRecognitionCorrection.user_id == user.id)
    )
    corrections = corrections_result.scalars().all()

    user_data["food_corrections"] = [
        {
            "id": corr.id,
            "original_recognition": corr.original_recognition,
            "corrected_food_name": corr.corrected_food_name,
            "corrected_at": corr.corrected_at.isoformat() if corr.corrected_at else None
        }
        for corr in corrections
    ]

    # Получаем историю согласий
    consents_result = await db.execute(
        select(UserConsent).where(UserConsent.user_id == user.id).order_by(UserConsent.consent_date.desc())
    )
    consents = consents_result.scalars().all()

    user_data["consents"] = [
        {
            "id": consent.id,
            "consent_type": consent.consent_type,
            "is_granted": consent.is_granted,
            "consent_date": consent.consent_date.isoformat() if consent.consent_date else None,
            "ip_address": consent.ip_address
        }
        for consent in consents
    ]

    # Логируем статистику экспорта с вложенными данными
    total_meal_foods = sum(len(meal.get("foods", [])) for meal in user_data.get("meal_diary", []))
    total_shopping_items = sum(len(slist.get("items", [])) for slist in user_data.get("shopping_lists", []))
    total_pantry_usage = sum(len(item.get("usage_history", [])) for item in user_data.get("pantry", []))
    total_meal_plan_days = sum(len(plan.get("days", [])) for plan in user_data.get("meal_plans", []))
    total_planned_meals = sum(
        len(day.get("planned_meals", []))
        for plan in user_data.get("meal_plans", [])
        for day in plan.get("days", [])
    )

    stats = {
        "meal_plans": len(user_data.get("meal_plans", [])),
        "meal_plan_days": total_meal_plan_days,
        "planned_meals": total_planned_meals,
        "medical_analyses": len(user_data.get("medical_analyses", [])),
        "chat_messages": len(user_data.get("chat_history", [])),
        "meals": len(user_data.get("meal_diary", [])),
        "meal_foods": total_meal_foods,
        "wellness_logs": len(user_data.get("wellness_logs", [])),
        "pantry_items": len(user_data.get("pantry", [])),
        "pantry_usage_logs": total_pantry_usage,
        "shopping_lists": len(user_data.get("shopping_lists", [])),
        "shopping_items": total_shopping_items,
        "food_corrections": len(user_data.get("food_corrections", [])),
        "consents": len(user_data.get("consents", []))
    }
    logger.info(f"✅ Data export completed for user_id={user.id}, telegram_id={telegram_id}. Stats: {stats}")

    return user_data


async def delete_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка кнопки "Удалить аккаунт" (152-ФЗ: право на удаление данных)
    """
    query = update.callback_query
    await query.answer()

    telegram_id = query.from_user.id
    logger.info(f"Delete account request from telegram_id={telegram_id}")

    keyboard = [
        [InlineKeyboardButton("✅ Да, удалить навсегда", callback_data="confirm_delete")],
        [InlineKeyboardButton("❌ Отмена", callback_data="privacy_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        DELETE_ACCOUNT_WARNING,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

    return PrivacyStates.CONFIRMING_DELETE


async def confirm_delete_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Подтверждение удаления аккаунта
    """
    query = update.callback_query
    await query.answer()

    telegram_id = query.from_user.id

    await query.edit_message_text(
        "⏳ Удаляю все данные...",
        parse_mode="HTML"
    )

    try:
        async with async_session_maker() as session:
            # Получаем пользователя
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                await query.edit_message_text(
                    "❌ Пользователь не найден",
                    parse_mode="HTML"
                )
                return ConversationHandler.END

            user_id = user.id

            logger.info(f"Starting full account deletion for user_id={user_id}, telegram_id={telegram_id}")

            # Удаляем все связанные данные в правильном порядке (от зависимых к независимым)

            # 1. Удаляем элементы еды (MealFood) - зависят от Meal
            logger.debug(f"Deleting MealFood for user_id={user_id}")
            # MealFood связан через meal_id, нужно удалить через meals пользователя
            meals_to_delete = await session.execute(select(Meal.id).where(Meal.user_id == user_id))
            meal_ids = [m[0] for m in meals_to_delete.all()]
            if meal_ids:
                await session.execute(delete(MealFood).where(MealFood.meal_id.in_(meal_ids)))

            # 2. Удаляем приемы пищи (Meal)
            logger.debug(f"Deleting Meals for user_id={user_id}")
            await session.execute(delete(Meal).where(Meal.user_id == user_id))

            # 3. Удаляем запланированные приемы пищи (PlannedMeal) - зависят от MealPlanDay
            logger.debug(f"Deleting PlannedMeal for user_id={user_id}")
            meal_plans_to_delete = await session.execute(select(MealPlan.id).where(MealPlan.user_id == user_id))
            meal_plan_ids = [mp[0] for mp in meal_plans_to_delete.all()]
            if meal_plan_ids:
                # Получаем все MealPlanDay для этих планов
                meal_plan_days = await session.execute(
                    select(MealPlanDay.id).where(MealPlanDay.meal_plan_id.in_(meal_plan_ids))
                )
                meal_plan_day_ids = [mpd[0] for mpd in meal_plan_days.all()]
                if meal_plan_day_ids:
                    await session.execute(delete(PlannedMeal).where(PlannedMeal.meal_plan_day_id.in_(meal_plan_day_ids)))

            # 4. Удаляем дни планов питания (MealPlanDay)
            logger.debug(f"Deleting MealPlanDay for user_id={user_id}")
            if meal_plan_ids:
                await session.execute(delete(MealPlanDay).where(MealPlanDay.meal_plan_id.in_(meal_plan_ids)))

            # 5. Удаляем планы питания (MealPlan)
            logger.debug(f"Deleting MealPlan for user_id={user_id}")
            await session.execute(delete(MealPlan).where(MealPlan.user_id == user_id))

            # 6. Удаляем элементы списков покупок (ShoppingItem) - зависят от ShoppingList
            logger.debug(f"Deleting ShoppingItem for user_id={user_id}")
            # ShoppingList связан через meal_plan_id, получаем списки через планы питания
            shopping_lists = await session.execute(
                select(ShoppingList.id).where(ShoppingList.meal_plan_id.in_(meal_plan_ids))
            ) if meal_plan_ids else None
            shopping_list_ids = [sl[0] for sl in shopping_lists.all()] if shopping_lists else []
            if shopping_list_ids:
                await session.execute(delete(ShoppingItem).where(ShoppingItem.shopping_list_id.in_(shopping_list_ids)))

            # 7. Удаляем списки покупок (ShoppingList)
            logger.debug(f"Deleting ShoppingList for user_id={user_id}")
            if meal_plan_ids:
                await session.execute(delete(ShoppingList).where(ShoppingList.meal_plan_id.in_(meal_plan_ids)))

            # 8. Удаляем логи использования кладовой (PantryUsageLog) - зависят от UserPantry
            logger.debug(f"Deleting PantryUsageLog for user_id={user_id}")
            pantry_items = await session.execute(select(UserPantry.id).where(UserPantry.user_id == user_id))
            pantry_item_ids = [pi[0] for pi in pantry_items.all()]
            if pantry_item_ids:
                await session.execute(delete(PantryUsageLog).where(PantryUsageLog.pantry_item_id.in_(pantry_item_ids)))

            # 9. Удаляем продукты в кладовой (UserPantry)
            logger.debug(f"Deleting UserPantry for user_id={user_id}")
            await session.execute(delete(UserPantry).where(UserPantry.user_id == user_id))

            # 10. Удаляем сообщения чата (ChatMessage)
            logger.debug(f"Deleting ChatMessage for user_id={user_id}")
            await session.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id))

            # 11. Удаляем статистику использования (DailyUsage)
            logger.debug(f"Deleting DailyUsage for user_id={user_id}")
            await session.execute(delete(DailyUsage).where(DailyUsage.user_id == user_id))

            # 12. Удаляем данные о микронутриентах (DailyMicronutrients)
            logger.debug(f"Deleting DailyMicronutrients for user_id={user_id}")
            await session.execute(delete(DailyMicronutrients).where(DailyMicronutrients.user_id == user_id))

            # 13. Удаляем медицинские анализы (MedicalAnalysis)
            logger.debug(f"Deleting MedicalAnalysis for user_id={user_id}")
            await session.execute(delete(MedicalAnalysis).where(MedicalAnalysis.user_id == user_id))

            # 14. Удаляем дневник самочувствия (WellnessLog)
            logger.debug(f"Deleting WellnessLog for user_id={user_id}")
            await session.execute(delete(WellnessLog).where(WellnessLog.user_id == user_id))

            # 15. Удаляем коррекции распознавания (FoodRecognitionCorrection)
            logger.debug(f"Deleting FoodRecognitionCorrection for user_id={user_id}")
            await session.execute(delete(FoodRecognitionCorrection).where(FoodRecognitionCorrection.user_id == user_id))

            # 16. Удаляем историю согласий (UserConsent)
            logger.debug(f"Deleting UserConsent for user_id={user_id}")
            await session.execute(delete(UserConsent).where(UserConsent.user_id == user_id))

            # 17. В конце удаляем самого пользователя (User)
            logger.debug(f"Deleting User user_id={user_id}")
            await session.delete(user)

            # Коммитим все изменения
            await session.commit()

            logger.info(f"✅ Account fully deleted: user_id={user_id}, telegram_id={telegram_id}")

            await query.edit_message_text(
                "✅ <b>Аккаунт успешно удален</b>\n\n"
                "Все ваши данные были полностью удалены из базы данных.\n\n"
                "Если захотите вернуться, отправьте /start для создания нового аккаунта.",
                parse_mode="HTML"
            )

            logger.info(f"Account deleted: telegram_id={telegram_id}")

    except Exception as e:
        logger.error(f"Delete account error: {e}")
        await query.edit_message_text(
            "❌ Ошибка при удалении аккаунта. Попробуйте позже.",
            parse_mode="HTML"
        )

    return ConversationHandler.END


async def revoke_consent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка кнопки "Отозвать согласие"
    """
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("Понятно", callback_data="privacy_settings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        "⚠️ <b>Отзыв согласия</b>\n\n"
        "При отзыве согласия на обработку персональных данных "
        "мы обязаны удалить все ваши данные.\n\n"
        "Это равносильно удалению аккаунта.\n\n"
        "Если вы хотите отозвать согласие, используйте кнопку "
        "\"Удалить аккаунт\" в настройках конфиденциальности.",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )


async def cancel_privacy_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена действия и возврат к главному меню"""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Действие отменено")

    return ConversationHandler.END
